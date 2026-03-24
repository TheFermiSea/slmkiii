import binascii
import json
import os
import struct
import slmkiii.errors
import slmkiii.utils as utils
from slmkiii.template.defaults import defaults
from slmkiii.template.sections import sections

version = 1.0


class Template():
    def __init__(self, data=None):
        self.name = ''
        for sdata in sections:
            setattr(self, sdata['name'], [])

        if data is None:
            self._new()
        elif isinstance(data, (bytes, bytearray)):
            if len(data) == 3408:
                self._open_raw(data)
            elif len(data) == 4214:
                self._open_sysex(None, raw=data)
            else:
                raise slmkiii.errors.ErrorUnknownData()
        elif isinstance(data, str) and os.path.isfile(data):
            self._open_file(data)
        else:
            raise slmkiii.errors.ErrorUnknownData()

    def _open_file(self, filename):
        ftype = utils.file_type(filename)
        if ftype == 'json':
            self._open_json(filename)
        elif ftype == 'sysex':
            self._open_sysex(filename)

    def _new(self):
        data = self.patch_defaults({})
        data['version'] = version
        self._data_to_raw(data)

    def _open_json(self, filename):
        with open(filename, 'r') as jsonfile:
            data = self.patch_defaults(json.load(jsonfile))
        self._data_to_raw(data)

    def _data_to_raw(self, data):
        # If we add more versions, fail hard instead of breaking old versions
        if data['version'] != version:
            raise slmkiii.errors.ErrorUnknownVersion(data['version'])

        # Header
        name_bytes = data['name'].encode('ascii', errors='replace')[:16].ljust(16, b'\0')
        raw = struct.pack('>4s16s', b'\x50\x0d\x00\x00', name_bytes)

        for sdata in sections:
            for item in data[sdata['name']]:
                raw += sdata['class'](item)._data

        self._open_raw(raw)

    def _open_sysex(self, filename, raw=None):
        if raw is None:
            with open(filename, 'rb') as sysexfile:
                raw = sysexfile.read()

        checksum = 0
        data = b''
        for chunk in raw[1:-1].split(b'\xf7\xf0'):
            block_type = chunk[6]
            if block_type == 1:
                data = b''
            elif block_type == 2:
                raw_chunk = utils.seven_to_eight(chunk[17:])
                data += raw_chunk
                checksum = binascii.crc32(raw_chunk, checksum) & 0xffffffff
            elif block_type == 3:
                if checksum != utils.nibbles_to_bytes(chunk[17:]):
                    raise slmkiii.errors.ErrorInvalidChecksum()
        self._open_raw(data)

    def _open_raw(self, data):
        ofst = 20  # header length
        block_length = 44
        self._data = data
        self._header = self._data[:ofst]
        self.name = self._header[4:17].rstrip(b'\0').rstrip().decode('ascii', errors='replace')
        self._body = self._data[ofst:]

        for sdata in sections:
            items = []
            for _ in range(sdata['items']):
                items.append(sdata['class'](data[ofst:ofst+block_length]))
                ofst += block_length
            setattr(self, sdata['name'], items)

    def patch_defaults(self, data):
        for sdata in sections:
            section = sdata['name']
            if section not in data:
                data[section] = []
            if len(data[section]) > sdata['items']:
                raise slmkiii.errors.ErrorTooManyItemsInSection(
                    section,
                    len(data[section]),
                    sdata['items'],
                )
            elif len(data[section]) < sdata['items']:
                needed = sdata['items'] - len(data[section])
                data[section] += [defaults[section] for _ in range(needed)]
            new_structure = []
            for item in data[section]:
                new_item = defaults[section].copy()
                new_item.update(item)
                new_structure.append(new_item)
            data[section] = new_structure
        for k in ('name', 'version'):
            if k not in data:
                data[k] = defaults[k]
        return data

    def _rebuild(self):
        """Rebuild raw _data from current control attributes."""
        name_bytes = self.name.encode('ascii', errors='replace')[:16].ljust(16, b'\0')
        raw = struct.pack('>4s16s', b'\x50\x0d\x00\x00', name_bytes)
        for sdata in sections:
            for item in getattr(self, sdata['name']):
                d = item.export_dict()
                rebuilt = sdata['class'](d)
                raw += rebuilt._data
        self._data = raw

    def save(self, filename, minify=False, overwrite=False):
        ftype = utils.file_type(filename)
        if overwrite is False:
            if os.path.exists(filename):
                raise slmkiii.errors.ErrorFileExists(filename)
        if ftype == 'json':
            self.export_json(filename, minify)
        elif ftype == 'sysex':
            self.export_sysex(filename)

    def export_sysex(self, filename=None):
        self._rebuild()

        header = struct.pack('>7B', 240, 0, 32, 41, 2, 10, 3)
        data = header + struct.pack('>B2L4B', 1, 0, 0, 2, 0, 1, 247)

        # Data
        block = 0
        checksum = 0
        while (block * 256) <= len(self._data):
            chunk = self._data[block * 256:(block + 1) * 256]
            checksum = binascii.crc32(chunk, checksum) & 0xffffffff
            encoded_data = utils.eight_to_seven(chunk)
            data += header
            data += struct.pack(
                '>B2L2B{}sB'.format(len(encoded_data)),
                2, 0, block + 1, 2, 0, encoded_data, 247,
            )
            block += 1

        # Footer/crc
        data += header
        encoded_checksum = utils.bytes_to_nibbles(checksum)
        data += struct.pack('>B2L2B8sB', 3, 0, 15, 2, 0, encoded_checksum, 247)

        if filename is not None:
            with open(filename, 'wb') as sysexfile:
                sysexfile.write(data)

        return data

    def export_json(self,
                    filename=None,
                    minify=False):
        data = {x['name']: [] for x in sections}

        for sdata in sections:
            items = getattr(self, sdata['name'])
            for item in items:
                data[sdata['name']].append(item.export_dict())

        data['name'] = self.name
        data['version'] = version
        data['-NOTES-'] = (
            '*_param_name fields are for reference and are not editable',
            'Many fields are used/unused based on behavior or message_type',
        )

        if minify:
            for sdata in sections:
                new_structure = []
                for item in data[sdata['name']]:
                    for key, value in defaults[sdata['name']].items():
                        if item[key] == value:
                            item.pop(key)
                    for key, value in item.items():
                        if key[-11:] in ('_param_name', 'method_name'):
                            item.pop(key)
                    new_structure.append(item)
                data[sdata['name']] = new_structure

        if filename is not None:
            with open(filename, 'w') as jsonfile:
                json.dump(data,
                          jsonfile,
                          indent=4,
                          sort_keys=True,
                          separators=(',', ': '))

        return data
