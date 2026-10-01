import hashlib

def derive_key(password, salt):
    return hashlib.sha256(password.encode()).digest()
