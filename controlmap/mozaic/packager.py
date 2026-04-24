"""Pack a Mozaic .moz ASCII script into a .mozaic NSKeyedArchiver plist.

The .mozaic format is an NSKeyedArchiver binary plist whose root object is an
NSMutableDictionary of fixed keys. The only keys that matter for loading a
script are FILENAME and CODE (NSMutableData wrapping UTF-8 source). The rest
are UI state (knob labels, pad colours, etc.) that Mozaic will regenerate on
first run - but they must be present for the plist to validate, so we fill
defaults.

This format was reverse-engineered from a real Patchstorage .mozaic sample
(Mutator v3.6). See bead slmkiii-adw.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

from aum_tools import ArchiverBuilder


class _MozaicBuilder(ArchiverBuilder):
    """Extends the AUM ArchiverBuilder with NSMutableData wrapping for CODE."""

    def encode_ns_mutable_data(self, data: bytes) -> plistlib.UID:
        cls = self._get_class_uid(
            'NSMutableData', ['NSMutableData', 'NSData', 'NSObject'])
        return self._add_object({'NS.data': data, '$class': cls})


def build_mozaic(script_text: str, filename: str) -> bytes:
    """Build a .mozaic file from a Mozaic ASCII script.

    Args:
        script_text: The full .moz script source (UTF-8).
        filename: Display name for the script inside Mozaic.

    Returns:
        Binary plist bytes suitable for writing to a .mozaic file.
    """
    b = _MozaicBuilder()

    # NSMutableData wrapping is special - the rest of the dict is straightforward.
    code_uid = b.encode_ns_mutable_data(script_text.encode('utf-8'))

    root: dict = {}
    root['FILENAME'] = filename
    root['GUI'] = bytes(40)
    root['SCALE'] = 1000
    for i in range(22):
        root[f'KNOBLABEL{i}'] = str(i) if i else ' '
        root[f'KNOBVALUE{i}'] = 0.0
    root['KNOBTITLE'] = ' '
    for i in range(16):
        root[f'PADLABEL{i}'] = ' '
        root[f'PADCOLOR{i}'] = 0
    root['PADTITLE'] = ' '
    for i in range(8):
        root[f'AUVALUE{i}'] = 0.0
    root['XYTITLE'] = 'XY Pad'
    root['XVALUE'] = 64.0
    root['YVALUE'] = 64.0

    # Build the root dict by hand so CODE can point directly at our
    # pre-encoded NSMutableData UID instead of being re-encoded.
    key_uids = [b.encode_value('CODE')] + [b.encode_value(k) for k in root.keys()]
    val_uids = [code_uid] + [b.encode_value(v) for v in root.values()]
    cls_uid = b._get_class_uid(
        'NSMutableDictionary',
        ['NSMutableDictionary', 'NSDictionary', 'NSObject'])
    root_uid = b._add_object({
        'NS.keys': key_uids,
        'NS.objects': val_uids,
        '$class': cls_uid,
    })

    plist = {
        '$archiver': 'NSKeyedArchiver',
        '$version': 100000,
        '$top': {'root': root_uid},
        '$objects': b._objects,
    }
    return plistlib.dumps(plist, fmt=plistlib.FMT_BINARY)


def pack_moz_file(moz_path: str | Path, mozaic_path: str | Path,
                  filename: str | None = None) -> None:
    """Read a .moz script and write a .mozaic file."""
    moz_path = Path(moz_path)
    mozaic_path = Path(mozaic_path)
    if filename is None:
        filename = moz_path.stem
    text = moz_path.read_text(encoding='utf-8')
    mozaic_path.write_bytes(build_mozaic(text, filename))
