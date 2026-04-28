"""Pydantic v2 models for declarative MappingSpec authoring.

The YAML/JSON spec files compile down (via c14+ tooling) to the runtime
``slmkiii.controller.config`` dataclasses. Authors edit YAML; this module
performs validation, ref-by-name resolution, and CC collision detection.

The models are deliberately *strict* (``extra="forbid"``) so that typos in
spec files are caught at load time rather than silently ignored.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


# String enum aliases that map to ``slmkiii.sysex.Color``.
# Keep the literal list a *superset* of the IntEnum so that authors can
# reach for natural color names; the c14 compiler is responsible for
# mapping unknown names to a sensible fallback if needed.
Color = Literal[
    "OFF",
    "RED",
    "ORANGE",
    "YELLOW",
    "GREEN",
    "CYAN",
    "BLUE",
    "PURPLE",
    "MAGENTA",
    "WHITE",
    "DIM_WHITE",
    "DIM_GREEN",
    "DIM_RED",
    "DIM_BLUE",
    "BLACK",
]

SLControl = Literal[
    "TRACK_LEFT",
    "TRACK_RIGHT",
    "SCENE_UP",
    "SCENE_DOWN",
    "PADS_UP",
    "PADS_DOWN",
    "TRANSPORT_PLAY",
    "TRANSPORT_STOP",
    "TRANSPORT_RECORD",
    "DISPLAY_BUTTON_1",
    "DISPLAY_BUTTON_2",
    "DISPLAY_BUTTON_3",
    "DISPLAY_BUTTON_4",
    "DISPLAY_BUTTON_5",
    "DISPLAY_BUTTON_6",
    "DISPLAY_BUTTON_7",
    "DISPLAY_BUTTON_8",
    "BUTTON_ROW1_1",
    "BUTTON_ROW1_2",
    "BUTTON_ROW1_3",
    "BUTTON_ROW1_4",
    "BUTTON_ROW1_5",
    "BUTTON_ROW1_6",
    "BUTTON_ROW1_7",
    "BUTTON_ROW1_8",
]

CC = Annotated[int, Field(ge=0, le=127)]
Channel = Annotated[int, Field(ge=1, le=16)]
Label = Annotated[str, Field(max_length=9)]


class _Strict(BaseModel):
    """Common base: forbid unknown keys, strip whitespace from strings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BindingModel(_Strict):
    """One control-to-parameter binding (knob, fader, button, or pad)."""

    label: Label
    cc: int | str  # str supports parametric expressions like "$base+1"
    channel: Channel | None = None
    param_path: str = ""
    min: int = Field(default=0, ge=0, le=127)
    max: int = Field(default=127, ge=0, le=127)
    units: str = ""
    transform: Literal["linear", "log", "exp", "bipolar"] = "linear"

    @model_validator(mode="after")
    def _range(self) -> "BindingModel":
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) > max ({self.max})")
        return self

    @model_validator(mode="after")
    def _cc_int_range(self) -> "BindingModel":
        # Parametric (str) CCs are validated by the compiler later.
        if isinstance(self.cc, int) and not (0 <= self.cc <= 127):
            raise ValueError(f"cc {self.cc} out of range; must be 0..127")
        return self


class ModeModel(_Strict):
    """A reusable knob/fader assignment shared by multiple pages."""

    knobs: list[BindingModel] = Field(default_factory=list, max_length=8)
    faders: list[BindingModel] = Field(default_factory=list, max_length=8)


# ---------------------------------------------------------------------------
# Discriminated-union widgets for the View layer (pads / radio / extras).
# ---------------------------------------------------------------------------


class _Widget(_Strict):
    type: str


class PadDrumKitModel(_Widget):
    type: Literal["PadDrumKit"]
    base_note: Annotated[int, Field(ge=0, le=112)]
    channel: Channel = 10
    label_prefix: str = "Pad"
    velocity: Literal["fixed", "sensitive"] = "sensitive"
    fixed_velocity: Annotated[int, Field(ge=1, le=127)] = 100
    colors: dict[str, Color] = Field(
        default_factory=lambda: {"rest": "BLUE", "active": "WHITE"},
    )


class StepGridModel(_Widget):
    type: Literal["StepGrid"]
    rows: Annotated[int, Field(ge=1, le=2)]
    steps: Annotated[int, Field(ge=2, le=16)]
    voices: list[BindingModel]
    cc_step_base: CC


class RadioGroupModel(_Widget):
    type: Literal["RadioGroup"]
    target: Literal["focus", "page", "custom"]
    count: Annotated[int, Field(ge=2, le=16)]
    colors: dict[str, Color] = Field(
        default_factory=lambda: {"selected": "WHITE", "idle": "DIM_WHITE"},
    )


class IncDecModel(_Widget):
    type: Literal["IncDec"]
    target: Literal["focus", "page", "value"]
    binding: BindingModel | None = None


class KnobBankModel(_Widget):
    type: Literal["KnobBank"]
    bindings: list[BindingModel] = Field(min_length=1, max_length=8)


class FaderBankModel(_Widget):
    type: Literal["FaderBank"]
    bindings: list[BindingModel] = Field(min_length=1, max_length=8)


Widget = Annotated[
    Union[
        PadDrumKitModel,
        StepGridModel,
        RadioGroupModel,
        IncDecModel,
        KnobBankModel,
        FaderBankModel,
    ],
    Field(discriminator="type"),
]


class ViewModel(_Strict):
    """A view describes the pad/radio/etc. widgets for a page."""

    pads: Widget | None = None
    radio: Widget | None = None
    extras: list[Widget] = Field(default_factory=list)


class FocusEntry(_Strict):
    """One entry in a page's focus_set: a sub-instance selector with vars.

    The ``vars`` dict provides substitutions for parametric ``cc`` strings
    in the page's mode bindings (e.g. ``"$base+1"`` resolves using
    ``vars["base"]``).
    """

    id: str
    label: Label
    vars: dict[str, int | str] = Field(default_factory=dict)


class PageModel(_Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: Label
    color: Color
    mode: str | ModeModel  # ref-by-name OR inline
    view: str | ViewModel | None = None
    focus_set: list[FocusEntry] = Field(default_factory=list)


class PluginInfo(_Strict):
    name: str
    au_id: str | None = None
    vendor: str | None = None


class EchoSub(_Strict):
    """One subscription for the SL MkIII -> AUM plugin echo path."""

    channel: Channel
    cc: CC | None = None
    cc_range: tuple[CC, CC] | None = None

    @model_validator(mode="after")
    def _xor(self) -> "EchoSub":
        if (self.cc is None) == (self.cc_range is None):
            raise ValueError("specify exactly one of `cc` or `cc_range`")
        return self


class Defaults(_Strict):
    channel: Channel = 1
    cc_range: tuple[CC, CC] = (20, 119)
    reserved_ccs: list[CC] = Field(
        default_factory=lambda: [7, 64, 65, 66, 67, 68, 69, 96, 97, 98, 99],
    )


class NavOverrides(_Strict):
    page_prev: SLControl = "TRACK_LEFT"
    page_next: SLControl = "TRACK_RIGHT"
    focus_prev: SLControl = "PADS_UP"
    focus_next: SLControl = "PADS_DOWN"


class MappingSpecModel(_Strict):
    """Top-level declarative spec for a controller mapping.

    Author-facing fields are validated strictly: typos in keys, out-of-range
    CCs/channels/labels, undefined ``mode``/``view`` references, and CC
    collisions across pages are all caught at load time.
    """

    spec_version: Literal[1]
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: Label
    project_id: str
    plugin: PluginInfo
    defaults: Defaults = Field(default_factory=Defaults)
    plugin_echo: list[EchoSub] = Field(default_factory=list)
    modes: dict[str, ModeModel] = Field(default_factory=dict)
    views: dict[str, ViewModel] = Field(default_factory=dict)
    pages: list[PageModel] = Field(min_length=1, max_length=8)
    navigation: NavOverrides = Field(default_factory=NavOverrides)

    @model_validator(mode="after")
    def _resolve_refs(self) -> "MappingSpecModel":
        for p in self.pages:
            if isinstance(p.mode, str) and p.mode not in self.modes:
                raise ValueError(
                    f"page {p.name!r}: mode {p.mode!r} not in `modes`"
                )
            if isinstance(p.view, str) and p.view not in self.views:
                raise ValueError(
                    f"page {p.name!r}: view {p.view!r} not in `views`"
                )
        return self

    @model_validator(mode="after")
    def _no_cc_collisions(self) -> "MappingSpecModel":
        seen: dict[tuple[int, int], str] = {}
        for p in self.pages:
            mode = self.modes[p.mode] if isinstance(p.mode, str) else p.mode
            if mode is None:
                continue
            for kind, lst in (("knob", mode.knobs), ("fader", mode.faders)):
                for b in lst:
                    if isinstance(b.cc, str):
                        # Parametric; resolved during compile.
                        continue
                    ch = b.channel or self.defaults.channel
                    key = (ch, b.cc)
                    label = b.param_path or f"{p.name}/{b.label}"
                    if key in seen and seen[key] != label:
                        raise ValueError(
                            f"CC collision on ch{ch} cc{b.cc}: "
                            f"{seen[key]!r} and page {p.name!r}/{kind} "
                            f"{b.label!r}"
                        )
                    seen[key] = label
        return self


# Convenience re-exports under shorter names for callers that want to
# write `Binding` / `Page` / `Mode` / `View`.
Binding = BindingModel
Page = PageModel
Mode = ModeModel
View = ViewModel
