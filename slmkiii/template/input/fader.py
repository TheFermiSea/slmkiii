from __future__ import annotations

import struct
from slmkiii.template.input import Input, _validate_int_range


class Fader(Input):
    def __init__(self, data: bytes | bytearray | dict | None = None):
        super(Fader, self).__init__(data)
        self.channel = self._channel_wrapper(12)
        self.from_value = self.data(13, 2)
        self.to_value = self.data(15, 2)
        self.first_param = self.data(17)
        self.second_param = self.data(18)
        self.lsb_index = self.data(19)

    @property
    def first_param(self) -> int:
        return self._first_param

    @first_param.setter
    def first_param(self, value: int) -> None:
        _validate_int_range('first_param', value, 0, 255)
        self._first_param = value

    @property
    def second_param(self) -> int:
        return self._second_param

    @second_param.setter
    def second_param(self, value: int) -> None:
        _validate_int_range('second_param', value, 0, 255)
        self._second_param = value

    @property
    def lsb_index(self) -> int:
        return self._lsb_index

    @lsb_index.setter
    def lsb_index(self, value: int) -> None:
        _validate_int_range('lsb_index', value, 0, 255)
        self._lsb_index = value

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
        data = super(Fader, self).from_dict(data)
        self._data += struct.pack(
            '>BHHBBB',
            data['channel'],
            data['from_value'],
            data['to_value'],
            data['first_param'],
            data['second_param'],
            data['lsb_index'],
        )
        self._data = self._data.ljust(self.length, b'\0')
        return data

    def export_dict(self) -> dict:
        data = super(Fader, self).export_dict()
        data.update({
            'channel': self.channel,
            'from_value': self.from_value,
            'to_value': self.to_value,
            'first_param': self.first_param,
            'first_param_name': self.first_param_name,
            'second_param': self.second_param,
            'second_param_name': self.second_param_name,
            'lsb_index': self.lsb_index,
        })
        return data

    def configure_cc(self, channel: int | str, cc_num: int,
                     name: str | None = None) -> None:
        super().configure_cc(channel, cc_num, name)
        self.second_param = cc_num

    @property
    def first_param_name(self) -> str:
        param_names = {
            0: 'Eight Bit',
            1: 'Eight Bit',
        }
        if self.message_type in param_names:
            return param_names[self.message_type]
        return 'n/a'

    @property
    def second_param_name(self) -> str:
        param_names = {
            0: 'CC Index',
            1: 'MSB Index',
        }
        if self.message_type in param_names:
            return param_names[self.message_type]
        return 'n/a'
