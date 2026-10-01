import secrets

def new_iv():
    return secrets.token_bytes(12)
