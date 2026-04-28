"""Shared `Page → AumMidiMapping` translator used by the runtime CLI and
the spec migration tool."""

from __future__ import annotations

from slmkiii.aum import AumMidiMapping, AumMsgType
from slmkiii.controller.config import Page


def _expand_focus(pages: list[Page]) -> list[Page]:
    """Flatten focus-set meta pages into per-instance pages.

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


def bindings_to_aum_mappings(
    pages: list[Page],
    *,
    expand_focus: bool = False,
) -> list[AumMidiMapping]:
    """Walk pages, dedupe bindings by (channel, cc, param_path), build
    AumMidiMappings. Set ``expand_focus=True`` to walk every focus_set
    instance (used by spec migration verification); leave False for the
    runtime live-render path which only addresses the active focus."""
    walk = _expand_focus(pages) if expand_focus else pages
    seen: set[tuple[int, int, str]] = set()
    out: list[AumMidiMapping] = []
    for p in walk:
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
