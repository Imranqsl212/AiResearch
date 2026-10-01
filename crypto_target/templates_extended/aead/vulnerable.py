from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt(key, plaintext, associated_data):
    nonce = b"\x00" * 12
    return nonce + AESGCM(key).encrypt(nonce, plaintext, associated_data)

def decrypt(key, ciphertext, associated_data):
    return AESGCM(key).decrypt(ciphertext[:12], ciphertext[12:], associated_data)
