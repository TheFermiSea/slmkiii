"""Live controller CLI: `slmkiii-controller {run,generate-mappings,push-mappings}`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from slmkiii.aum import AumMidiMapping, AumMsgType, write_aum_midimap
from slmkiii.aum.codec import MSG_TYPE_CC  # noqa: F401  (re-exported elsewhere)
from slmkiii.controller import runtime
from slmkiii.controller.config import Page
from slmkiii.controller.pages import PROJECTS, get_pages
from slmkiii.controller.pages import animoog as _animoog_pages
from slmkiii.controller.pages import battalion as _battalion_pages


# Maps each page-set module to (collection_name, output_filename).
_AUM_TARGETS: list[tuple[list[Page], str, str]] = [
    (_battalion_pages.PAGES + list(_battalion_pages.DRUM_FOCUS_PAGES.values()),
     _battalion_pages.AU_IDENTIFIER, 'SLMK Battalion.aum_midimap'),
    (_animoog_pages.PAGES,
     _animoog_pages.AU_IDENTIFIER, 'SLMK Animoog.aum_midimap'),
]


def _bindings_to_mappings(pages: list[Page]) -> list[AumMidiMapping]:
    """Walk pages, dedupe by (channel, cc, param_path), build AumMidiMappings."""
    seen: set[tuple[int, int, str]] = set()
    out: list[AumMidiMapping] = []
    for p in pages:
        for b in p.knobs + p.faders:
            if not b.param_path:
                continue
            key = (b.channel - 1, b.cc, b.param_path)
            if key in seen:
                continue
            seen.add(key)
            out.append(AumMidiMapping(
                parameter_name=b.param_path,
                cc_number=b.cc,
                channel=b.channel - 1,
                min_value=0.0,
                max_value=1.0,
                enabled=True,
                auto_toggle=False,
                msg_type=int(AumMsgType.CC),
            ))
    return out


def _cmd_generate_mappings(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for pages, collection, filename in _AUM_TARGETS:
        mappings = _bindings_to_mappings(pages)
        path = out_dir / filename
        write_aum_midimap(collection, mappings, path)
        print(f'  {len(mappings):3d} mappings -> {path}')
    return 0


def _cmd_push_mappings(args) -> int:
    from slmkiii.ipad_push import push_files
    out_dir = Path(args.out_dir)
    pairs: list[tuple[Path, str]] = []
    for _, _, filename in _AUM_TARGETS:
        local = out_dir / filename
        if not local.exists():
            print(f'missing {local}; run generate-mappings first', file=sys.stderr)
            return 1
        pairs.append((local, f'/Documents/MIDI Mappings/Channel/{filename}'))
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
