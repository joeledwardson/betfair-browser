class Intermediary:
    """
    increment value and return string for intermediaries
    """
    def __init__(self):
        self.value = 0

    def next(self):
        self.value += 1
        return str(self.value)
