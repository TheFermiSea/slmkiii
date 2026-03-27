"""Generate AUM .aum_midimap files from resolved mappings.

AUM's Channel-level mapping files have a nested structure:
  Root:
    _collection_map_name: "Channel"
    Channel controls: {Volume, Pan, Mute, Solo, ...}
    slot0: {
      _collection_map_name: "PluginName.AU-hexid"
      drumProtoParams: {
        drumProtoParams.drum1params: {
          drumProtoParams.drum1params.drum1cutoff: {specState: ...}
        }
      }
    }
    slot1: {...}

The parameter paths use AUM's dot-delimited convention where each
nesting level's key includes the full path prefix.
"""
from __future__ import annotations

from pathlib import Path

from aum_tools import MSG_TYPE_CC, MSG_TYPE_NOTE, ArchiverBuilder
from controlmap.model import MsgType, ResolvedMapping


class AumEmitter:
    """Generate .aum_midimap files matching AUM's expected structure."""

    target_id = 'aum'

    def emit(
        self,
        resolved: ResolvedMapping,
        output_dir: str | Path,
        slot_index: int = 0,
    ) -> list[Path]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        au_identifier = resolved.metadata.get('au_identifier', '')

        # Build the nested parameter dict matching AUM's structure
        param_tree: dict = {}
        for binding in resolved.page_set.all_bindings:
            if binding.msg_type == MsgType.NOTE:
                msg_type = MSG_TYPE_NOTE
                data1 = binding.midi_note
            else:
                msg_type = MSG_TYPE_CC
                data1 = binding.midi_cc

            entry = {
                'min': binding.min_value,
                'max': binding.max_value,
                'channel': binding.midi_channel - 1,  # AUM uses 0-indexed
                'autoToggle': False,
                'specState': {
                    'enabled': True,
                    'data1': data1,
                    'type': msg_type,
                },
            }

            # Rebuild the nested hierarchy from the dot-delimited path
            # e.g., "drumProtoParams.drum1params.drum1cutoff"
            # becomes: param_tree["drumProtoParams"]["drumProtoParams.drum1params"]["drumProtoParams.drum1params.drum1cutoff"] = entry
            path = binding.param.param_path
            parts = path.split('.')
            current = param_tree
            for depth in range(len(parts) - 1):
                prefix = '.'.join(parts[:depth + 1])
                if prefix not in current:
                    current[prefix] = {}
                current = current[prefix]
            current[path] = entry

        # Build the slot dict
        slot = {
            '_collection_map_name': au_identifier,
        }
        slot.update(param_tree)

        # Build the Channel-level root
        root = {
            '_collection_map_name': 'Channel',
            '_collection_editor_states': [],
            f'slot{slot_index}': slot,
            'Channel controls': {
                '_collection_map_name': 'Channel controls',
            },
        }

        # Encode as NSKeyedArchiver plist
        builder = ArchiverBuilder()
        data = builder.build(root)

        safe_name = resolved.spec.name.replace('/', '_')
        filename = f'{safe_name}.aum_midimap'
        path = output_dir / filename
        with open(path, 'wb') as f:
            f.write(data)

        return [path]
