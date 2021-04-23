class RegistrarException(Exception):
    pass


class MyRegistrar:
    def __init__(self):
        self._reg = dict()

    def register_element(self, obj):
        """
        register an element, add to dictionary of elements
        """
        if obj.__name__ in self._reg:
            raise Exception(f'registering object "{obj.__name__}", but already exists!')
        else:
            self._reg[obj.__name__] = obj
            return obj

    def __getitem__(self, item):
        if item in self._reg:
            return self._reg[item]
        else:
            raise RegistrarException(f'object "{item}" not found in registrar')

    def __contains__(self, item):
        return item in self._reg
