import hashlib

def derive_key(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120000, dklen=32)
