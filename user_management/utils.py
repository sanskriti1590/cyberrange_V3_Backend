import random
import string
import jwt
import hashlib

from django.conf import settings
from datetime import datetime, timedelta
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from celery import shared_task
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from database_management.pymongo_client import (
    user_collection, 
    id_collection,
    otp_hash_dump_collection
)
from core.utils import EMAIL_LOGO_URL


USER_ROLES = [
    'RED TEAM', 
    'BLUE TEAM', 
    'PURPLE TEAM', 
    'WHITE TEAM', 
    'YELLOW TEAM'
]



class InvalidUser(AuthenticationFailed):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = ("Invalid Credentials")
    default_code = 'user_credentials_not_valid'


def get_user_from_jwt_token(token):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload['user_id']

        user = user_collection.find_one({'user_id': user_id})
        if not user:
            raise AuthenticationFailed('Invalid Token.')

    except ExpiredSignatureError as e:
        raise InvalidUser("Expired Token.")
    except InvalidTokenError as e:
        raise InvalidUser('Invalid token.')
    except Exception as e:
        raise InvalidUser('Invalid token.')

    keys_to_remove = ['_id', 'password']
    for key in keys_to_remove:
        user.pop(key, None)

    return user, payload

def get_user_from_refresh_token(token):
    user, payload = get_user_from_jwt_token(token)
    # Check if the token is a refresh token
    if payload['token_type'] != 'refresh':
        raise AuthenticationFailed('Invalid Refresh Token.')
    else:
        return user
    
def get_user_from_access_token(token):
    user, payload = get_user_from_jwt_token(token)
    # Check if the token is a refresh token
    if payload['token_type'] == 'refresh':
        raise AuthenticationFailed('Invalid Access Token.')
    else:
        return user


def generate_access_token_payload(access_token):
    access_token_payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=['HS256'])
    
    user_id = access_token_payload['user_id']
    user = user_collection.find_one({'user_id': user_id})


    access_token_expiration = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRATION_MINUTES)
    # access_token_expiration = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRATION_SECONDS)
    
    access_token_payload['exp'] = access_token_expiration.timestamp()
    access_token_payload['user_full_name'] = user['user_full_name']
    access_token_payload['is_admin'] = user['is_admin']
    access_token_payload['is_verified'] = user['is_verified']
    # access_token_payload['user_avatar'] = user['user_avatar']
    new_access_token = jwt.encode(access_token_payload, settings.SECRET_KEY, algorithm='HS256')
    return new_access_token


def generate_otp():
    otp = ''.join(random.choices(string.digits + string.ascii_uppercase , k=6))
    otp_hash = hashlib.md5(otp.encode()).hexdigest()
    
    while otp_hash_dump_collection.find_one({"otp_hash": otp_hash}):
        otp = ''.join(random.choices(string.digits + string.ascii_uppercase , k=6))
        otp_hash = hashlib.md5(otp.encode()).hexdigest()

    otp_hash_dump_obj = {
        "otp_hash": otp_hash
    }
    otp_hash_dump_collection.insert_one(otp_hash_dump_obj)

    return otp, otp_hash

def send_otp_by_sms(mobile_number, otp):
    # key = "a3ee5c1c-ea5c-11ed-addf-0200cd936042"
    # # mobile_number = "8700488722"
    # # otp = "2H4J8G"
    # message = f"Welcome to Tyr's Arena! Your One-Time-Password (OTP) for registration is {otp}. Please enter this code within the next 10 minutes to complete your registration.\nThank you for choosing Tyr's Arena."
    # url = f"https://2factor.in/API/V1/{key}/SMS/{mobile_number}/{otp}/{message}"
    # res = requests.get(url)
    print("\n\n", mobile_number)
    print(otp, "\n\n")

@shared_task
def send_otp_by_email(user_email, otp, username, type_f=None):
    logo_url = EMAIL_LOGO_URL
    from_email = 'support@bhumiitech.com'
    recipient_list = [user_email]

    # Render the HTML template with OTP
    if type_f is None:
        html_content = render_to_string('email_otp_template.html', {'logo_url': logo_url, 'otp': otp, 'user_name': username})
        subject = 'Welcome to Cyber Range - User Verification'

    else:
        html_content = render_to_string('forgot_password_otp_template.html', {'logo_url': logo_url, 'otp': otp, 'user_name': username})
        subject = 'Welcome to Cyber Range - Change Password OTP'


    # Create the email message object
    msg = EmailMultiAlternatives(subject, '', from_email, recipient_list)
    msg.attach_alternative(html_content, "text/html")

    # Send the email
    msg.send()
