def validate_padding(data, block_size):
    if not data or len(data) % block_size:
        return False
    count = data[-1]
    return 1 <= count <= block_size and data[-count:] == bytes([count]) * count
