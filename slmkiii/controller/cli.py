"""Live controller CLI: `slmkiii-controller {run,generate-mappings,push-mappings}`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from slmkiii.aum import write_aum_midimap
from slmkiii.controller import runtime
from slmkiii.controller.aum_export import bindings_to_aum_mappings
from slmkiii.controller.pages import PROJECTS, get_pages, iter_aum_exports


def _cmd_generate_mappings(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for export in iter_aum_exports():
        mappings = bindings_to_aum_mappings(export.pages, expand_focus=True)
        path = out_dir / export.filename
        write_aum_midimap(export.au_identifier, mappings, path)
        print(f'  {len(mappings):3d} mappings -> {path}')
    return 0


def _cmd_push_mappings(args) -> int:
    from slmkiii.ipad_push import push_files
    out_dir = Path(args.out_dir)
    pairs: list[tuple[Path, str]] = []
    for export in iter_aum_exports():
        local = out_dir / export.filename
        if not local.exists():
            print(f'missing {local}; run generate-mappings first', file=sys.stderr)
            return 1
        pairs.append((local, f'/Documents/MIDI Mappings/Channel/{export.filename}'))
    print('Pushing to iPad AUM ...')
    for path in push_files(pairs):
        print(f'  {path}')
    return 0


def _cmd_run(args) -> int:
    pages = get_pages(args.project)
    return runtime.run(pages, output_port=args.output_port)


def main():
    parser = argparse.ArgumentParser(
        prog='slmkiii-controller',
        description='SL MkIII <-> AUM live controller')
    sub = parser.add_subparsers(dest='command')

    p_run = sub.add_parser('run', help='Run the live controller')
    p_run.add_argument('--project', default='default',
                       choices=sorted(PROJECTS),
                       help='Page-set to load (default: all projects)')
    p_run.add_argument('--output-port', default='iPad',
                       help='mido output port name (default: iPad / iDAM)')
    p_run.set_defaults(func=_cmd_run)

    p_gen = sub.add_parser('generate-mappings',
                           help='Write .aum_midimap files matching the controller CCs')
    p_gen.add_argument('--out-dir', default='output')
    p_gen.set_defaults(func=_cmd_generate_mappings)

    p_push = sub.add_parser('push-mappings',
                            help='Push generated .aum_midimap files to AUM on iPad over USB')
    p_push.add_argument('--out-dir', default='output')
    p_push.set_defaults(func=_cmd_push_mappings)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
