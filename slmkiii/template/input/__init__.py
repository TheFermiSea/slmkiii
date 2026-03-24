import struct


class Input(object):
    def __init__(self, data=None):
        self.length = 44
        if isinstance(data, (bytes, bytearray)):
            self._data = data[:self.length]
        elif isinstance(data, dict):
            self.from_dict(data)

        self.enabled = self.data(0, boolean=True)
        self.name = self.data(1, 9).rstrip(b'\0').rstrip().decode('ascii', errors='replace')
        self.message_type = self.data(10)

    def _channel_wrapper(self, offset):
        if self.data(offset) == 127:
            return 'default'
        return self.data(offset) + 1

    def data(self, offset, length=1, boolean=False, signed=False):
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

    def from_dict(self, data):
        if 'channel' in data:
            if data['channel'] == 'default':
                data['channel'] = 127
            else:
                data['channel'] -= 1
        name_bytes = data['name'].encode('ascii', errors='replace')[:9].ljust(9, b'\0')
        self._data = struct.pack(
            '>?9sBB',
            data['enabled'],
            name_bytes,
            data['message_type'],
            0,
        )

    def export_dict(self):
        return {
            'enabled': self.enabled,
            'name': self.name,
            'message_type': self.message_type,
        }

    @property
    def message_type_name(self):
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
    def message_type_name(self, name):
        name_map = {
            'CC': 0, 'NRPN': 1, 'Note': 2, 'Program Change': 3,
            'Song Position': 4, 'Channel Pressure': 5, 'Poly Aftertouch': 6,
        }
        self.message_type = name_map[name]

    @property
    def short_message_type_name(self):
        short_names = ('CC', 'NRPN', 'Not', 'PCh', 'SP', 'ChP', 'PA')
        return short_names[self.message_type]
