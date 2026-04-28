"""CLI for spec validation and JSON Schema export.

Usage::

    slmkiii-spec emit-schema             # print JSON Schema (drives editors)
    slmkiii-spec validate spec.yaml      # validate a spec, exit 1 on failure
"""

from __future__ import annotations

import argparse
import json
import sys

from slmkiii.spec.loader import SpecError, load_spec
from slmkiii.spec.models import MappingSpecModel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slmkiii-spec")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("emit-schema", help="print JSON Schema for MappingSpecModel")

    p_val = sub.add_parser("validate", help="validate a YAML spec file")
    p_val.add_argument("path", help="path to spec.yaml")

    args = parser.parse_args(argv)

    if args.cmd == "emit-schema":
        schema = MappingSpecModel.model_json_schema()
        json.dump(schema, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "validate":
        try:
            spec = load_spec(args.path)
        except SpecError as e:
            print(str(e), file=sys.stderr)
            return 1
        print(f"OK: {spec.name} ({len(spec.pages)} page(s))")
        return 0

    parser.error(f"unknown command: {args.cmd}")
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
