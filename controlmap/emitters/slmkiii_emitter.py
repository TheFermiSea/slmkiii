"""Generate SL MkIII .syx template files from resolved mappings."""
from __future__ import annotations

from pathlib import Path

import slmkiii
from controlmap.model import MsgType, ResolvedMapping

# Map controlmap group names to slmkiii template section names
_GROUP_TO_SECTION = {
    'knobs': 'knobs',
    'faders': 'faders',
    'buttons': 'buttons',
    'pads': 'pad_hits',
}


class SlMkIIIEmitter:
    """Generate .syx template files using slmkiii.Template."""

    target_id = 'slmkiii'

    def emit(
        self,
        resolved: ResolvedMapping,
        output_dir: str | Path,
    ) -> list[Path]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        files = []

        for page in resolved.page_set.pages:
            template = slmkiii.Template()
            template.name = page.name[:16]  # SL MkIII name max 16 chars

            for binding in page.bindings:
                section_name = _GROUP_TO_SECTION.get(binding.slot.group)
                if section_name is None:
                    continue

                section = getattr(template, section_name, None)
                if section is None or binding.slot.index >= len(section):
                    continue

                control = section[binding.slot.index]
                if binding.msg_type == MsgType.NOTE:
                    control.configure_note(
                        channel=binding.midi_channel,
                        note=binding.midi_note,
                        name=binding.param.display_name,
                    )
                else:
                    control.configure_cc(
                        channel=binding.midi_channel,
                        cc_num=binding.midi_cc,
                        name=binding.param.display_name,
                    )

            filename = f'{page.name}.syx'.replace(' ', '_')
            path = output_dir / filename
            template.save(str(path))
            files.append(path)

        return files
