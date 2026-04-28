"""NSKeyedArchiver binary plist decoder/encoder.

AUM persists session and mapping state in NSKeyedArchiver-format binary plists
(the same format Apple Cocoa apps use). The standard library's `plistlib`
parses the wire format but does not resolve the UID-graph or NSDictionary
key/value pairing, so this module wraps it.
"""

from __future__ import annotations

import plistlib

# NSKeyedArchiver always stores '$null' at $objects[0].
_NS_NULL = '$null'


def _resolve_uid(objects: list, val, _seen: set[int] | None = None):
    """Recursively resolve NSKeyedArchiver UID references to Python objects."""
    if _seen is None:
        _seen = set()
    if isinstance(val, plistlib.UID):
        uid_int = int(val)
        if uid_int in _seen:
            return None  # break circular reference
        _seen.add(uid_int)
        try:
            return _resolve_uid(objects, objects[val], _seen)
        finally:
            _seen.discard(uid_int)
    elif isinstance(val, dict):
        if 'NS.keys' in val and 'NS.objects' in val:
            keys = [_resolve_uid(objects, k, _seen) for k in val['NS.keys']]
            vals = [_resolve_uid(objects, v, _seen) for v in val['NS.objects']]
            return dict(zip(keys, vals))
        elif 'NS.objects' in val:
            return [_resolve_uid(objects, o, _seen) for o in val['NS.objects']]
        elif '$classname' in val or '$classes' in val:
            return None
        else:
            return {k: _resolve_uid(objects, v, _seen)
                    for k, v in val.items() if not k.startswith('$')}
    elif isinstance(val, list):
        return [_resolve_uid(objects, item, _seen) for item in val]
    else:
        return val


def decode_keyed_archiver(data: bytes) -> dict:
    """Decode an NSKeyedArchiver binary plist to a Python dict."""
    plist = plistlib.loads(data)
    if plist.get('$archiver') != 'NSKeyedArchiver':
        raise ValueError('Not an NSKeyedArchiver plist')
    objects = plist['$objects']
    root_uid = plist['$top']['root']
    return _resolve_uid(objects, root_uid)


def deref_uid(objects: list, val):
    """Resolve a single UID without recursing into nested dicts.

    Useful when walking the raw `$objects` graph from a session file where
    you want to inspect dict shape (NS.keys / NS.objects) yourself.
    """
    if isinstance(val, plistlib.UID):
        return objects[val]
    return val


class ArchiverBuilder:
    """Builds an NSKeyedArchiver binary plist from Python objects."""

    def __init__(self):
        self._objects = ['$null']  # index 0 is always $null
        self._class_cache: dict[str, plistlib.UID] = {}
        self._scalar_cache: dict[tuple, plistlib.UID] = {}

    def _add_object(self, obj) -> plistlib.UID:
        idx = len(self._objects)
        self._objects.append(obj)
        return plistlib.UID(idx)

    def _get_class_uid(self, classname: str,
                       classes: list[str] | None = None) -> plistlib.UID:
        if classname in self._class_cache:
            return self._class_cache[classname]
        if classes is None:
            classes = [classname, 'NSObject']
        uid = self._add_object({
            '$classes': classes,
            '$classname': classname,
        })
        self._class_cache[classname] = uid
        return uid

    def _add_scalar(self, val) -> plistlib.UID:
        # bool must be in the key alongside the value: bool is a subclass of
        # int and plistlib encodes the two differently in binary plists.
        cache_key = (type(val), val)
        if cache_key in self._scalar_cache:
            return self._scalar_cache[cache_key]
        uid = self._add_object(val)
        self._scalar_cache[cache_key] = uid
        return uid

    def encode_value(self, val, *, mutable_dict: bool = False) -> plistlib.UID:
        """Encode a Python value as an NSKeyedArchiver object reference."""
        if val is None:
            return plistlib.UID(0)  # $null
        elif isinstance(val, plistlib.UID):
            return val
        elif isinstance(val, (bool, int, float, str)):
            return self._add_scalar(val)
        elif isinstance(val, dict):
            return self._encode_dict(val, mutable=mutable_dict)
        elif isinstance(val, list):
            return self._encode_array(val)
        else:
            return self._add_object(val)

    def encode_ns_mutable_data(self, data: bytes) -> plistlib.UID:
        """Encode raw bytes as NSMutableData; returns a UID embeddable as a value."""
        cls = self._get_class_uid(
            'NSMutableData', ['NSMutableData', 'NSData', 'NSObject'])
        return self._add_object({'NS.data': data, '$class': cls})

    def _encode_dict(self, d: dict, *, mutable: bool = False) -> plistlib.UID:
        key_uids = [self.encode_value(k) for k in d.keys()]
        val_uids = [self.encode_value(v) for v in d.values()]
        if mutable:
            class_uid = self._get_class_uid(
                'NSMutableDictionary',
                ['NSMutableDictionary', 'NSDictionary', 'NSObject'])
        else:
            class_uid = self._get_class_uid('NSDictionary')
        return self._add_object({
            'NS.keys': key_uids,
            'NS.objects': val_uids,
            '$class': class_uid,
        })

    def _encode_array(self, arr: list) -> plistlib.UID:
        item_uids = [self.encode_value(v) for v in arr]
        return self._add_object({
            'NS.objects': item_uids,
            '$class': self._get_class_uid(
                'NSMutableArray',
                ['NSMutableArray', 'NSArray', 'NSObject']),
        })

    def build(self, root) -> bytes:
        root_uid = self.encode_value(root, mutable_dict=True)
        plist = {
            '$archiver': 'NSKeyedArchiver',
            '$version': 100000,
            '$top': {'root': root_uid},
            '$objects': self._objects,
        }
        return plistlib.dumps(plist, fmt=plistlib.FMT_BINARY)
