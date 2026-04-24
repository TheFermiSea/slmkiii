"""Load a MappingSpec from YAML or JSON.

The spec file is the operator-facing entry point — it describes a mapping
declaratively without requiring Python. Example:

    name: animoog_perform
    controller: sl_mkiii
    plugin: animoog_z
    target: aum
    midi_channel_base: 1
    parameters:
      - "filter.*"
      - "envelope.*"
    priorities:
      "filter.cutoff": 100
      "filter.resonance": 90

Either YAML or JSON is accepted (auto-detected by extension; YAML body works
for both since YAML is a JSON superset).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from controlmap.model import MappingSpec, RouteSpec


def load_spec(path: str | Path) -> MappingSpec:
    """Load a MappingSpec from a YAML or JSON file."""
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    suffix = p.suffix.lower()
    if suffix in {'.yaml', '.yml'}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as e:
            raise RuntimeError(
                "PyYAML is required for YAML specs. Install with `uv add pyyaml`."
            ) from e
        data = yaml.safe_load(text)
    elif suffix == '.json':
        data = json.loads(text)
    else:
        # Try YAML first (handles both), then JSON as fallback.
        try:
            import yaml  # type: ignore[import-not-found]
            data = yaml.safe_load(text)
        except ImportError:
            data = json.loads(text)
    return spec_from_dict(data, source=str(p))


def spec_from_dict(data: dict[str, Any], source: str | None = None) -> MappingSpec:
    """Build a MappingSpec from a parsed dict.

    Recognized keys (operator-friendly aliases supported):
        name              -> spec name
        controller        -> controller_id
        plugin            -> plugin_id
        target            -> target_id (default: "aum")
        midi_channel_base -> 1-indexed MIDI channel base (default: 1)
        parameters        -> param_selections (list of fnmatch globs)
        priorities        -> param_priorities (dict path -> int)
    """
    if not isinstance(data, dict):
        raise ValueError(f"spec root must be a mapping, got {type(data).__name__}")

    def require(key: str) -> Any:
        if key not in data:
            label = f' in {source}' if source else ''
            raise KeyError(f"spec missing required key '{key}'{label}")
        return data[key]

    name = require('name')
    controller = require('controller')
    plugin = require('plugin')
    target = data.get('target', 'aum')
    midi_channel_base = int(data.get('midi_channel_base', 1))

    raw_params = data.get('parameters', [])
    if not isinstance(raw_params, list):
        raise ValueError("'parameters' must be a list of glob patterns")
    param_selections = [str(p) for p in raw_params]

    raw_priorities = data.get('priorities', {})
    if not isinstance(raw_priorities, dict):
        raise ValueError("'priorities' must be a mapping of path -> int")
    param_priorities = {str(k): int(v) for k, v in raw_priorities.items()}

    raw_routes = data.get('routes', [])
    if not isinstance(raw_routes, list):
        raise ValueError("'routes' must be a list of route entries")
    routes: list[RouteSpec] = []
    for entry in raw_routes:
        if not isinstance(entry, dict):
            raise ValueError(f"route entry must be a mapping, got {type(entry).__name__}")

        def _get(key_a: str, key_b: str | None = None):
            if key_a in entry:
                return entry[key_a]
            if key_b is not None and key_b in entry:
                return entry[key_b]
            raise ValueError(f"route entry missing {key_a!r}: {entry!r}")

        try:
            routes.append(RouteSpec(
                page=int(_get('page')),
                in_channel=int(_get('in_channel', 'in_ch')),
                in_cc=int(_get('in_cc')),
                out_channel=int(_get('out_channel', 'out_ch')),
                out_cc=int(_get('out_cc')),
            ))
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(
                f"invalid route entry {entry!r}: {e}") from e

    return MappingSpec(
        name=str(name),
        controller_id=str(controller),
        plugin_id=str(plugin),
        target_id=str(target),
        param_selections=param_selections,
        param_priorities=param_priorities,
        midi_channel_base=midi_channel_base,
        routes=routes,
    )
