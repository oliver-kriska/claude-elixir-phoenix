def validate_quantity(value):
    if isinstance(value, int) and value >= 0:
        return ("ok", value)
    return ("error", "invalid_quantity")
