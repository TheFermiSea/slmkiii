"""CLI for AUM file inspection — `slmkiii-aum inspect-mapping|inspect-session`."""

from __future__ import annotations

import argparse

from slmkiii.aum.codec import AumMsgType
from slmkiii.aum.midimap import read_aum_midimap
from slmkiii.aum.session import read_aum_session


def _cmd_inspect_mapping(path: str) -> None:
    result = read_aum_midimap(path)
    print(f"Collection: {result['collection_name']}")
    print(f"Parameters: {len(result['mappings'])}")
    print()
    for m in sorted(result['mappings'], key=lambda x: x.parameter_name):
        status = 'ON ' if m.enabled else 'off'
        msg = 'CC' if m.msg_type == AumMsgType.CC else f'type{m.msg_type}'
        print(f"  [{status}] {m.parameter_name:<30s} {msg}{m.cc_number:<4d} ch{m.channel + 1}")


def _cmd_inspect_session(path: str) -> None:
    session = read_aum_session(path)
    print(f"Session: {session.title}")
    print(f"Version: {session.version}  Sample Rate: {session.sample_rate}  Tempo: {session.tempo}")
    print(f"Channels: {len(session.channels)}")
    print()
    for ch in session.channels:
        mute_str = ' [MUTED]' if ch.muted else ''
        solo_str = ' [SOLO]' if ch.soloed else ''
        title = ch.title or '(untitled)'
        print(f"  Ch {ch.index}: {title} ({ch.channel_type})"
              f" level={ch.fader_level:.2f}{mute_str}{solo_str}")
        for p in ch.plugins:
            au_id = f"{p.au_type}/{p.au_subtype}/{p.au_manufacturer}" if p.au_type else p.node_type
            print(f"    └─ {p.component_name or p.node_type}  [{au_id}]")


def main():
    parser = argparse.ArgumentParser(prog='slmkiii-aum',
                                     description='AUM file analysis tools')
    sub = parser.add_subparsers(dest='command')
    p_map = sub.add_parser('inspect-mapping',
                           help='Decode and display an AUM MIDI mapping file')
    p_map.add_argument('path')
    p_sess = sub.add_parser('inspect-session',
                            help='Decode and display an AUM session file')
    p_sess.add_argument('path')

    args = parser.parse_args()
    if args.command == 'inspect-mapping':
        _cmd_inspect_mapping(args.path)
    elif args.command == 'inspect-session':
        _cmd_inspect_session(args.path)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
