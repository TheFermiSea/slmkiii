"""Reader for AUM `.aumproj` session files (channel/plugin topology)."""

from __future__ import annotations

import plistlib
from dataclasses import dataclass, field
from pathlib import Path

from slmkiii.aum.archiver import _NS_NULL, deref_uid


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


def _stringy(val) -> str:
    """Reduce a deref'd UID value to a plain str (handling $null and dicts)."""
    if val is None or isinstance(val, dict) or val == _NS_NULL:
        return ''
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

    title = _stringy(deref_uid(objects, root.get('title')))
    version = root.get('version', 0)
    sample_rate = root.get('sampleRate', 48000)

    # Tempo lives inside transportClockState (an NSDictionary)
    tempo = 120.0
    transport = deref_uid(objects, root.get('transportClockState'))
    if isinstance(transport, dict) and 'NS.keys' in transport:
        keys = [deref_uid(objects, k) for k in transport['NS.keys']]
        vals = [deref_uid(objects, v) for v in transport['NS.objects']]
        tempo = dict(zip(keys, vals)).get('clockTempo', 120.0)

    channels: list[AumChannel] = []
    channels_arr = deref_uid(objects, root.get('channels'))
    if isinstance(channels_arr, dict) and 'NS.objects' in channels_arr:
        for ch_uid in channels_arr['NS.objects']:
            ch_obj = deref_uid(objects, ch_uid)
            if not isinstance(ch_obj, dict):
                continue
            class_obj = deref_uid(objects, ch_obj.get('$class')) or {}
            channel_type = class_obj.get('$classname', '') if isinstance(class_obj, dict) else ''
            channels.append(AumChannel(
                index=ch_obj.get('index', 0),
                title=_stringy(deref_uid(objects, ch_obj.get('title'))),
                channel_type=channel_type,
                fader_level=ch_obj.get('faderLevel', 1.0),
                muted=ch_obj.get('muted', False),
                soloed=ch_obj.get('soloed', False),
            ))

    # nodeArchives: per-channel list of plugin nodes
    node_archives = deref_uid(objects, root.get('nodeArchives'))
    if isinstance(node_archives, dict) and 'NS.objects' in node_archives:
        for ch_idx, node_list_uid in enumerate(node_archives['NS.objects']):
            node_list = deref_uid(objects, node_list_uid)
            if not isinstance(node_list, dict) or 'NS.objects' not in node_list:
                continue
            plugins: list[AumPlugin] = []
            for node_uid in node_list['NS.objects']:
                node = deref_uid(objects, node_uid)
                if not isinstance(node, dict):
                    continue
                desc_class = _stringy(deref_uid(objects, node.get('archiveDescClass')))
                comp_name = _stringy(deref_uid(objects, node.get('componentName')))
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
            if ch_idx < len(channels):
                channels[ch_idx].plugins = plugins

    return AumSession(
        title=title,
        version=version,
        sample_rate=sample_rate,
        channels=channels,
        tempo=tempo,
    )
