from __future__ import annotations

import binascii
import copy
import json
import os
import struct
import warnings
import slmkiii.errors
import slmkiii.utils as utils
from slmkiii.template.defaults import defaults
from slmkiii.template.sections import sections
from slmkiii.template.input.button import Button
from slmkiii.template.input.knob import Knob
from slmkiii.template.input.fader import Fader

# Template format version supported by this library
TEMPLATE_VERSION = 1.0

# Total bytes of decoded (8-bit) template data: 20-byte header + 77 controls * 44 bytes
RAW_TEMPLATE_SIZE = 3408

# Total bytes of a SysEx-encoded (.syx) template file
SYSEX_TEMPLATE_SIZE = 4214

# 4-byte magic identifier at the start of every raw template header
TEMPLATE_HEADER_MAGIC = b'\x50\x0d\x00\x00'

# Bytes per control block in the raw binary format (buttons, knobs, faders, etc.)
CONTROL_BLOCK_SIZE = 44

# Byte length of the template header (magic + 16-char name)
HEADER_SIZE = 20

# SysEx header identifying the Novation SL MkIII (manufacturer + device IDs)
# 240=F0 SysEx start, 0x00/0x20/0x29=Novation vendor ID, 0x02/0x0A/0x03=device
SYSEX_HEADER = (240, 0, 32, 41, 2, 10, 3)

# SysEx end-of-message byte (0xF7)
SYSEX_END = 247

# SysEx block type markers
SYSEX_BLOCK_INIT = 1    # start-of-template marker
SYSEX_BLOCK_DATA = 2    # data payload block
SYSEX_BLOCK_CRC = 3     # CRC checksum footer


class Template():
    def __init__(self, data: bytes | bytearray | str | None = None):
        self.name = ''
        self.metadata: dict = {}
        for sdata in sections:
            setattr(self, sdata['name'], [])

        if data is None:
            self._new()
        elif isinstance(data, (bytes, bytearray)):
            if len(data) == RAW_TEMPLATE_SIZE:
                self._open_raw(data)
            elif len(data) == SYSEX_TEMPLATE_SIZE:
                self._open_sysex(None, raw=data)
            else:
                raise slmkiii.errors.ErrorUnknownData(type(data), len(data))
        elif isinstance(data, str) and os.path.isfile(data):
            self._open_file(data)
        else:
            raise slmkiii.errors.ErrorUnknownData(type(data), None)

    def _open_file(self, filename: str) -> None:
        ftype = utils.file_type(filename)
        if ftype == 'json':
            self._open_json(filename)
        elif ftype == 'sysex':
            self._open_sysex(filename)

    def _new(self) -> None:
        data = self.patch_defaults({})
        data['version'] = TEMPLATE_VERSION
        self._data_to_raw(data)

    def _open_json(self, filename: str) -> None:
        with open(filename, 'r') as jsonfile:
            loaded = json.load(jsonfile)
        if 'metadata' in loaded:
            self.metadata = loaded.pop('metadata')
        data = self.patch_defaults(loaded)
        self._data_to_raw(data)

    def _data_to_raw(self, data: dict) -> None:
        if data['version'] != TEMPLATE_VERSION:
            raise slmkiii.errors.ErrorUnknownVersion(data['version'], TEMPLATE_VERSION)

        name_str = data['name']
        name_bytes = name_str.encode('ascii', errors='replace')[:16].ljust(16, b'\0')
        if name_str and name_bytes.rstrip(b'\0') != name_str.encode('utf-8', errors='replace')[:16].rstrip(b'\0'):
            warnings.warn(
                f"Non-ASCII characters in template name '{name_str}' were replaced",
                UserWarning, stacklevel=2,
            )
        raw = struct.pack('>4s16s', TEMPLATE_HEADER_MAGIC, name_bytes)

        for sdata in sections:
            for item in data[sdata['name']]:
                raw += sdata['class'](item)._data

        self._open_raw(raw)

    def _open_sysex(self, filename: str | None, raw: bytes | None = None) -> None:
        if raw is None:
            with open(filename, 'rb') as sysexfile:
                raw = sysexfile.read()

        checksum = 0
        data = b''
        for chunk in raw[1:-1].split(b'\xf7\xf0'):
            block_type = chunk[6]
            if block_type == SYSEX_BLOCK_INIT:
                data = b''
            elif block_type == SYSEX_BLOCK_DATA:
                raw_chunk = utils.seven_to_eight(chunk[17:])
                data += raw_chunk
                checksum = binascii.crc32(raw_chunk, checksum) & 0xffffffff
            elif block_type == SYSEX_BLOCK_CRC:
                if checksum != utils.nibbles_to_bytes(chunk[17:]):
                    raise slmkiii.errors.ErrorInvalidChecksum()
        self._open_raw(data)

    def _open_raw(self, data: bytes) -> None:
        ofst = HEADER_SIZE
        self._data = data
        self._header = self._data[:ofst]
        self.name = self._header[4:17].rstrip(b'\0').rstrip().decode('ascii', errors='replace')
        self._body = self._data[ofst:]

        for sdata in sections:
            items = []
            for _ in range(sdata['items']):
                items.append(sdata['class'](data[ofst:ofst+CONTROL_BLOCK_SIZE]))
                ofst += CONTROL_BLOCK_SIZE
            setattr(self, sdata['name'], items)

    def patch_defaults(self, data: dict) -> dict:
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
                data[section] += [copy.deepcopy(defaults[section]) for _ in range(needed)]
            new_structure = []
            for item in data[section]:
                new_item = copy.deepcopy(defaults[section])
                new_item.update(item)
                new_structure.append(new_item)
            data[section] = new_structure
        for k in ('name', 'version'):
            if k not in data:
                data[k] = defaults[k]
        return data

    def _rebuild(self) -> None:
        """Rebuild raw _data from current control attributes."""
        name_bytes = self.name.encode('ascii', errors='replace')[:16].ljust(16, b'\0')
        raw = struct.pack('>4s16s', TEMPLATE_HEADER_MAGIC, name_bytes)
        for sdata in sections:
            for item in getattr(self, sdata['name']):
                d = item.export_dict()
                rebuilt = sdata['class'](d)
                raw += rebuilt._data
        self._data = raw

    def save(self, filename: str, minify: bool = False, overwrite: bool = True) -> None:
        dirname = os.path.dirname(filename)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        ftype = utils.file_type(filename)
        if overwrite is False:
            if os.path.exists(filename):
                raise slmkiii.errors.ErrorFileExists(filename)
        if ftype == 'json':
            self.export_json(filename, minify)
        elif ftype == 'sysex':
            self.export_sysex(filename)

    def export_sysex(self, filename: str | None = None) -> bytes:
        self._rebuild()

        header = struct.pack('>7B', *SYSEX_HEADER)
        data = header + struct.pack(
            '>B2L4B', SYSEX_BLOCK_INIT, 0, 0,
            SYSEX_BLOCK_DATA, 0, 1, SYSEX_END,
        )

        block = 0
        checksum = 0
        while (block * 256) <= len(self._data):
            chunk = self._data[block * 256:(block + 1) * 256]
            checksum = binascii.crc32(chunk, checksum) & 0xffffffff
            encoded_data = utils.eight_to_seven(chunk)
            data += header
            data += struct.pack(
                '>B2L2B{}sB'.format(len(encoded_data)),
                SYSEX_BLOCK_DATA, 0, block + 1,
                SYSEX_BLOCK_DATA, 0, encoded_data, SYSEX_END,
            )
            block += 1

        data += header
        encoded_checksum = utils.bytes_to_nibbles(checksum)
        data += struct.pack(
            '>B2L2B8sB', SYSEX_BLOCK_CRC, 0, 15,
            SYSEX_BLOCK_DATA, 0, encoded_checksum, SYSEX_END,
        )

        if filename is not None:
            with open(filename, 'wb') as sysexfile:
                sysexfile.write(data)

        return data

    def export_json(self, filename: str | None = None,
                    minify: bool = False) -> dict:
        data = {x['name']: [] for x in sections}

        for sdata in sections:
            items = getattr(self, sdata['name'])
            for item in items:
                data[sdata['name']].append(item.export_dict())

        data['name'] = self.name
        data['version'] = TEMPLATE_VERSION
        data['-NOTES-'] = (
            '*_param_name fields are for reference and are not editable',
            'Many fields are used/unused based on behavior or message_type',
        )

        if self.metadata:
            data['metadata'] = self.metadata

        if minify:
            for sdata in sections:
                new_structure = []
                for item in data[sdata['name']]:
                    minified = {}
                    for key, value in item.items():
                        if key[-11:] in ('_param_name', 'method_name'):
                            continue
                        if key in defaults[sdata['name']] and defaults[sdata['name']][key] == value:
                            continue
                        minified[key] = value
                    new_structure.append(minified)
                data[sdata['name']] = new_structure

        if filename is not None:
            with open(filename, 'w') as jsonfile:
                json.dump(data,
                          jsonfile,
                          indent=4,
                          sort_keys=True,
                          separators=(',', ': '))

        return data

    # ---- Bulk operations ----

    def all_controls(self) -> list:
        controls = []
        for sdata in sections:
            controls.extend(getattr(self, sdata['name']))
        return controls

    def find_controls(self, **kwargs) -> list:
        results = []
        for control in self.all_controls():
            match = True
            for key, value in kwargs.items():
                if getattr(control, key, None) != value:
                    match = False
                    break
            if match:
                results.append(control)
        return results

    def enable_all(self, section: str | None = None) -> None:
        for control in self._controls_for_section(section):
            control.enabled = True

    def disable_all(self, section: str | None = None) -> None:
        for control in self._controls_for_section(section):
            control.enabled = False

    def reset_all(self, section: str | None = None) -> None:
        target_sections = sections
        if section is not None:
            target_sections = [s for s in sections if s['name'] == section]
        for sdata in target_sections:
            new_controls = []
            for _ in range(sdata['items']):
                new_controls.append(sdata['class'](copy.deepcopy(defaults[sdata['name']])))
            setattr(self, sdata['name'], new_controls)

    def _controls_for_section(self, section: str | None) -> list:
        if section is None:
            return self.all_controls()
        return getattr(self, section, [])

    # ---- Validation ----

    def validate(self) -> list[str]:
        messages = []
        cc_assignments = {}

        for sdata in sections:
            section_name = sdata['name']
            for i, control in enumerate(getattr(self, section_name)):
                if not control.enabled:
                    continue

                label = f'{section_name} {i}'

                try:
                    type_name = control.message_type_name
                except (IndexError, KeyError):
                    messages.append(f'{label}: unknown message_type {control.message_type}')
                    continue

                channel = control.channel
                if channel != 'default' and not (1 <= channel <= 16):
                    messages.append(f'{label}: channel {channel} out of range 1-16')

                if type_name == 'CC':
                    cc_num = self._cc_number(control)
                    if cc_num is not None:
                        if not (0 <= cc_num <= 127):
                            messages.append(f'{label}: CC number {cc_num} out of range 0-127')
                        else:
                            key = (channel, cc_num)
                            if key in cc_assignments:
                                messages.append(
                                    f'{label}: duplicate CC {cc_num} on channel {channel} '
                                    f'(also assigned to {cc_assignments[key]})')
                            else:
                                cc_assignments[key] = label

                if type_name == 'Note':
                    note_num = self._note_number(control)
                    if note_num is not None and not (0 <= note_num <= 127):
                        messages.append(f'{label}: note number {note_num} out of range 0-127')

        return messages

    @staticmethod
    def _cc_number(control) -> int | None:
        if isinstance(control, Button):
            return control.fourth_param
        if isinstance(control, Knob):
            return control.first_param
        if isinstance(control, Fader):
            return control.second_param
        return None

    @staticmethod
    def _note_number(control) -> int | None:
        if isinstance(control, Button):
            return control.third_param
        return None

    # ---- Dunder methods ----

    def __repr__(self) -> str:
        parts = [f"<Template {self.name!r}"]
        for sdata in sections:
            items = getattr(self, sdata['name'])
            parts.append(f"{sdata['name']}={len(items)}")
        return ' '.join(parts) + '>'

    def __str__(self) -> str:
        return repr(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Template):
            return NotImplemented
        self._rebuild()
        other._rebuild()
        return self._data == other._data

    def __len__(self) -> int:
        return sum(len(getattr(self, s['name'])) for s in sections)

    def __iter__(self):
        for sdata in sections:
            yield from getattr(self, sdata['name'])

    def __getitem__(self, key: str) -> list:
        if not isinstance(key, str):
            raise TypeError(f"Template indices must be strings, not {type(key).__name__}")
        for sdata in sections:
            if sdata['name'] == key:
                return getattr(self, key)
        raise KeyError(key)

    def clone(self) -> Template:
        """Return a deep copy of this template."""
        return copy.deepcopy(self)

    def summary(self) -> str:
        """Return a human-readable summary of the template."""
        lines = [f"Template: {self.name or '(unnamed)'}"]
        for sdata in sections:
            items = getattr(self, sdata['name'])
            enabled = [c for c in items if c.enabled]
            lines.append(f"  {sdata['name']}: {len(enabled)}/{len(items)} enabled")
            for c in enabled:
                ch = f' ch={c.channel}' if hasattr(c, '_channel') else ''
                lines.append(f"    {c.name!r} {c.message_type_name}{ch}")
        return '\n'.join(lines)
