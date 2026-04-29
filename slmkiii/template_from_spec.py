"""Build an SL MkIII binary template from a MappingSpec YAML.

Goal: SL in TEMPLATE mode sends the plugin's actual CCs/notes directly so
AUM's MIDI Control engine (driven by .aum_midimap) maps them to plugin
parameters with no Mozaic in the path.

Layout policy (single-template-per-spec, packed flat):
  - SL knobs 1..16 = spec pages' knob bindings, in order, up to 16.
  - SL faders 1..8 = spec pages' fader bindings, in order, up to 8.
  - SL pad_hits   = the first spec page's pad bindings (drum kit), 0..16.
  - SL buttons    = unused for now.

For specs with focus_set, the FIRST focus instance is used (e.g. battalion
drum 1). This is the path-of-least-resistance shape; richer per-focus
templates can come later.
"""

from __future__ import annotations

from pathlib import Path

from slmkiii.controller.config import Binding
from slmkiii.spec.compile import compile_spec
from slmkiii.spec.loader import load_spec
from slmkiii.spec.models import MappingSpecModel
from slmkiii.template import Template


def _flat_knobs_faders_pads(model: MappingSpecModel
                            ) -> tuple[list[Binding], list[Binding], list[Binding]]:
    """Return (knobs, faders, pads) flattened across all spec pages.

    Knobs/faders are concatenated in page order. Pads come from the first
    page that defines any."""
    pages = compile_spec(model)
    knobs: list[Binding] = []
    faders: list[Binding] = []
    pads: list[Binding] = []
    for p in pages:
        # Use first focus for focused pages — gives a usable default mapping.
        page = p.specialize(0) if p.specialize else p
        knobs.extend(page.knobs)
        faders.extend(page.faders)
        if not pads and page.pads:
            pads = list(page.pads)
    return knobs, faders, pads


def build_template(model: MappingSpecModel,
                   template_name: str | None = None) -> Template:
    """Construct an SL MkIII Template configured from the spec."""
    knobs, faders, pads = _flat_knobs_faders_pads(model)
    name = (template_name
            or f"SLMK {model.plugin.name}")[:16]

    t = Template()
    t.name = name

    for slot, b in enumerate(knobs[:16]):
        t.knobs[slot].configure_cc(
            channel=b.channel, cc_num=b.cc, name=b.label[:9])
    for slot, b in enumerate(faders[:8]):
        t.faders[slot].configure_cc(
            channel=b.channel, cc_num=b.cc, name=b.label[:9])
    for slot, b in enumerate(pads[:16]):
        t.pad_hits[slot].configure_note(
            channel=b.channel, note=b.cc, name=b.label[:9])

    return t


def build_and_save(model: MappingSpecModel, out_dir: Path,
                   template_name: str | None = None) -> Path:
    t = build_template(model, template_name=template_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in t.name)
    path = out_dir / f"{safe}.syx"
    t.save(str(path))
    return path


def build_all_specs(specs_dir: Path | None = None,
                    out_dir: Path | None = None) -> list[Path]:
    """Build one template per *.yaml in slmkiii/data/specs/."""
    specs_dir = specs_dir or Path(__file__).parent / "data" / "specs"
    out_dir = out_dir or Path("output") / "templates"
    paths: list[Path] = []
    for yaml_path in sorted(specs_dir.glob("*.yaml")):
        model = load_spec(yaml_path)
        paths.append(build_and_save(model, out_dir))
    return paths
