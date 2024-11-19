import secrets

secret_key = secrets.token_hex(32)  # Generates a 64-character (256-bit) hex key
print(f"Your secret key: {secret_key}")
