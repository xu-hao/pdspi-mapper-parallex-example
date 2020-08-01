def select(dictionary, fields):
    return {field : dictionary[field] for field in fields}

def coalesce(value, value2):
    return value2 if value is None else value



