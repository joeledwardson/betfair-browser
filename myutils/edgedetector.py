class EdgeDetector:
    """
    detect when a boolean value changes from True to False and vice-versa comparing to previous-state value
    """
    def __init__(self, initial_value: bool):
        self._value: bool = initial_value
        self._previous: bool = initial_value
        self._rising: bool = False
        self._falling: bool = False

    def update(self, new_value: bool) -> bool:
        """update value, return True if rising or falling edge"""
        self._previous = self._value
        self._value = new_value
        self._rising = self._value and not self._previous
        self._falling = self._previous and not self._value
        return self._rising or self._falling

    @property
    def current_value(self) -> bool:
        return self._value

    @property
    def rising(self):
        return self._rising

    @property
    def falling(self):
        return self._falling