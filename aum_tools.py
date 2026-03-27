"""Tools for reading and writing AUM (Kymatica) session and MIDI mapping files.

AUM stores its data as NSKeyedArchiver binary property lists. This module
decodes and encodes these formats, enabling programmatic control of MIDI
mappings and session topology discovery.

File formats:
- .aum_midimap — MIDI CC/Note mappings for a plugin or transport
- .aumproj — Full session state (channels, plugins, routing, mappings)
"""
from __future__ import annotations

import plistlib
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# NSKeyedArchiver decoding helpers
# ---------------------------------------------------------------------------

# NSKeyedArchiver always stores '$null' at $objects[0]
_NS_NULL = '$null'


def _resolve_uid(objects: list, val):
    """Recursively resolve NSKeyedArchiver UID references to Python objects."""
    if isinstance(val, plistlib.UID):
        return _resolve_uid(objects, objects[val])
    elif isinstance(val, dict):
        if 'NS.keys' in val and 'NS.objects' in val:
            keys = [_resolve_uid(objects, k) for k in val['NS.keys']]
            vals = [_resolve_uid(objects, v) for v in val['NS.objects']]
            return dict(zip(keys, vals))
        elif 'NS.objects' in val:
            return [_resolve_uid(objects, o) for o in val['NS.objects']]
        elif '$classname' in val or '$classes' in val:
            return None
        else:
            result = {}
            for k, v in val.items():
                if k.startswith('$'):
                    continue
                result[k] = _resolve_uid(objects, v)
            return result
    elif isinstance(val, list):
        return [_resolve_uid(objects, item) for item in val]
    else:
        return val


def _decode_keyed_archiver(data: bytes) -> dict:
    """Decode an NSKeyedArchiver binary plist to a Python dict."""
    plist = plistlib.loads(data)
    if plist.get('$archiver') != 'NSKeyedArchiver':
        raise ValueError('Not an NSKeyedArchiver plist')
    objects = plist['$objects']
    root_uid = plist['$top']['root']
    return _resolve_uid(objects, root_uid)


# ---------------------------------------------------------------------------
# MIDI mapping file types
# ---------------------------------------------------------------------------

# MIDI message types used in AUM's specState
MSG_TYPE_NOTE = 0
MSG_TYPE_CC = 1
MSG_TYPE_PROGRAM_CHANGE = 2
MSG_TYPE_PITCH_BEND = 3
MSG_TYPE_CHANNEL_PRESSURE = 4


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
    msg_type: int = MSG_TYPE_CC


# ---------------------------------------------------------------------------
# MIDI mapping file reader
# ---------------------------------------------------------------------------

def read_aum_midimap(path: str | Path) -> dict:
    """Read an AUM MIDI mapping file and return a clean Python dict.

    Returns:
        Dict with keys:
        - 'collection_name': str (e.g., "Transport" or plugin identifier)
        - 'mappings': list[AumMidiMapping] — all parameter mappings
        - 'raw': dict — the full decoded plist for inspection
    """
    path = Path(path)
    with open(path, 'rb') as f:
        data = f.read()

    decoded = _decode_keyed_archiver(data)

    collection_name = decoded.get('_collection_map_name', '')
    mappings = []

    for key, value in decoded.items():
        if key.startswith('_') or not isinstance(value, dict):
            continue
        spec = value.get('specState')
        if spec is None:
            continue
        mappings.append(AumMidiMapping(
            parameter_name=key,
            cc_number=spec.get('data1', 0),
            channel=value.get('channel', 0),
            min_value=value.get('min', 0.0),
            max_value=value.get('max', 1.0),
            enabled=spec.get('enabled', False),
            auto_toggle=value.get('autoToggle', False),
            msg_type=spec.get('type', MSG_TYPE_CC),
        ))

    return {
        'collection_name': collection_name,
        'mappings': mappings,
        'raw': decoded,
    }


# ---------------------------------------------------------------------------
# NSKeyedArchiver encoding helpers
# ---------------------------------------------------------------------------

class _ArchiverBuilder:
    """Builds an NSKeyedArchiver plist from Python objects."""

    def __init__(self):
        self._objects = ['$null']  # index 0 is always $null
        self._class_cache = {}

    def _add_object(self, obj) -> plistlib.UID:
        idx = len(self._objects)
        self._objects.append(obj)
        return plistlib.UID(idx)

    def _get_class_uid(self, classname: str,
                       classes: list[str] | None = None) -> plistlib.UID:
        if classname in self._class_cache:
            return self._class_cache[classname]
        if classes is None:
            classes = [classname, 'NSObject']
        uid = self._add_object({
            '$classes': classes,
            '$classname': classname,
        })
        self._class_cache[classname] = uid
        return uid

    def encode_value(self, val) -> plistlib.UID:
        """Encode a Python value as an NSKeyedArchiver object."""
        if val is None:
            return plistlib.UID(0)  # $null
        elif isinstance(val, bool):
            return self._add_object(val)
        elif isinstance(val, (int, float)):
            return self._add_object(val)
        elif isinstance(val, str):
            return self._add_object(val)
        elif isinstance(val, dict):
            return self._encode_dict(val)
        elif isinstance(val, list):
            return self._encode_array(val)
        else:
            return self._add_object(val)

    def _encode_dict(self, d: dict) -> plistlib.UID:
        key_uids = []
        val_uids = []
        for k, v in d.items():
            key_uids.append(self.encode_value(k))
            val_uids.append(self.encode_value(v))

        obj = {
            'NS.keys': key_uids,
            'NS.objects': val_uids,
            '$class': self._get_class_uid(
                'NSMutableDictionary',
                ['NSMutableDictionary', 'NSDictionary', 'NSObject']),
        }
        return self._add_object(obj)

    def _encode_array(self, arr: list) -> plistlib.UID:
        item_uids = [self.encode_value(v) for v in arr]
        obj = {
            'NS.objects': item_uids,
            '$class': self._get_class_uid(
                'NSMutableArray',
                ['NSMutableArray', 'NSArray', 'NSObject']),
        }
        return self._add_object(obj)

    def build(self, root) -> bytes:
        root_uid = self.encode_value(root)
        plist = {
            '$archiver': 'NSKeyedArchiver',
            '$version': 100000,
            '$top': {'root': root_uid},
            '$objects': self._objects,
        }
        return plistlib.dumps(plist, fmt=plistlib.FMT_BINARY)


# ---------------------------------------------------------------------------
# MIDI mapping file writer
# ---------------------------------------------------------------------------

def write_aum_midimap(collection_name: str,
                      mappings: list[AumMidiMapping],
                      path: str | Path) -> None:
    """Write an AUM MIDI mapping file.

    Args:
        collection_name: The collection identifier (e.g., "Transport",
                         or "PluginName.AU-<hex>").
        mappings: List of AumMidiMapping objects.
        path: Output file path (.aum_midimap).
    """
    data = generate_midimap_bytes(collection_name, mappings)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)


def generate_midimap_bytes(collection_name: str,
                           mappings: list[AumMidiMapping]) -> bytes:
    """Generate AUM MIDI mapping file bytes.

    Returns:
        Binary plist data suitable for writing to a .aum_midimap file.
    """
    root = {
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

    builder = _ArchiverBuilder()
    return builder.build(root)


# ---------------------------------------------------------------------------
# Session file reader
# ---------------------------------------------------------------------------

@dataclass
class AumPlugin:
    """An AUv3 plugin loaded in an AUM channel."""
    component_name: str          # e.g., "Unfiltered Audio: UA Battalion"
    au_type: str                 # FourCC: "aumu", "aufx", "aumf"
    au_subtype: str              # FourCC: plugin-specific
    au_manufacturer: str         # FourCC: e.g., "Moog", "appl"
    node_type: str = ''          # "AUXNodeDescription", "MIDIBusNodeDescription", etc.


@dataclass
class AumChannel:
    """A channel strip in an AUM session."""
    index: int
    title: str
    channel_type: str            # "AUMAudioStrip" or "AUMMIDIStrip"
    fader_level: float = 1.0
    muted: bool = False
    soloed: bool = False
    plugins: list[AumPlugin] = field(default_factory=list)


@dataclass
class AumSession:
    """Parsed AUM session data."""
    title: str
    version: int
    sample_rate: float
    channels: list[AumChannel] = field(default_factory=list)
    tempo: float = 120.0


def _decode_fourcc_le(raw: bytes, offset: int) -> str:
    """Decode a 4-byte little-endian FourCC string."""
    return raw[offset:offset + 4][::-1].decode('ascii', errors='replace')


def _deref_uid(objects: list, val):
    """Resolve UID but preserve dict structure (don't recurse into all dicts)."""
    if isinstance(val, plistlib.UID):
        return objects[val]
    return val


def read_aum_session(path: str | Path) -> AumSession:
    """Read an AUM session file and extract channel/plugin topology.

    Args:
        path: Path to .aumproj file.

    Returns:
        AumSession with channels and their plugins.
    """
    path = Path(path)
    with open(path, 'rb') as f:
        plist = plistlib.load(f)

    objects = plist['$objects']
    root_uid = plist['$top']['root']
    root = objects[root_uid]

    # Extract basic session info
    title_uid = root.get('title')
    title = _deref_uid(objects, title_uid) if title_uid else ''
    if title is None or isinstance(title, dict) or title == _NS_NULL:
        title = ''

    version = root.get('version', 0)
    sample_rate = root.get('sampleRate', 48000)

    # Extract tempo from transportClockState
    tempo = 120.0
    transport_uid = root.get('transportClockState')
    if transport_uid:
        transport = _deref_uid(objects, transport_uid)
        if isinstance(transport, dict) and 'NS.keys' in transport:
            keys = [_deref_uid(objects, k) for k in transport['NS.keys']]
            vals = [_deref_uid(objects, v) for v in transport['NS.objects']]
            transport_dict = dict(zip(keys, vals))
            tempo = transport_dict.get('clockTempo', 120.0)

    # Parse channels
    channels_uid = root.get('channels')
    channels_arr = _deref_uid(objects, channels_uid) if channels_uid else None
    channels = []

    if channels_arr and isinstance(channels_arr, dict) and 'NS.objects' in channels_arr:
        for ch_uid in channels_arr['NS.objects']:
            ch_obj = _deref_uid(objects, ch_uid)
            if not isinstance(ch_obj, dict):
                continue

            # Determine channel type from $class
            class_uid = ch_obj.get('$class')
            class_obj = _deref_uid(objects, class_uid) if class_uid else {}
            channel_type = class_obj.get('$classname', '') if isinstance(class_obj, dict) else ''

            ch_title_uid = ch_obj.get('title')
            ch_title = _deref_uid(objects, ch_title_uid) if ch_title_uid else ''
            if ch_title is None or isinstance(ch_title, dict) or ch_title == _NS_NULL:
                ch_title = ''

            channel = AumChannel(
                index=ch_obj.get('index', 0),
                title=ch_title,
                channel_type=channel_type,
                fader_level=ch_obj.get('faderLevel', 1.0),
                muted=ch_obj.get('muted', False),
                soloed=ch_obj.get('soloed', False),
            )
            channels.append(channel)

    # Parse nodeArchives to discover plugins per channel
    node_archives_uid = root.get('nodeArchives')
    if node_archives_uid:
        node_archives = _deref_uid(objects, node_archives_uid)
        if isinstance(node_archives, dict) and 'NS.objects' in node_archives:
            channel_node_lists = node_archives['NS.objects']
            for ch_idx, node_list_uid in enumerate(channel_node_lists):
                node_list = _deref_uid(objects, node_list_uid)
                if not isinstance(node_list, dict) or 'NS.objects' not in node_list:
                    continue

                plugins = []
                for node_uid in node_list['NS.objects']:
                    node = _deref_uid(objects, node_uid)
                    if not isinstance(node, dict):
                        continue

                    desc_class_uid = node.get('archiveDescClass')
                    desc_class = _deref_uid(objects, desc_class_uid) if desc_class_uid else ''
                    if desc_class is None or isinstance(desc_class, dict):
                        desc_class = ''

                    comp_name_uid = node.get('componentName')
                    comp_name = _deref_uid(objects, comp_name_uid) if comp_name_uid else ''
                    if comp_name is None or isinstance(comp_name, dict):
                        comp_name = ''

                    au_desc = node.get('audioComponentDescription')
                    au_type = au_subtype = au_manufacturer = ''
                    if isinstance(au_desc, bytes) and len(au_desc) >= 12:
                        au_type = _decode_fourcc_le(au_desc, 0)
                        au_subtype = _decode_fourcc_le(au_desc, 4)
                        au_manufacturer = _decode_fourcc_le(au_desc, 8)

                    if comp_name or au_type:
                        plugins.append(AumPlugin(
                            component_name=comp_name,
                            au_type=au_type,
                            au_subtype=au_subtype,
                            au_manufacturer=au_manufacturer,
                            node_type=desc_class,
                        ))

                # Match plugins to channels by index
                if ch_idx < len(channels):
                    channels[ch_idx].plugins = plugins

    return AumSession(
        title=title,
        version=version,
        sample_rate=sample_rate,
        channels=channels,
        tempo=tempo,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description='AUM file analysis tools')
    sub = parser.add_subparsers(dest='command')

    # inspect-mapping
    p_map = sub.add_parser('inspect-mapping', help='Decode and display an AUM MIDI mapping file')
    p_map.add_argument('path', help='Path to .aum_midimap file')

    # inspect-session
    p_sess = sub.add_parser('inspect-session', help='Decode and display an AUM session file')
    p_sess.add_argument('path', help='Path to .aumproj file')

    args = parser.parse_args()

    if args.command == 'inspect-mapping':
        result = read_aum_midimap(args.path)
        print(f"Collection: {result['collection_name']}")
        print(f"Parameters: {len(result['mappings'])}")
        print()
        for m in sorted(result['mappings'], key=lambda x: x.parameter_name):
            status = 'ON ' if m.enabled else 'off'
            msg = 'CC' if m.msg_type == MSG_TYPE_CC else f'type{m.msg_type}'
            print(f"  [{status}] {m.parameter_name:<30s} {msg}{m.cc_number:<4d} ch{m.channel + 1}")

    elif args.command == 'inspect-session':
        session = read_aum_session(args.path)
        print(f"Session: {session.title}")
        print(f"Version: {session.version}  Sample Rate: {session.sample_rate}  Tempo: {session.tempo}")
        print(f"Channels: {len(session.channels)}")
        print()
        for ch in session.channels:
            mute_str = ' [MUTED]' if ch.muted else ''
            solo_str = ' [SOLO]' if ch.soloed else ''
            title = ch.title or '(untitled)'
            print(f"  Ch {ch.index}: {title} ({ch.channel_type})"
                  f" level={ch.fader_level:.2f}{mute_str}{solo_str}")
            for p in ch.plugins:
                au_id = f"{p.au_type}/{p.au_subtype}/{p.au_manufacturer}" if p.au_type else p.node_type
                print(f"    └─ {p.component_name or p.node_type}  [{au_id}]")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
