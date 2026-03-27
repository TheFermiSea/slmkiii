"""Generate AUM .aum_midimap files from resolved mappings."""
from __future__ import annotations

from pathlib import Path

from aum_tools import AumMidiMapping, write_aum_midimap, MSG_TYPE_CC, MSG_TYPE_NOTE
from controlmap.model import ResolvedMapping


class AumEmitter:
    """Generate .aum_midimap files using aum_tools."""

    target_id = 'aum'

    def emit(
        self,
        resolved: ResolvedMapping,
        output_dir: str | Path,
    ) -> list[Path]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        collection_name = resolved.metadata.get(
            'au_identifier',
            resolved.spec.plugin_id,
        )

        # Collect all bindings across all pages
        mappings = []
        for binding in resolved.page_set.all_bindings:
            if binding.msg_type == 'note':
                msg_type = MSG_TYPE_NOTE
                cc = binding.midi_note
            else:
                msg_type = MSG_TYPE_CC
                cc = binding.midi_cc

            mappings.append(AumMidiMapping(
                parameter_name=binding.param.param_path,
                cc_number=cc,
                channel=binding.midi_channel - 1,  # AUM uses 0-indexed
                min_value=binding.min_value,
                max_value=binding.max_value,
                enabled=True,
                msg_type=msg_type,
            ))

        # Write the mapping file
        safe_name = collection_name.replace('/', '_')
        filename = f'{safe_name}.aum_midimap'
        path = output_dir / filename
        write_aum_midimap(collection_name, mappings, path)

        return [path]
