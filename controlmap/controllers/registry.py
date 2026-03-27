"""Load controller profiles from JSON data files."""
from __future__ import annotations

import json
from pathlib import Path

from controlmap.controllers import ControllerProfile, ControlGroup, Feature
from controlmap.model import ControlType

_DATA_DIR = Path(__file__).parent / 'data'
_CACHE: dict[str, ControllerProfile] = {}

_CONTROL_TYPE_MAP = {
    'continuous': ControlType.CONTINUOUS,
    'momentary': ControlType.MOMENTARY,
    'velocity': ControlType.VELOCITY,
    'toggle': ControlType.TOGGLE,
}

_FEATURE_MAP = {
    'screens': Feature.SCREENS,
    'rgb_leds': Feature.RGB_LEDS,
    'velocity_pads': Feature.VELOCITY_PADS,
    'aftertouch': Feature.AFTERTOUCH,
    'sequencer': Feature.SEQUENCER,
    'motorized_faders': Feature.MOTORIZED_FADERS,
}


def load_controller(controller_id: str) -> ControllerProfile:
    """Load a controller profile by ID.

    Profiles are JSON files in controlmap/controllers/data/.
    """
    if controller_id in _CACHE:
        return _CACHE[controller_id]

    path = _DATA_DIR / f'{controller_id}.json'
    if not path.exists():
        raise FileNotFoundError(
            f'No controller profile found: {path}')

    with open(path) as f:
        data = json.load(f)

    groups = []
    for g in data['control_groups']:
        groups.append(ControlGroup(
            name=g['name'],
            count=g['count'],
            control_type=_CONTROL_TYPE_MAP[g['control_type']],
            pages_hardware=g.get('pages_hardware', 1),
            has_display=g.get('has_display', False),
            display_chars=g.get('display_chars', 0),
        ))

    features = {_FEATURE_MAP[f] for f in data.get('features', [])}

    profile = ControllerProfile(
        id=data['id'],
        name=data['name'],
        control_groups=groups,
        features=features,
    )
    _CACHE[controller_id] = profile
    return profile
