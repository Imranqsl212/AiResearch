def validate_certificate(cert, trusted_roots):
    return cert in trusted_roots
