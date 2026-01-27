import requests
import random

# API Endpoint
url = "http://localhost:8000/api/user/register/"

# Users with "WHITE" role
white_ids = {1, 7, 13, 19, 25}

# Loop from 1 to 30
for i in range(1, 31):
    # Generate user-specific values
    full_name = f"player{i}"
    email = f"user{i}@bhumiitech.com"
    password = f"user{i}#519"
    mobile_number = f"9{random.randint(100000000, 999999999)}"  # 10-digit random number starting with 9
    user_role = "WHITE TEAM" if i in white_ids else "RED TEAM"

    # Prepare payload
    payload = {
        "user_full_name": full_name,
        "mobile_number": mobile_number,
        "email": email,
        "password": password,
        "confirm_password": password,
        "user_role": user_role
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 201:
            print(f" User {i} created successfully.")
        else:
            print(f"Failed to create User {i}: {response.status_code}, {response.text}")
    except Exception as e:
        print(f" Error creating User {i}: {e}")
