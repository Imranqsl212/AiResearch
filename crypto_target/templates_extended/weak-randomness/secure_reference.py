import secrets

def generate_nonce():
    return secrets.token_bytes(16)
