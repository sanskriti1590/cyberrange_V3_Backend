from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings

from .utils import get_user_from_access_token


class CustomRefreshToken(RefreshToken):
    
    @classmethod
    def for_user(cls, user):
        """
        Returns an authorization token for the given user that will be provided
        after authenticating the user's credentials.
        """
        if user.get('refresh'):
            token = RefreshToken(user['refresh'])
            user_id = token.payload['user_id']
        else:
            user_id = str(user['user_id'])

        token = RefreshToken()
        token[api_settings.USER_ID_CLAIM] = user_id

        return token


class CustomJWTAuthentication(BaseAuthentication):
    keyword = 'Bearer'

    def authenticate(self, request):
        auth_header = get_authorization_header(request).split()
        if not auth_header:
            return None

        if auth_header[0].decode('utf-8') != self.keyword:
            return None

        if len(auth_header) == 1:
            raise AuthenticationFailed('Invalid Request.')

        elif len(auth_header) > 2:
            raise AuthenticationFailed('Invalid Request.')

        token = auth_header[1].decode('utf-8')
        user = get_user_from_access_token(token)
        
        return (user, token)
