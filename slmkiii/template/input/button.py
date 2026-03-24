from __future__ import annotations

import struct
from slmkiii.template.input import Input, _validate_int_range


class Button(Input):
    def __init__(self, data: bytes | bytearray | dict | None = None):
        super(Button, self).__init__(data)
        self.behavior = self.data(12)
        self.action = self.data(13)
        self.first_param = self.data(14, 2)
        self.second_param = self.data(16, 2)
        self.step = self.data(18, 2, signed=True)
        self.wrap = self.data(20, boolean=True)
        self.pair = self.data(21, boolean=True)
        self.channel = self._channel_wrapper(22)
        self.third_param = self.data(23)
        self.fourth_param = self.data(24)
        self.lsb_index = self.data(25)

    @property
    def behavior(self) -> int:
        return self._behavior

    @behavior.setter
    def behavior(self, value: int) -> None:
        _validate_int_range('behavior', value, 0, 255)
        self._behavior = value

    @property
    def action(self) -> int:
        return self._action

    @action.setter
    def action(self, value: int) -> None:
        _validate_int_range('action', value, 0, 255)
        self._action = value

    @property
    def first_param(self) -> int:
        return self._first_param

    @first_param.setter
    def first_param(self, value: int) -> None:
        _validate_int_range('first_param', value, 0, 65535)
        self._first_param = value

    @property
    def second_param(self) -> int:
        return self._second_param

    @second_param.setter
    def second_param(self, value: int) -> None:
        _validate_int_range('second_param', value, 0, 65535)
        self._second_param = value

    @property
    def third_param(self) -> int:
        return self._third_param

    @third_param.setter
    def third_param(self, value: int) -> None:
        _validate_int_range('third_param', value, 0, 255)
        self._third_param = value

    @property
    def fourth_param(self) -> int:
        return self._fourth_param

    @fourth_param.setter
    def fourth_param(self, value: int) -> None:
        _validate_int_range('fourth_param', value, 0, 255)
        self._fourth_param = value

    @property
    def lsb_index(self) -> int:
        return self._lsb_index

    @lsb_index.setter
    def lsb_index(self, value: int) -> None:
        _validate_int_range('lsb_index', value, 0, 255)
        self._lsb_index = value

    def from_dict(self, data: dict, extend: bool = False) -> dict:
        data = super(Button, self).from_dict(data)
        # Step is stored as a signed big-endian 16-bit short, matching
        # the decode in __init__ which uses struct.unpack('>h', ...).
        self._data += struct.pack(
            '>BBHHh??BBBB',
            data['behavior'],
            data['action'],
            data['first_param'],
            data['second_param'],
            data['step'],
            data['wrap'],
            data['pair'],
            data['channel'],
            data['third_param'],
            data['fourth_param'],
            data['lsb_index'],
        )
        if extend is False:
            self._data = self._data.ljust(self.length, b'\0')
        return data

    def export_dict(self) -> dict:
        data = super(Button, self).export_dict()
        data.update({
            'behavior': self.behavior,
            'action': self.action,
            'first_param': self.first_param,
            'first_param_name': self.first_param_name,
            'second_param': self.second_param,
            'second_param_name': self.second_param_name,
            'step': self.step,
            'wrap': self.wrap,
            'pair': self.pair,
            'channel': self.channel,
            'third_param': self.third_param,
            'third_param_name': self.third_param_name,
            'fourth_param': self.fourth_param,
            'fourth_param_name': self.fourth_param_name,
            'lsb_index': self.lsb_index,
        })
        return data

    def configure_cc(self, channel: int | str, cc_num: int,
                     name: str | None = None) -> None:
        super().configure_cc(channel, cc_num, name)
        self.fourth_param = cc_num

    def configure_note(self, channel: int | str, note: int,
                       velocity: int = 127, name: str | None = None) -> None:
        super().configure_note(channel, note, velocity, name)
        self.first_param = note
        self.second_param = 0
        self.third_param = velocity
        self.fourth_param = note

    @property
    def first_param_name(self) -> str:
        first_param_names = {
            0: 'Down Value',
            1: 'On Value',
            2: 'From Value',
            3: 'Trigger Value',
        }
        return first_param_names[self.behavior]

    @property
    def second_param_name(self) -> str:
        second_param_names = {
            0: 'Up Value',
            1: 'Off Value',
            2: 'To Value',
            3: 'n/a',
        }
        return second_param_names[self.behavior]

    @property
    def third_param_name(self) -> str:
        if self.message_type == 2:
            return 'Note'
        return 'n/a'

    @property
    def fourth_param_name(self) -> str:
        if self.message_type == 0:
            return 'CC Index'
        if self.message_type == 1:
            return 'MSB Index'
        return 'n/a'
