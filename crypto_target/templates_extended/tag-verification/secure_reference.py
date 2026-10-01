import hmac

def verify_tag(message, tag, expected):
    return hmac.compare_digest(tag, expected)
