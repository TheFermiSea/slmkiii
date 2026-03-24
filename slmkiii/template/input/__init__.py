from __future__ import annotations

import struct
import warnings


def _validate_int_range(name: str, value: int, min_val: int, max_val: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"{name} must be an integer, got {type(value).__name__}"
        )
    if value < min_val or value > max_val:
        raise ValueError(
            f"{name} must be between {min_val} and {max_val}, got {value}"
        )


class Input(object):
    def __init__(self, data: bytes | bytearray | dict | None = None):
        self.length = 44
        if isinstance(data, (bytes, bytearray)):
            self._data = data[:self.length]
        elif isinstance(data, dict):
            self.from_dict(data)

        self.enabled = self.data(0, boolean=True)
        self.name = self.data(1, 9).rstrip(b'\0').rstrip().decode('ascii', errors='replace')
        self.message_type = self.data(10)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise ValueError(
                f"enabled must be a bool, got {type(value).__name__}"
            )
        self._enabled = value

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValueError(
                f"name must be a string, got {type(value).__name__}"
            )
        self._name = value[:9]

    @property
    def message_type(self) -> int:
        return self._message_type

    @message_type.setter
    def message_type(self, value: int) -> None:
        _validate_int_range('message_type', value, 0, 6)
        self._message_type = value

    @property
    def channel(self) -> int | str:
        return self._channel

    @channel.setter
    def channel(self, value: int | str) -> None:
        if value == 'default':
            self._channel = value
        elif isinstance(value, int) and not isinstance(value, bool):
            if value < 1 or value > 16:
                raise ValueError(
                    f"channel must be between 1 and 16, got {value}"
                )
            self._channel = value
        else:
            raise ValueError(
                f"channel must be int 1-16 or 'default', got {value!r}"
            )

    def _channel_wrapper(self, offset: int) -> int | str:
        if self.data(offset) == 127:
            return 'default'
        return self.data(offset) + 1

    def data(self, offset: int, length: int = 1, boolean: bool = False,
             signed: bool = False) -> int | bool | bytes:
        value = self._data[offset:offset + length]
        if length > 2:
            return value
        elif length == 2:
            if signed:
                return struct.unpack('>h', value)[0]
            else:
                return struct.unpack('>H', value)[0]
        if boolean:
            return bool(value[0])
        return value[0]

    def from_dict(self, data: dict) -> dict:
        data = dict(data)
        if 'channel' in data:
            if data['channel'] == 'default':
                data['channel'] = 127
            else:
                data['channel'] -= 1
        name_str = data['name']
        name_bytes = name_str.encode('ascii', errors='replace')[:9].ljust(9, b'\0')
        if name_bytes != name_str.encode('utf-8', errors='replace')[:9].ljust(9, b'\0'):
            warnings.warn(
                f"Non-ASCII characters in name '{name_str}' were replaced",
                UserWarning, stacklevel=2,
            )
        self._data = struct.pack(
            '>?9sBB',
            data['enabled'],
            name_bytes,
            data['message_type'],
            0,
        )
        return data

    def export_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'name': self.name,
            'message_type': self.message_type,
        }

    @property
    def message_type_name(self) -> str:
        message_type_names = (
            'CC',
            'NRPN',
            'Note',
            'Program Change',
            'Song Position',
            'Channel Pressure',
            'Poly Aftertouch',
        )
        return message_type_names[self.message_type]

    @message_type_name.setter
    def message_type_name(self, name: str) -> None:
        name_map = {
            'CC': 0, 'NRPN': 1, 'Note': 2, 'Program Change': 3,
            'Song Position': 4, 'Channel Pressure': 5, 'Poly Aftertouch': 6,
        }
        self.message_type = name_map[name]

    @property
    def short_message_type_name(self) -> str:
        short_names = ('CC', 'NRPN', 'Not', 'PCh', 'SP', 'ChP', 'PA')
        return short_names[self.message_type]

    def configure_cc(self, channel: int | str, cc_num: int,
                     name: str | None = None) -> None:
        """Configure this control as a CC message."""
        self.enabled = True
        self.message_type_name = 'CC'
        self.channel = channel
        if name is not None:
            self.name = name

    def configure_note(self, channel: int | str, note: int,
                       velocity: int = 127, name: str | None = None) -> None:
        """Configure this control as a Note message."""
        self.enabled = True
        self.message_type_name = 'Note'
        self.channel = channel
        if name is not None:
            self.name = name

    def __repr__(self) -> str:
        ch = ''
        if hasattr(self, '_channel'):
            ch = f' ch={self.channel}'
        state = 'enabled' if self.enabled else 'disabled'
        return (f"<{type(self).__name__} {self.name!r} "
                f"{self.message_type_name}{ch} {state}>")

    def __str__(self) -> str:
        return repr(self)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return self.export_dict() == other.export_dict()
