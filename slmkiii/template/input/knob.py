from __future__ import annotations

import struct
from slmkiii.template.input import Input, _validate_int_range


class Knob(Input):
    def __init__(self, data: bytes | bytearray | dict | None = None):
        super(Knob, self).__init__(data)
        self.first_param = self.data(12)
        self.lsb_index = self.data(13)
        self.relative = self.data(14)
        self.eight_bit = self.data(15)
        self.pivot = self.data(16, 2)
        self.step = self.data(18)
        self.resolution = self.data(19, 2)
        self.channel = self._channel_wrapper(21)
        self.from_value = self.data(22, 2)
        self.to_value = self.data(24, 2)

    @property
    def first_param(self) -> int:
        return self._first_param

    @first_param.setter
    def first_param(self, value: int) -> None:
        _validate_int_range('first_param', value, 0, 255)
        self._first_param = value

    @property
    def lsb_index(self) -> int:
        return self._lsb_index

    @lsb_index.setter
    def lsb_index(self, value: int) -> None:
        _validate_int_range('lsb_index', value, 0, 255)
        self._lsb_index = value

    @property
    def relative(self) -> int:
        return self._relative

    @relative.setter
    def relative(self, value: int) -> None:
        _validate_int_range('relative', value, 0, 255)
        self._relative = value

    @property
    def eight_bit(self) -> int:
        return self._eight_bit

    @eight_bit.setter
    def eight_bit(self, value: int) -> None:
        _validate_int_range('eight_bit', value, 0, 255)
        self._eight_bit = value

    @property
    def pivot(self) -> int:
        return self._pivot

    @pivot.setter
    def pivot(self, value: int) -> None:
        _validate_int_range('pivot', value, 0, 65535)
        self._pivot = value

    @property
    def step(self) -> int:
        return self._step

    @step.setter
    def step(self, value: int) -> None:
        _validate_int_range('step', value, 0, 255)
        self._step = value

    @property
    def resolution(self) -> int:
        return self._resolution

    @resolution.setter
    def resolution(self, value: int) -> None:
        _validate_int_range('resolution', value, 0, 65535)
        self._resolution = value

    @property
    def from_value(self) -> int:
        return self._from_value

    @from_value.setter
    def from_value(self, value: int) -> None:
        _validate_int_range('from_value', value, 0, 65535)
        self._from_value = value

    @property
    def to_value(self) -> int:
        return self._to_value

    @to_value.setter
    def to_value(self, value: int) -> None:
        _validate_int_range('to_value', value, 0, 65535)
        self._to_value = value

    def from_dict(self, data: dict) -> dict:
        data = super(Knob, self).from_dict(data)
        self._data += struct.pack(
            '>BBBBHBHBHH',
            data['first_param'],
            data['lsb_index'],
            data['relative'],
            data['eight_bit'],
            data['pivot'],
            data['step'],
            data['resolution'],
            data['channel'],
            data['from_value'],
            data['to_value'],
        )
        self._data = self._data.ljust(self.length, b'\0')
        return data

    def export_dict(self) -> dict:
        data = super(Knob, self).export_dict()
        data.update({
            'first_param': self.first_param,
            'first_param_name': self.first_param_name,
            'lsb_index': self.lsb_index,
            'relative': self.relative,
            'eight_bit': self.eight_bit,
            'pivot': self.pivot,
            'step': self.step,
            'resolution': self.resolution,
            'channel': self.channel,
            'from_value': self.from_value,
            'to_value': self.to_value,
        })
        return data

    def configure_cc(self, channel: int | str, cc_num: int,
                     name: str | None = None) -> None:
        super().configure_cc(channel, cc_num, name)
        self.first_param = cc_num

    @property
    def first_param_name(self) -> str:
        param_names = {
            0: 'CC Index',
            1: 'MSB Index',
            2: 'Velocity',
        }
        if self.message_type in param_names:
            return param_names[self.message_type]
        return 'n/a'
