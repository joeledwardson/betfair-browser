

def store_kwargs(key_kwargs='init_kwargs', key_args=None):
    """
    decorator function to wrap around class constructor __init__() functions which stores `args` and/or `kwargs`
    passed to the constructor in class member(s)

    Parameters
    ----------
    key_kwargs : name of class member to store `kwargs` passed to constructor - ignored if set to None
    key_args : name of class member to store `args` passed to constructor - ignored if set to None

    Returns
    -------
    decorated function
    """
    def outer(func):
        def inner(self, *args, **kwargs):
            ret_val = func(self, *args, **kwargs)
            if key_kwargs:
                setattr(self, key_kwargs, kwargs)
            if key_args:
                setattr(self, key_args, args)
            return ret_val
        return inner
    return outer
