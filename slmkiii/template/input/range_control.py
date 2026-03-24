from slmkiii.template.input import Input


class RangeControl(Input):
    """Base class for continuous-range controls (Fader, Knob).

    Provides common from_value/to_value attributes shared by faders,
    knobs, wheels, pedals, and pad pressures.
    """
    def __init__(self, data=None):
        self.from_value = 0
        self.to_value = 0
        super(RangeControl, self).__init__(data)
