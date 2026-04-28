"""Tree-walking evaluator for Mozaic Script.

Mozaic semantics implemented here:

* Every variable is internally a list (an "array"). Scalar reads are equivalent
  to ``arr[0]``; scalar writes overwrite ``arr[0]``.
* Reading an unassigned variable returns 0 (Mozaic ref §602).
* Array indices ≥ 1024 raise ``MozaicError``. Float indices are truncated to
  int.
* Assigned values are coerced to a 24-bit signed wrap (matches Mozaic's
  internal integer representation).
* Division by zero yields 0.
* Cascade rule: NoteOn fires ``@OnMidiInput → @OnMidiNote → @OnMidiNoteOn``.
  ``Exit`` aborts the rest of the cascade.
* ``Call @Handler`` preserves magic vars; depth > 32 raises.
* CC events fire ``@OnMidiInput → @OnMidiCC``.
* SysEx events fire ``@OnSysex``; ``ReceiveSysex arr`` copies the payload
  (without the F0/F7 envelope) into ``arr``, and ``SysexByte0..N`` magic vars
  expose the same payload.

Captured side-effects:

* ``midi_out: list[MidiEvent]`` — every CC / NoteOn / NoteOff sent.
* ``sysex_out: list[SysexEvent]`` — every SysEx packet sent.
* ``log: list[str]`` — every Log line, joined into a single string.

Real Mozaic functions like ``ShowLayout``, ``LabelPad``, ``ColorPad`` etc. are
recorded with no observable side-effect (they would manipulate the on-screen
UI of the AUv3, which we don't emulate).
"""

from __future__ import annotations

import math
from typing import Any, Callable

from slmkiii.mozaic import ast as A
from slmkiii.mozaic.errors import MozaicError
from slmkiii.mozaic.parser import parse
from slmkiii.mozaic.snapshot import MidiEvent, SysexEvent

_MAX_INDEX = 1024
_MAX_CALL_DEPTH = 32

# 24-bit signed wrap on assignment.
_INT_MIN = -(1 << 23)
_INT_MAX = (1 << 23) - 1


class _ExitSignal(Exception):
    """Raised by ``Exit`` to unwind the current handler chain."""


def _wrap24(v: int | float) -> int | float:
    if isinstance(v, float):
        # Floats are stored as-is — Mozaic actually has float support.
        return v
    # Two's complement wrap into a signed 24-bit range.
    v = v & 0xFFFFFF
    if v & 0x800000:
        v -= 0x1000000
    return v


def _to_int(v: Any) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)  # truncation toward zero
    raise MozaicError(f"cannot coerce {v!r} to int")


def _truthy(v: Any) -> bool:
    if isinstance(v, str):
        return bool(v)
    return _to_int(v) != 0


class MozaicInterp:
    """A Mozaic Script interpreter.

    Parameters
    ----------
    None — instantiate, then ``load(source)`` and ``fire(...)``.
    """

    def __init__(self) -> None:
        self.vars: dict[str, list[Any]] = {}
        self.assigned: set[str] = set()
        self.handlers: dict[str, list[A.Stmt]] = {}
        self.midi_out: list[MidiEvent] = []
        self.sysex_out: list[SysexEvent] = []
        self.log: list[str] = []
        self.tick = 0
        self.timer_interval_ms = 0
        self.timer_running = False
        self.timer_accum_ms = 0
        self.exit_event = False
        # Internal: depth counter for Call recursion limit.
        self._call_depth = 0
        # Per-event sysex payload (set during @OnSysex dispatch).
        self._sysex_payload: list[int] = []

    # ---- public API -------------------------------------------------------

    def load(self, source: str) -> None:
        """Parse ``source`` and register handlers; fire ``@OnLoad`` if present."""
        mod = parse(source)
        self.handlers = mod.handlers
        if "OnLoad" in self.handlers:
            self.fire("OnLoad")

    def fire(self, handler: str, **magic: Any) -> None:
        """Execute the named handler with the given magic vars set."""
        if handler not in self.handlers:
            return
        # Set magic vars (these are visible to the handler body).
        for k, v in magic.items():
            self._set_scalar(k, v)
        try:
            self._exec_block(self.handlers[handler])
        except _ExitSignal:
            self.exit_event = True

    def send_cc(self, channel: int, cc: int, val: int) -> None:
        """Simulate an inbound MIDI CC; fires the @OnMidiInput → @OnMidiCC chain."""
        magic = dict(
            MIDIChannel=channel,
            MIDICommand=0xB0 | (channel & 0x0F),
            MIDIByte1=0xB0 | (channel & 0x0F),
            MIDIByte2=cc,
            MIDIByte3=val,
        )
        self.exit_event = False
        for h in ("OnMidiInput", "OnMidiCC"):
            if self.exit_event:
                break
            if h in self.handlers:
                self.fire(h, **magic)

    def send_note_on(self, channel: int, note: int, vel: int) -> None:
        """Simulate inbound NoteOn; fires @OnMidiInput → @OnMidiNote → @OnMidiNoteOn."""
        magic = dict(
            MIDIChannel=channel,
            MIDICommand=0x90 | (channel & 0x0F),
            MIDIByte1=0x90 | (channel & 0x0F),
            MIDIByte2=note,
            MIDIByte3=vel,
        )
        self.exit_event = False
        for h in ("OnMidiInput", "OnMidiNote", "OnMidiNoteOn"):
            if self.exit_event:
                break
            if h in self.handlers:
                self.fire(h, **magic)

    def send_note_off(self, channel: int, note: int, vel: int = 0) -> None:
        """Simulate inbound NoteOff; fires @OnMidiInput → @OnMidiNote → @OnMidiNoteOff."""
        magic = dict(
            MIDIChannel=channel,
            MIDICommand=0x80 | (channel & 0x0F),
            MIDIByte1=0x80 | (channel & 0x0F),
            MIDIByte2=note,
            MIDIByte3=vel,
        )
        self.exit_event = False
        for h in ("OnMidiInput", "OnMidiNote", "OnMidiNoteOff"):
            if self.exit_event:
                break
            if h in self.handlers:
                self.fire(h, **magic)

    def send_sysex(self, data: bytes) -> None:
        """Simulate inbound SysEx; fires @OnSysex with SysexByte0..N magic vars."""
        # Strip F0/F7 envelope if present so SysexByte0 is the first payload byte.
        payload = list(data)
        if payload and payload[0] == 0xF0:
            payload = payload[1:]
        if payload and payload[-1] == 0xF7:
            payload = payload[:-1]
        self._sysex_payload = payload
        magic: dict[str, Any] = {"SysexSize": len(payload)}
        for i, b in enumerate(payload):
            magic[f"SysexByte{i}"] = b
        self.exit_event = False
        if "OnSysex" in self.handlers:
            self.fire("OnSysex", **magic)
        self._sysex_payload = []

    def advance_timer(self, ms: int) -> None:
        """Advance the simulated clock; fire @OnTimer once per interval elapsed."""
        self.tick += ms
        if not self.timer_running or self.timer_interval_ms <= 0:
            return
        self.timer_accum_ms += ms
        while self.timer_accum_ms >= self.timer_interval_ms:
            self.timer_accum_ms -= self.timer_interval_ms
            if "OnTimer" in self.handlers:
                self.fire("OnTimer", TimerNumber=0)

    # ---- variable storage -------------------------------------------------

    def _ensure_var(self, name: str) -> list[Any]:
        if name not in self.vars:
            self.vars[name] = [0]
        return self.vars[name]

    def _set_cell(self, name: str, idx: int, value: Any) -> None:
        if idx < 0:
            raise MozaicError(f"negative array index {idx} on {name}")
        if idx >= _MAX_INDEX:
            raise MozaicError(f"array index {idx} >= {_MAX_INDEX} on {name}")
        arr = self._ensure_var(name)
        if idx >= len(arr):
            arr.extend([0] * (idx + 1 - len(arr)))
        arr[idx] = _wrap24(value) if not isinstance(value, str) else value
        self.assigned.add(name)

    def _set_scalar(self, name: str, value: Any) -> None:
        self._set_cell(name, 0, value)

    def _get_cell(self, name: str, idx: int) -> Any:
        if idx < 0:
            raise MozaicError(f"negative array index {idx} on {name}")
        if idx >= _MAX_INDEX:
            raise MozaicError(f"array index {idx} >= {_MAX_INDEX} on {name}")
        arr = self.vars.get(name)
        if arr is None or idx >= len(arr):
            return 0
        return arr[idx]

    def _get_scalar(self, name: str) -> Any:
        return self._get_cell(name, 0)

    # ---- statement execution ---------------------------------------------

    def _exec_block(self, stmts: list[A.Stmt]) -> None:
        for s in stmts:
            self._exec(s)

    def _exec(self, s: A.Stmt) -> None:
        if isinstance(s, A.Assign):
            self._exec_assign(s)
            return
        if isinstance(s, A.If):
            for cond, body in s.branches:
                if _truthy(self._eval(cond)):
                    self._exec_block(body)
                    return
            self._exec_block(s.else_body)
            return
        if isinstance(s, A.For):
            lo = _to_int(self._eval(s.lo))
            hi = _to_int(self._eval(s.hi))
            step = 1 if hi >= lo else -1
            # `for i = lo to hi` is inclusive at both ends in Mozaic.
            i = lo
            while True:
                self._set_scalar(s.var, i)
                self._exec_block(s.body)
                if i == hi:
                    break
                i += step
            return
        if isinstance(s, A.While):
            while _truthy(self._eval(s.cond)):
                self._exec_block(s.body)
            return
        if isinstance(s, A.Repeat):
            while True:
                self._exec_block(s.body)
                if _truthy(self._eval(s.cond)):
                    break
            return
        if isinstance(s, A.Call):
            if self._call_depth >= _MAX_CALL_DEPTH:
                raise MozaicError(
                    f"Call depth exceeded {_MAX_CALL_DEPTH} (recursive @{s.handler}?)"
                )
            target = self.handlers.get(s.handler)
            if target is None:
                # Mozaic silently ignores Call to unknown handler; we follow.
                return
            self._call_depth += 1
            try:
                self._exec_block(target)
            finally:
                self._call_depth -= 1
            return
        if isinstance(s, A.Exit):
            raise _ExitSignal()
        if isinstance(s, A.BuiltinCall):
            self._exec_builtin(s.name, s.args)
            return
        raise MozaicError(f"unknown statement type {type(s).__name__}")

    def _exec_assign(self, s: A.Assign) -> None:
        rhs = s.value_expr
        if isinstance(rhs, A.FuncCall) and rhs.name == "__array__":
            # Bulk array fill at the given index (or 0 for scalar LHS).
            base = 0 if s.idx_expr is None else _to_int(self._eval(s.idx_expr))
            for i, elem in enumerate(rhs.args):
                self._set_cell(s.name, base + i, self._eval(elem))
            return
        value = self._eval(rhs)
        if s.idx_expr is None:
            self._set_scalar(s.name, value)
        else:
            self._set_cell(s.name, _to_int(self._eval(s.idx_expr)), value)

    # ---- expression evaluation -------------------------------------------

    def _eval(self, e: A.Expr) -> Any:
        if isinstance(e, A.Number):
            return e.value
        if isinstance(e, A.String):
            return e.value
        if isinstance(e, A.Var):
            return self._get_scalar(e.name)
        if isinstance(e, A.Index):
            idx = _to_int(self._eval(e.idx))
            return self._get_cell(e.name, idx)
        if isinstance(e, A.Unassigned):
            return 0 if e.name in self.assigned else 1
        if isinstance(e, A.UnaryOp):
            v = self._eval(e.operand)
            if e.op == "-":
                return -v
            if e.op == "not":
                return 0 if _truthy(v) else 1
            raise MozaicError(f"unknown unary op {e.op}")
        if isinstance(e, A.BinOp):
            return self._eval_binop(e)
        if isinstance(e, A.FuncCall):
            return self._eval_func(e.name, e.args)
        raise MozaicError(f"unknown expression type {type(e).__name__}")

    def _eval_binop(self, e: A.BinOp) -> Any:
        op = e.op
        # Short-circuit boolean ops.
        if op == "and":
            l = self._eval(e.left)
            if not _truthy(l):
                return 0
            return 1 if _truthy(self._eval(e.right)) else 0
        if op == "or":
            l = self._eval(e.left)
            if _truthy(l):
                return 1
            return 1 if _truthy(self._eval(e.right)) else 0
        l = self._eval(e.left)
        r = self._eval(e.right)
        if op == "+":
            return l + r
        if op == "-":
            return l - r
        if op == "*":
            return l * r
        if op == "/":
            if r == 0:
                return 0
            # Integer division if both are ints.
            if isinstance(l, int) and isinstance(r, int):
                # Truncate toward zero — matches C-style integer division.
                q = abs(l) // abs(r)
                return -q if (l < 0) ^ (r < 0) else q
            return l / r
        if op == "%":
            if r == 0:
                return 0
            return l % r
        if op == "&":
            return _to_int(l) & _to_int(r)
        if op == "|":
            return _to_int(l) | _to_int(r)
        if op == "^":
            return _to_int(l) ^ _to_int(r)
        if op == "=":
            return 1 if l == r else 0
        if op == "<>":
            return 1 if l != r else 0
        if op == "<":
            return 1 if l < r else 0
        if op == ">":
            return 1 if l > r else 0
        if op == "<=":
            return 1 if l <= r else 0
        if op == ">=":
            return 1 if l >= r else 0
        raise MozaicError(f"unknown binary op {op}")

    # ---- builtin dispatch -------------------------------------------------

    def _eval_func(self, name: str, args: list[A.Expr]) -> Any:
        # Function used as expression (parenthesised form).
        evaluated = [self._eval(a) for a in args]
        fn = _EXPR_BUILTINS.get(name)
        if fn is not None:
            return fn(self, evaluated)
        # Some functions are usable both as statements (recorded) and
        # expressions (no-op return 0). Fall back gracefully.
        return 0

    def _exec_builtin(self, name: str, args: list[A.Expr]) -> None:
        fn = _STMT_BUILTINS.get(name)
        if fn is None:
            # Unknown statement-form builtin: silently ignore (matches
            # Mozaic's tolerance for plugin-specific functions we don't
            # model). Record in log for diagnostic visibility in tests.
            self.log.append(f"<unknown:{name}>")
            return
        fn(self, args)


# ---- builtin implementations ---------------------------------------------


def _arg_int(interp: MozaicInterp, args: list[A.Expr], i: int, default: int = 0) -> int:
    if i >= len(args):
        return default
    return _to_int(interp._eval(args[i]))


def _stringify(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return str(v)
    return str(v)


# -- statement-form builtins (return None) --


def _b_send_sysex(interp: MozaicInterp, args: list[A.Expr]) -> None:
    if len(args) < 2:
        raise MozaicError("SendSysex requires (array_var, length)")
    var = args[0]
    if not isinstance(var, A.Var):
        raise MozaicError("SendSysex first arg must be a variable name")
    n = _to_int(interp._eval(args[1]))
    arr = interp.vars.get(var.name, [])
    payload = bytes(_to_int(arr[i]) & 0xFF for i in range(n) if i < len(arr))
    interp.sysex_out.append(SysexEvent(tick=interp.tick, bytes_data=payload))


def _b_send_sysex_thru(interp: MozaicInterp, args: list[A.Expr]) -> None:
    # No-op: there is no upstream sysex to forward in our test harness.
    pass


def _b_send_midi_cc(interp: MozaicInterp, args: list[A.Expr]) -> None:
    ch = _arg_int(interp, args, 0)
    cc = _arg_int(interp, args, 1)
    val = _arg_int(interp, args, 2)
    delay = _arg_int(interp, args, 3, 0) if len(args) > 3 else 0
    interp.midi_out.append(
        MidiEvent(
            tick=interp.tick + max(0, delay),
            status=0xB0 | (ch & 0x0F),
            data1=cc & 0x7F,
            data2=val & 0x7F,
        )
    )


def _b_send_midi_note_on(interp: MozaicInterp, args: list[A.Expr]) -> None:
    ch = _arg_int(interp, args, 0)
    note = _arg_int(interp, args, 1)
    vel = _arg_int(interp, args, 2)
    delay = _arg_int(interp, args, 3, 0) if len(args) > 3 else 0
    interp.midi_out.append(
        MidiEvent(
            tick=interp.tick + max(0, delay),
            status=0x90 | (ch & 0x0F),
            data1=note & 0x7F,
            data2=vel & 0x7F,
        )
    )


def _b_send_midi_note_off(interp: MozaicInterp, args: list[A.Expr]) -> None:
    ch = _arg_int(interp, args, 0)
    note = _arg_int(interp, args, 1)
    vel = _arg_int(interp, args, 2, 0) if len(args) > 2 else 0
    delay = _arg_int(interp, args, 3, 0) if len(args) > 3 else 0
    interp.midi_out.append(
        MidiEvent(
            tick=interp.tick + max(0, delay),
            status=0x80 | (ch & 0x0F),
            data1=note & 0x7F,
            data2=vel & 0x7F,
        )
    )


def _b_send_midi_thru(interp: MozaicInterp, args: list[A.Expr]) -> None:
    pass


def _b_send_midi_thru_on_ch(interp: MozaicInterp, args: list[A.Expr]) -> None:
    pass


def _b_fill_array(interp: MozaicInterp, args: list[A.Expr]) -> None:
    if not args or not isinstance(args[0], A.Var):
        raise MozaicError("FillArray first arg must be a variable name")
    name = args[0].name
    val = _to_int(interp._eval(args[1])) if len(args) > 1 else 0
    n = _to_int(interp._eval(args[2])) if len(args) > 2 else _MAX_INDEX
    n = min(n, _MAX_INDEX)
    arr = interp._ensure_var(name)
    if n > len(arr):
        arr.extend([0] * (n - len(arr)))
    for i in range(n):
        arr[i] = _wrap24(val)
    interp.assigned.add(name)


def _resolve_arr_offset(arg: A.Expr, interp: MozaicInterp) -> tuple[str, int]:
    """Resolve ``Var`` / ``Index`` argument forms into (name, offset)."""
    if isinstance(arg, A.Var):
        return arg.name, 0
    if isinstance(arg, A.Index):
        return arg.name, _to_int(interp._eval(arg.idx))
    raise MozaicError("expected array reference (Var or Var[idx])")


def _b_copy_array(interp: MozaicInterp, args: list[A.Expr]) -> None:
    if len(args) < 2:
        raise MozaicError("CopyArray requires (src, dst[, n])")
    src_name, src_off = _resolve_arr_offset(args[0], interp)
    dst_name, dst_off = _resolve_arr_offset(args[1], interp)
    n = _to_int(interp._eval(args[2])) if len(args) > 2 else _MAX_INDEX
    n = max(0, min(n, _MAX_INDEX))
    src = interp._ensure_var(src_name)
    dst = interp._ensure_var(dst_name)
    needed = dst_off + n
    if needed > len(dst):
        dst.extend([0] * (needed - len(dst)))
    for i in range(n):
        v = src[src_off + i] if src_off + i < len(src) else 0
        dst[dst_off + i] = v
    interp.assigned.add(dst_name)


def _b_receive_sysex(interp: MozaicInterp, args: list[A.Expr]) -> None:
    if not args or not isinstance(args[0], A.Var):
        raise MozaicError("ReceiveSysex requires a variable name")
    name = args[0].name
    payload = interp._sysex_payload
    arr = interp._ensure_var(name)
    needed = len(payload)
    if needed > len(arr):
        arr.extend([0] * (needed - len(arr)))
    for i, b in enumerate(payload):
        arr[i] = b
    interp.assigned.add(name)


def _b_log(interp: MozaicInterp, args: list[A.Expr]) -> None:
    parts = [_stringify(interp._eval(a)) for a in args]
    interp.log.append("".join(parts))


def _b_set_timer_interval(interp: MozaicInterp, args: list[A.Expr]) -> None:
    interp.timer_interval_ms = max(0, _arg_int(interp, args, 0))


def _b_start_timer(interp: MozaicInterp, args: list[A.Expr]) -> None:
    interp.timer_running = True
    interp.timer_accum_ms = 0


def _b_stop_timer(interp: MozaicInterp, args: list[A.Expr]) -> None:
    interp.timer_running = False


def _b_reset_timer(interp: MozaicInterp, args: list[A.Expr]) -> None:
    interp.timer_accum_ms = 0


def _b_noop(interp: MozaicInterp, args: list[A.Expr]) -> None:
    """No-op for UI builtins (LabelPad, ColorPad, etc.)."""
    pass


# -- expression-form builtins (return value) --


def _f_round(interp: MozaicInterp, args: list[Any]) -> int:
    if not args:
        return 0
    return int(round(args[0]))


def _f_round_up(interp: MozaicInterp, args: list[Any]) -> int:
    if not args:
        return 0
    return int(math.ceil(args[0]))


def _f_round_down(interp: MozaicInterp, args: list[Any]) -> int:
    if not args:
        return 0
    return int(math.floor(args[0]))


def _f_div(interp: MozaicInterp, args: list[Any]) -> int:
    if len(args) < 2 or args[1] == 0:
        return 0
    return _to_int(args[0]) // _to_int(args[1])


def _f_clip(interp: MozaicInterp, args: list[Any]) -> Any:
    if len(args) < 3:
        return args[0] if args else 0
    v, lo, hi = args[0], args[1], args[2]
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _f_abs(interp: MozaicInterp, args: list[Any]) -> Any:
    return abs(args[0]) if args else 0


def _f_min(interp: MozaicInterp, args: list[Any]) -> Any:
    return min(args) if args else 0


def _f_max(interp: MozaicInterp, args: list[Any]) -> Any:
    return max(args) if args else 0


_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _f_note_name(interp: MozaicInterp, args: list[Any]) -> str:
    if not args:
        return ""
    n = _to_int(args[0])
    show_oct = bool(_to_int(args[1])) if len(args) > 1 else False
    name = _NOTE_NAMES[n % 12]
    if show_oct:
        return f"{name}{(n // 12) - 1}"
    return name


def _f_const_zero(interp: MozaicInterp, args: list[Any]) -> int:
    return 0


_STMT_BUILTINS: dict[str, Callable[[MozaicInterp, list[A.Expr]], None]] = {
    "SendSysex": _b_send_sysex,
    "SendSysexThru": _b_send_sysex_thru,
    "SendMIDICC": _b_send_midi_cc,
    "SendMidiCC": _b_send_midi_cc,  # tolerate casing variations
    "SendMIDINoteOn": _b_send_midi_note_on,
    "SendMidiNoteOn": _b_send_midi_note_on,
    "SendMIDINoteOff": _b_send_midi_note_off,
    "SendMidiNoteOff": _b_send_midi_note_off,
    "SendMIDIThru": _b_send_midi_thru,
    "SendMidiThru": _b_send_midi_thru,
    "SendMIDIThruOnCh": _b_send_midi_thru_on_ch,
    "SendMidiThruOnCh": _b_send_midi_thru_on_ch,
    "FillArray": _b_fill_array,
    "CopyArray": _b_copy_array,
    "ReceiveSysex": _b_receive_sysex,
    "Log": _b_log,
    "LogTime": _b_log,
    "SetTimerInterval": _b_set_timer_interval,
    "StartTimer": _b_start_timer,
    "StopTimer": _b_stop_timer,
    "ResetTimer": _b_reset_timer,
    "SetShortName": _b_noop,
    "LabelPads": _b_noop,
    "LabelPad": _b_noop,
    "ColorPad": _b_noop,
    "LatchPad": _b_noop,
    "ShowLayout": _b_noop,
}

_EXPR_BUILTINS: dict[str, Callable[[MozaicInterp, list[Any]], Any]] = {
    "Round": _f_round,
    "RoundUp": _f_round_up,
    "RoundDown": _f_round_down,
    "Div": _f_div,
    "Clip": _f_clip,
    "Abs": _f_abs,
    "Min": _f_min,
    "Max": _f_max,
    "NoteName": _f_note_name,
    "Random": _f_const_zero,
    "GetKnobValue": _f_const_zero,
    "Log10": _f_const_zero,
    "Logn": _f_const_zero,
}
