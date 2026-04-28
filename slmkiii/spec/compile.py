"""Compile MappingSpecModel → controller.config.Page list.

Resolves parametric mode references (when a page declares a focus_set with
vars), expands $n / $base+N substitutions in cc and label strings, and
produces dataclass-based Page objects that runtime.py consumes today.
"""

from __future__ import annotations

import re
from typing import Any

from slmkiii.controller.config import Binding, Page
from slmkiii.spec.models import (
    BindingModel,
    FocusEntry,
    MappingSpecModel,
    ModeModel,
    PadDrumKitModel,
    PageModel,
)
from slmkiii.sysex import Color


_SUBST_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")
_ARITH_RE = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*([+\-])\s*(\d+)\s*$")


def _subst_str(text: str, vars_: dict[str, Any]) -> str:
    """Substitute $name in a string with str(vars_[name]).

    Uses longest-prefix-in-vars matching: when the regex matches a maximal
    identifier run after `$`, we shrink the candidate from the right until
    a known var name is found. The trailing characters are preserved as
    literal text. So with vars = {"n": 1}, "$nparams" -> "1params" (not
    "<unknown $nparams>"). Use ``$$`` (not yet supported) or stop the
    identifier with a non-word char if you need a literal `$` followed by
    identifier characters.
    """
    def _repl(m: re.Match) -> str:
        full = m.group(1)
        # Try progressively shorter prefixes of `full` that exist in vars_
        for length in range(len(full), 0, -1):
            prefix = full[:length]
            if prefix in vars_:
                return str(vars_[prefix]) + full[length:]
        return m.group(0)
    return _SUBST_RE.sub(_repl, text)


def _resolve_cc(cc: int | str, vars_: dict[str, Any]) -> int:
    """Resolve cc (which may be int or string like '$base+1') to int."""
    if isinstance(cc, int):
        return cc
    s = cc.strip()
    if s.startswith("$"):
        # try arithmetic form: $base+1
        m = _ARITH_RE.match(s.lstrip("$"))
        if m:
            varname, op, lit = m.group(1), m.group(2), int(m.group(3))
            if varname not in vars_:
                raise KeyError(f"unknown var {varname!r} in cc expression {cc!r}")
            base = int(vars_[varname])
            return base + lit if op == "+" else base - lit
        # bare $name
        bare = s.lstrip("$")
        if bare in vars_:
            return int(vars_[bare])
        raise KeyError(f"unknown var {bare!r} in cc {cc!r}")
    # numeric string fallback
    return int(s)


def _resolve_binding(b: BindingModel, vars_: dict[str, Any], default_channel: int) -> Binding:
    return Binding(
        label=_subst_str(b.label, vars_),
        cc=_resolve_cc(b.cc, vars_),
        channel=b.channel if b.channel is not None else default_channel,
        param_path=_subst_str(b.param_path, vars_),
        min_val=b.min,
        max_val=b.max,
    )


def _resolve_pads(view, vars_: dict[str, Any]) -> list[Binding]:
    """Resolve a PadDrumKit-style view into 16 pad Bindings (or empty)."""
    if view is None:
        return []
    pads_widget = getattr(view, "pads", None)
    if pads_widget is None:
        return []
    if not isinstance(pads_widget, PadDrumKitModel):
        return []
    base_note = pads_widget.base_note
    chan = pads_widget.channel
    prefix = pads_widget.label_prefix
    out: list[Binding] = []
    for i in range(16):
        out.append(Binding(
            label=f"{prefix} {i + 1}"[:9],
            cc=base_note + i,
            channel=chan,
            param_path=f"drum_trigger_{i + 1}",
        ))
    return out


def _resolve_view(model: MappingSpecModel, page: PageModel):
    if page.view is None:
        return None
    if isinstance(page.view, str):
        return model.views.get(page.view)
    return page.view


def _resolve_mode(model: MappingSpecModel, page: PageModel):
    if isinstance(page.mode, str):
        return model.modes[page.mode]
    return page.mode


def _color_int(color_name: str) -> int:
    """Map YAML color name (e.g. 'RED') to slmkiii.sysex.Color int value."""
    try:
        return int(getattr(Color, color_name))
    except AttributeError:
        return 0


def _build_page(page: PageModel, mode: ModeModel | None, view, focus: FocusEntry | None,
                default_channel: int) -> Page:
    vars_ = dict(focus.vars) if focus is not None else {}

    knobs: list[Binding] = []
    faders: list[Binding] = []
    if mode is not None:
        knobs = [_resolve_binding(b, vars_, default_channel) for b in mode.knobs]
        faders = [_resolve_binding(b, vars_, default_channel) for b in mode.faders]

    pads = _resolve_pads(view, vars_)

    name = page.name if focus is None else f"{page.name}_{focus.id}"
    label = page.label if focus is None else focus.label

    return Page(
        name=name,
        label=label[:9],
        color=_color_int(page.color),
        knobs=knobs,
        faders=faders,
        pads=pads,
    )


def compile_spec(model: MappingSpecModel) -> list[Page]:
    """Compile a MappingSpecModel into a list of controller.config.Page.

    Each PageModel becomes one Page:
      - If no focus_set: a plain Page with the resolved bindings
      - If focus_set: a meta Page with focus_set + specialize callable that
        returns the pre-resolved Page for the requested focus index
        (matching runtime.py's existing focus-page mechanism)
    """
    out: list[Page] = []
    default_ch = model.defaults.channel
    for page in model.pages:
        mode = _resolve_mode(model, page)
        view = _resolve_view(model, page)
        if page.focus_set:
            # Pre-build all focus-resolved pages, then wrap in a meta with
            # focus_set + specialize callable
            resolved = [_build_page(page, mode, view, focus, default_ch)
                        for focus in page.focus_set]
            focus_ids = [focus.id for focus in page.focus_set]

            def _specialize(idx: int, _resolved=resolved) -> Page:
                return _resolved[idx]

            meta = Page(
                name=page.name,
                label=page.label[:9],
                color=_color_int(page.color),
                knobs=resolved[0].knobs,    # default to first focus's bindings
                faders=resolved[0].faders,
                pads=resolved[0].pads,
                focus_set=focus_ids,
                specialize=_specialize,
            )
            out.append(meta)
        else:
            out.append(_build_page(page, mode, view, None, default_ch))
    return out
