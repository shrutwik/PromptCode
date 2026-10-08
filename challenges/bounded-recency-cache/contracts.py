def validate_capacity(capacity):
    if type(capacity) is not int or capacity<0:raise ValueError('invalid capacity')
