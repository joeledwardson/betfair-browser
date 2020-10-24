"""increment and count number of occurances"""


class Counter:
    def __init__(self, initial_value: int = 0):
        self.value: int = initial_value

    def inc(self) -> int:
        self.value += 1
        return self.value

    def __repr__(self):
        return self.value