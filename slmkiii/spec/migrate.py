"""Migrate Python-dataclass page specs to YAML MappingSpec.

Reads a slmkiii.controller.pages.<name> module, walks its PAGES list (and
any DRUM_FOCUS_PAGES dict if present), and emits a YAML file matching the
pydantic v2 MappingSpecModel schema.

Each Python Page becomes one inline YAML page (no parametric inference for
now — that's an optional manual cleanup later). The --verify flag re-loads
the YAML, compiles back to Page objects, regenerates the .aum_midimap, and
byte-compares against the original — refuses to write on mismatch.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import ruamel.yaml

from slmkiii.aum import AumMidiMapping, AumMsgType, generate_midimap_bytes
from slmkiii.controller.config import Binding, Page
from slmkiii.spec.compile import compile_spec
from slmkiii.spec.loader import load_spec_dict
from slmkiii.spec.models import MappingSpecModel
from slmkiii.sysex import Color


def _color_name(color_int: int) -> str:
    """Reverse-map a Color int value back to its name (e.g. 5 -> 'RED').
    Falls back to 'WHITE' if no exact match (rare)."""
    for c in Color:
        if int(c) == color_int:
            return c.name
    return "WHITE"


def _binding_to_dict(b: Binding) -> dict[str, Any]:
    out: dict[str, Any] = {
        "label": b.label,
        "cc": b.cc,
        "channel": b.channel,
    }
    if b.param_path:
        out["param_path"] = b.param_path
    if b.min_val != 0:
        out["min"] = b.min_val
    if b.max_val != 127:
        out["max"] = b.max_val
    return out


def _detect_pad_widget(page: Page) -> dict[str, Any] | None:
    """Detect a PadDrumKit-shaped pads list and emit its widget definition."""
    if not page.pads:
        return None
    # Check that pads form a consecutive note sequence on a single channel
    base = page.pads[0]
    for i, p in enumerate(page.pads):
        if p.channel != base.channel or p.cc != base.cc + i:
            return None
    # Extract a sensible label_prefix from "Pad 1" -> "Pad", "Drum 1" -> "Drum"
    first_label = page.pads[0].label
    prefix = first_label.rstrip("0123456789 ").strip() or "Pad"
    return {
        "type": "PadDrumKit",
        "base_note": base.cc,
        "channel": base.channel,
        "label_prefix": prefix,
    }


def _page_to_dict(page: Page, page_index: int, default_channel: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Returns (page_dict, optional_view_dict). View is inlined into the
    page when present."""
    mode_dict: dict[str, Any] = {}
    if page.knobs:
        mode_dict["knobs"] = [_binding_to_dict(b) for b in page.knobs]
    if page.faders:
        mode_dict["faders"] = [_binding_to_dict(b) for b in page.faders]

    page_dict: dict[str, Any] = {
        "name": page.name,
        "label": page.label,
        "color": _color_name(page.color),
        "mode": mode_dict if mode_dict else {},
    }
    pad_widget = _detect_pad_widget(page)
    if pad_widget is not None:
        page_dict["view"] = {"pads": pad_widget}
    return page_dict, None


def migrate_module(module_name: str,
                   *,
                   plugin_au_id: str | None = None,
                   plugin_name: str | None = None) -> dict[str, Any]:
    """Load a slmkiii.controller.pages.<name> module and produce a YAML-serializable dict."""
    mod = importlib.import_module(module_name)
    pages: list[Page] = list(getattr(mod, "PAGES", []))
    drum_focus = getattr(mod, "DRUM_FOCUS_PAGES", None)
    au_id = plugin_au_id or getattr(mod, "AU_IDENTIFIER", None)

    # Combine PAGES + DRUM_FOCUS_PAGES (if focus pages exist, append them in order)
    if drum_focus:
        focus_pages = [drum_focus[k] for k in sorted(drum_focus.keys())]
        pages = pages + focus_pages

    short = module_name.rsplit(".", 1)[-1]
    spec: dict[str, Any] = {
        "spec_version": 1,
        "name": short,
        "label": (pages[0].label if pages else short)[:9],
        "project_id": short,
        "plugin": {
            "name": plugin_name or short.capitalize(),
            "au_id": au_id,
        },
        "modes": {},
        "views": {},
        "pages": [],
    }
    if au_id is None:
        spec["plugin"].pop("au_id")

    for i, page in enumerate(pages):
        page_dict, _ = _page_to_dict(page, i, 1)
        spec["pages"].append(page_dict)

    return spec


def _expand_pages(pages: list[Page]) -> list[Page]:
    """Flatten focus-set meta pages into per-instance pages for AUM export.

    A page with `specialize` set produces N specialized pages (one per
    focus_set entry). A plain page passes through unchanged.
    """
    out: list[Page] = []
    for p in pages:
        if p.specialize is not None and p.focus_set:
            for i in range(len(p.focus_set)):
                out.append(p.specialize(i))
        else:
            out.append(p)
    return out


def _bindings_to_aum_mappings(pages: list[Page]) -> list[AumMidiMapping]:
    """Mirror of slmkiii.controller.cli._bindings_to_mappings, with focus
    expansion so all sub-instance bindings reach the AUM mapping file."""
    seen: set[tuple[int, int, str]] = set()
    out: list[AumMidiMapping] = []
    for p in _expand_pages(pages):
        for b in list(p.knobs) + list(p.faders):
            if not b.param_path:
                continue
            key = (b.channel - 1, b.cc, b.param_path)
            if key in seen:
                continue
            seen.add(key)
            out.append(AumMidiMapping(
                parameter_name=b.param_path,
                cc_number=b.cc,
                channel=b.channel - 1,
                min_value=0.0,
                max_value=1.0,
                enabled=True,
                auto_toggle=False,
                msg_type=int(AumMsgType.CC),
            ))
    return out


def verify_round_trip(module_name: str, spec_dict: dict[str, Any]) -> tuple[bool, str]:
    """Round-trip the migrated YAML and byte-compare AUM mapping output."""
    mod = importlib.import_module(module_name)
    drum_focus = getattr(mod, "DRUM_FOCUS_PAGES", None)
    py_pages = list(getattr(mod, "PAGES", []))
    if drum_focus:
        py_pages = py_pages + [drum_focus[k] for k in sorted(drum_focus.keys())]

    try:
        model = load_spec_dict(spec_dict)
    except Exception as e:
        return False, f"YAML failed to validate: {e}"

    yml_pages = compile_spec(model)

    py_maps = _bindings_to_aum_mappings(py_pages)
    yml_maps = _bindings_to_aum_mappings(yml_pages)

    # Use a stable AU identifier for both — only the binding contents matter
    collection = "verify"
    py_bytes = generate_midimap_bytes(collection, py_maps)
    yml_bytes = generate_midimap_bytes(collection, yml_maps)

    if py_bytes == yml_bytes:
        return True, f"OK: {len(py_maps)} mappings round-trip byte-equal"
    return (False,
            f"MISMATCH: py={len(py_maps)} maps, yml={len(yml_maps)} maps; "
            f"py_size={len(py_bytes)} yml_size={len(yml_bytes)}")


def write_yaml(spec_dict: dict[str, Any], path: Path) -> None:
    yml = ruamel.yaml.YAML(typ="rt")
    yml.indent(mapping=2, sequence=4, offset=2)
    yml.width = 160
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# yaml-language-server: $schema=../schemas/mapping-spec-v1.json\n")
        yml.dump(spec_dict, f)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Migrate Python page spec to YAML")
    parser.add_argument("--module", required=True,
                        help="dotted module path, e.g. slmkiii.controller.pages.battalion")
    parser.add_argument("--out", required=True, help="output YAML path")
    parser.add_argument("--verify", action="store_true",
                        help="reload YAML, regenerate AUM mapping, byte-compare to original")
    parser.add_argument("--plugin-name", default=None)
    parser.add_argument("--au-id", default=None)
    args = parser.parse_args()

    spec_dict = migrate_module(args.module,
                               plugin_au_id=args.au_id,
                               plugin_name=args.plugin_name)

    if args.verify:
        ok, msg = verify_round_trip(args.module, spec_dict)
        print(msg, file=sys.stderr)
        if not ok:
            return 1

    write_yaml(spec_dict, Path(args.out))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
