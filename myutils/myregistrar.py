class RegistrarException(Exception):
    pass


class MyRegistrar:
    def __init__(self):
        self.register = dict()

    def register_element(self, obj):
        """
        register an element, add to dictionary of elements
        """
        if obj.__name__ in self.register:
            raise Exception(f'registering object "{obj.__name__}", but already exists!')
        else:
            self.register[obj.__name__] = obj
            return obj

    def __getitem__(self, item):
        if item in self.register:
            return self.register[item]
        else:
            raise RegistrarException(f'object "{item}" not found in registrar')


