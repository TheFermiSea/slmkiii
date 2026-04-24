"""Pack a Mozaic .moz ASCII script into a .mozaic NSKeyedArchiver plist.

The .mozaic format is an NSKeyedArchiver binary plist whose root is an
NSMutableDictionary of fixed keys. The only keys that matter for loading a
script are FILENAME and CODE (NSMutableData wrapping UTF-8 source). The rest
are UI state (knob labels, pad colours, etc.) that Mozaic will regenerate on
first run — but they must be present for the plist to validate, so we fill
defaults.

Format reverse-engineered from a real Patchstorage .mozaic sample
(Mutator v3.6). See bead slmkiii-adw.
"""

from __future__ import annotations

from pathlib import Path

from aum_tools import ArchiverBuilder


def build_mozaic(script_text: str, filename: str) -> bytes:
    """Build a .mozaic file from a Mozaic ASCII script."""
    b = ArchiverBuilder()

    root: dict = {
        # encode_value() passes UIDs through so CODE points at the
        # pre-encoded NSMutableData object instead of being re-encoded.
        'CODE': b.encode_ns_mutable_data(script_text.encode('utf-8')),
        'FILENAME': filename,
        'GUI': bytes(40),
        'SCALE': 1000,
    }
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

    return b.build(root)


def pack_moz_file(moz_path: str | Path, mozaic_path: str | Path,
                  filename: str | None = None) -> None:
    """Read a .moz script and write a .mozaic file."""
    moz_path = Path(moz_path)
    mozaic_path = Path(mozaic_path)
    if filename is None:
        filename = moz_path.stem
    text = moz_path.read_text(encoding='utf-8')
    mozaic_path.write_bytes(build_mozaic(text, filename))
