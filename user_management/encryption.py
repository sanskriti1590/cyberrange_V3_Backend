from cryptography.fernet import Fernet

# aes_key = Fernet.generate_key()
aes_key = b'K3udNaqqfsBaxs2jwWOYZsDt6F8pqF9okyTdSH5zJVc='
cipher_suite = Fernet(aes_key)
