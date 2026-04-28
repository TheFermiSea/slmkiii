"""Extract plugin parameters from AUM MIDI mapping files."""
from __future__ import annotations

import json
import re
from pathlib import Path

from aum_tools import decode_keyed_archiver


def _infer_param_type(name: str) -> str:
    """Infer parameter type from its name."""
    lower = name.lower()
    if any(t in lower for t in ('mute', 'solo', 'bypass', 'enabled',
                                 'mono', 'legato', 'hold', 'sync',
                                 'bipolar', 'reset')):
        return 'toggle'
    if 'trigger' in lower:
        return 'trigger'
    if any(t in lower for t in ('mode', 'shape', 'bus', 'variation',
                                 'choke', 'outputbus')):
        return 'discrete'
    return 'continuous'


def _make_display_name(param_name: str, max_len: int = 9) -> str:
    """Generate a short display name from a parameter name.

    Strips common prefixes like "drum1" and abbreviates.
    """
    # Remove drumN prefix
    name = re.sub(r'^drum(\d+)', r'D\1 ', param_name)
    # Remove common verbose parts
    name = name.replace('params.', '').replace('modparams.', '')
    # Capitalize first letter
    if name and name[0].islower():
        name = name[0].upper() + name[1:]
    # Truncate
    return name[:max_len]


def _infer_group(path: str) -> str:
    """Infer a semantic group from the parameter path."""
    parts = path.split('.')
    if len(parts) < 2:
        return 'root'

    # drumProtoParams.drum1params.drum1modparams.drum1cutoffenv1 → drum1.mod
    # drumProtoParams.drum1params.drum1cutoff → drum1
    # drumProtoParams.effectParams.* → effects
    # drumProtoParams.performParams.* → perform
    # drumProtoParams.sendAParams.* → sendA
    # drumProtoParams.seqChan1params.* → seq1

    for part in parts:
        m = re.match(r'drum(\d+)params', part)
        if m:
            drum_num = m.group(1)
            if 'modparams' in path:
                return f'drum{drum_num}.mod'
            return f'drum{drum_num}'

        if part == 'effectParams':
            return 'effects'
        if part == 'performParams':
            return 'perform'
        m = re.match(r'send([AB])Params', part)
        if m:
            return f'send{m.group(1)}'
        m = re.match(r'seqChan(\d+)params', part)
        if m:
            return f'seq{m.group(1)}'
        if part == 'sequencerParams':
            return 'sequencer'

    return 'root'


def _walk_params(d: dict) -> list[dict]:
    """Recursively walk a decoded AUM mapping dict to find all leaf parameters.

    AUM encodes full parameter paths as dict keys (e.g.,
    'drumProtoParams.drum1params.drum1cutoff'), so no prefix
    accumulation is needed.
    """
    params = []
    for key, value in d.items():
        if key.startswith('_'):
            continue
        if not isinstance(value, dict):
            continue

        if 'specState' in value:
            param_name = key.split('.')[-1] if '.' in key else key
            params.append({
                'path': key,
                'display_name': _make_display_name(param_name),
                'param_type': _infer_param_type(param_name),
            })
        else:
            params.extend(_walk_params(value))

    return params


def harvest_from_aum_midimap(
    input_path: str | Path,
    plugin_id: str,
    plugin_name: str = '',
    slot_name: str = '',
) -> dict:
    """Extract all parameters from an AUM MIDI mapping file.

    Handles nested sub-collections (like Battalion's drumProtoParams).
    For Channel-level mappings with multiple slots, use slot_name to
    select a specific plugin (e.g., "Animoog Z.AU-..."). If empty,
    harvests from the slot with the most parameters.

    Returns:
        Dict suitable for writing as a plugin parameter JSON file.
    """
    input_path = Path(input_path)
    with open(input_path, 'rb') as f:
        data = f.read()

    decoded = decode_keyed_archiver(data)

    # Collect params per slot to handle multi-slot Channel mappings
    slots: dict[str, dict] = {}  # slot_key -> {au_id, params}
    top_level_params = []

    for key, value in decoded.items():
        if key.startswith('slot') and isinstance(value, dict):
            collection_name = value.get('_collection_map_name', '')
            slot_params = _walk_params(value)
            slots[key] = {
                'au_identifier': collection_name if '.AU-' in collection_name else '',
                'params': slot_params,
                'collection_name': collection_name,
            }
        elif key.startswith('_'):
            continue
        elif isinstance(value, dict):
            if 'specState' in value:
                top_level_params.append({
                    'path': key,
                    'display_name': _make_display_name(key),
                    'param_type': _infer_param_type(key),
                })
            else:
                top_level_params.extend(_walk_params(value))

    # Select the target slot
    all_params = []
    au_identifier = ''

    if slot_name:
        # Find slot matching the requested name
        for slot_data in slots.values():
            if slot_name in slot_data['collection_name']:
                all_params = slot_data['params']
                au_identifier = slot_data['au_identifier']
                break
    elif slots:
        # Auto-select: use the slot with the most params (skip empty slots)
        best = max(slots.values(), key=lambda s: len(s['params']))
        all_params = best['params']
        au_identifier = best['au_identifier']

    # Include top-level params only if no slot was selected
    if not all_params:
        all_params = top_level_params

    if not plugin_name:
        plugin_name = plugin_id.replace('_', ' ').title()

    # Group params
    groups: dict[str, list[dict]] = {}
    for p in all_params:
        group = _infer_group(p['path'])
        p['group'] = group
        p['priority'] = 50
        p['tags'] = []
        groups.setdefault(group, []).append(p)

    # Build output structure
    result = {
        'plugin_id': plugin_id,
        'plugin_name': plugin_name,
        'au_identifier': au_identifier,
        'param_count': len(all_params),
        'groups': {
            group_name: {
                'display_name': group_name,
                'params': sorted(group_params, key=lambda p: p['path']),
            }
            for group_name, group_params in sorted(groups.items())
        },
    }

    return result


def harvest_to_file(
    input_path: str | Path,
    output_path: str | Path,
    plugin_id: str,
    plugin_name: str = '',
    slot_name: str = '',
) -> int:
    """Harvest params from AUM mapping and write to JSON file.

    Returns:
        Number of parameters extracted.
    """
    result = harvest_from_aum_midimap(
        input_path, plugin_id, plugin_name, slot_name=slot_name)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    return result['param_count']
