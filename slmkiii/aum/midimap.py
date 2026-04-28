"""Reader/writer for AUM `.aum_midimap` files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slmkiii.aum.archiver import ArchiverBuilder, decode_keyed_archiver
from slmkiii.aum.codec import AumMsgType


@dataclass
class AumMidiMapping:
    """A single MIDI CC/Note mapping for an AUM parameter."""
    parameter_name: str
    cc_number: int = 0
    channel: int = 0       # 0-indexed
    min_value: float = 0.0
    max_value: float = 1.0
    enabled: bool = True
    auto_toggle: bool = False
    msg_type: int = int(AumMsgType.CC)


def read_aum_midimap(path: str | Path) -> dict:
    """Read an AUM MIDI mapping file and return a clean Python dict.

    Returns:
        Dict with keys:
        - 'collection_name': str (e.g., "Transport" or plugin identifier)
        - 'mappings': list[AumMidiMapping] — all parameter mappings
        - 'raw': dict — the full decoded plist for inspection
    """
    path = Path(path)
    data = path.read_bytes()
    decoded = decode_keyed_archiver(data)

    collection_name = decoded.get('_collection_map_name', '')
    mappings: list[AumMidiMapping] = []

    def visit(node: dict) -> None:
        # AUM channel-level files have nested container dicts (slot0, slot1,
        # 'drumProtoParams', etc.) and leaf dicts with specState. Walk all
        # containers, collect every leaf.
        for key, value in node.items():
            if key.startswith('_') or not isinstance(value, dict):
                continue
            if 'specState' in value:
                spec = value['specState']
                mappings.append(AumMidiMapping(
                    parameter_name=key,
                    cc_number=spec.get('data1', 0),
                    channel=value.get('channel', 0),
                    min_value=value.get('min', 0.0),
                    max_value=value.get('max', 1.0),
                    enabled=spec.get('enabled', False),
                    auto_toggle=value.get('autoToggle', False),
                    msg_type=spec.get('type', int(AumMsgType.CC)),
                ))
            else:
                visit(value)

    visit(decoded)
    return {
        'collection_name': collection_name,
        'mappings': mappings,
        'raw': decoded,
    }


def generate_midimap_bytes(collection_name: str,
                           mappings: list[AumMidiMapping]) -> bytes:
    """Generate AUM MIDI mapping file bytes (a binary NSKeyedArchiver plist)."""
    root: dict = {
        '_collection_map_name': collection_name,
        '_collection_editor_states': [],
    }
    for m in mappings:
        root[m.parameter_name] = {
            'min': m.min_value,
            'max': m.max_value,
            'channel': m.channel,
            'autoToggle': m.auto_toggle,
            'specState': {
                'enabled': m.enabled,
                'data1': m.cc_number,
                'type': m.msg_type,
            },
        }
    return ArchiverBuilder().build(root)


def write_aum_midimap(collection_name: str,
                      mappings: list[AumMidiMapping],
                      path: str | Path) -> None:
    """Write an AUM MIDI mapping file."""
    data = generate_midimap_bytes(collection_name, mappings)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
