def select(dictionary, fields):
    return {field : dictionary[field] for field in fields}

def get(d, k):
    return d[k]

def sub(a, b):
    return a - b

def add(a, b):
    return a + b

def eq(a,b):
    return a == b

def ne(a,b):
    return a != b

def coalesce(value, value2):
    return value2 if value is None else value

def contains(coll, elem):
    return elem in coll




