def sanitize_log(message):
    return message.replace("secret=", "secret=<redacted>")
