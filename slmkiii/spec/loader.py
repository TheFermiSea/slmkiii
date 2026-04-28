"""YAML loader for MappingSpecModel with file/path-aware error reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from slmkiii.spec.models import MappingSpecModel


class SpecError(Exception):
    """Raised when a spec fails to load or validate."""


def load_spec(path: str | Path) -> MappingSpecModel:
    """Load and validate a YAML spec file.

    Raises ``SpecError`` with a multi-line message that names the file and
    every validation error (with dotted location path).
    """
    p = Path(path)
    text = p.read_text()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SpecError(f"{p}: YAML parse error: {e}") from e
    if data is None:
        raise SpecError(f"{p}: file is empty or YAML loaded as None")
    try:
        return MappingSpecModel.model_validate(data)
    except ValidationError as e:
        raise SpecError(_format(p, text, e)) from e


def load_spec_dict(data: dict[str, Any]) -> MappingSpecModel:
    """Load from an already-parsed dict (used by tests + migrate tooling)."""
    try:
        return MappingSpecModel.model_validate(data)
    except ValidationError as e:
        raise SpecError(_format_dict(e)) from e


def _format(path: Path, text: str, err: ValidationError) -> str:
    # ``text`` is currently unused (no line/column info from pydantic v2);
    # kept in the signature so a future upgrade can surface line numbers.
    del text
    msgs = [f"Spec validation failed in {path}:"]
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"])
        msgs.append(
            f"  [{loc}]  {e['msg']}  (got: {e.get('input', '?')!r})"
        )
    return "\n".join(msgs)


def _format_dict(err: ValidationError) -> str:
    msgs = ["Spec validation failed:"]
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"])
        msgs.append(
            f"  [{loc}]  {e['msg']}  (got: {e.get('input', '?')!r})"
        )
    return "\n".join(msgs)
