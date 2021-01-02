class MyRegistrar:
    def __init__(self):
        self.register = dict()

    def register_element(self, obj):
        """
        register an element, add to dictionary of elements
        """
        if obj.__name__ in self.register:
            raise Exception(f'registering feature "{obj.__name__}", but already exists!')
        else:
            self.register[obj.__name__] = obj
            return obj
