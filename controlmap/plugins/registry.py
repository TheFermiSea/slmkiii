"""Load plugin parameter databases from JSON data files."""
from __future__ import annotations

import json
from pathlib import Path

from controlmap.plugins import PluginParam, PluginParamDB
from controlmap.model import ParamType

_DATA_DIR = Path(__file__).parent / 'data'
_CACHE: dict[str, PluginParamDB] = {}

_PARAM_TYPE_MAP = {
    'continuous': ParamType.CONTINUOUS,
    'discrete': ParamType.DISCRETE,
    'toggle': ParamType.TOGGLE,
    'trigger': ParamType.TRIGGER,
}


def load_plugin(plugin_id: str) -> PluginParamDB:
    """Load a plugin parameter database by ID."""
    if plugin_id in _CACHE:
        return _CACHE[plugin_id]

    path = _DATA_DIR / f'{plugin_id}.json'
    if not path.exists():
        raise FileNotFoundError(
            f'No plugin database found: {path}')

    with open(path) as f:
        data = json.load(f)

    params = {}
    for group_name, group_data in data.get('groups', {}).items():
        for p in group_data.get('params', []):
            param = PluginParam(
                path=p['path'],
                display_name=p.get('display_name', p['path'].split('.')[-1][:9]),
                param_type=_PARAM_TYPE_MAP.get(
                    p.get('param_type', 'continuous'), ParamType.CONTINUOUS),
                group=group_name,
                priority=p.get('priority', 50),
                tags=p.get('tags', []),
            )
            params[param.path] = param

    db = PluginParamDB(
        plugin_id=data['plugin_id'],
        plugin_name=data['plugin_name'],
        au_identifier=data.get('au_identifier', ''),
        params=params,
    )
    _CACHE[plugin_id] = db
    return db
