"""MIDI bridge — forward messages between ports.

Routes MIDI from hardware controllers to targets (iPad via iDAM,
network sessions, etc.) with optional message filtering.
"""
from __future__ import annotations

import signal
import time

import mido


def bridge(
    inputs: list[str],
    outputs: list[str],
    passthrough: bool = True,
) -> None:
    """Forward MIDI messages from input ports to output ports.

    Runs until interrupted (Ctrl-C).

    Args:
        inputs: Input port names to listen on.
        outputs: Output port names to forward to.
        passthrough: If True, forward all message types.
    """
    in_ports = []
    out_ports = []

    try:
        for name in inputs:
            in_ports.append(mido.open_input(name))
            print(f'  IN:  {name}')
        for name in outputs:
            out_ports.append(mido.open_output(name))
            print(f'  OUT: {name}')

        print(f'\nBridging {len(in_ports)} input(s) → {len(out_ports)} output(s). Ctrl-C to stop.')

        running = True

        def stop(sig, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)

        while running:
            for port in in_ports:
                for msg in port.iter_pending():
                    if passthrough or msg.type in ('note_on', 'note_off', 'control_change'):
                        for out in out_ports:
                            out.send(msg)
            time.sleep(0.001)

    finally:
        for p in in_ports:
            p.close()
        for p in out_ports:
            p.close()
        print('\nBridge stopped.')


def list_ports() -> dict[str, list[str]]:
    """List all available MIDI ports."""
    from slmkiii.midi import list_midi_ports
    return list_midi_ports()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='MIDI bridge — forward between ports')
    sub = parser.add_subparsers(dest='command')

    # list
    sub.add_parser('list', help='List all MIDI ports')

    # run
    p_run = sub.add_parser('run', help='Start the bridge')
    p_run.add_argument('-i', '--input', action='append', required=True,
                       help='Input port name (can specify multiple)')
    p_run.add_argument('-o', '--output', action='append', required=True,
                       help='Output port name (can specify multiple)')

    args = parser.parse_args()

    if args.command == 'list':
        ports = list_ports()
        print('INPUT PORTS:')
        for p in ports['input']:
            print(f'  {p}')
        print('\nOUTPUT PORTS:')
        for p in ports['output']:
            print(f'  {p}')

    elif args.command == 'run':
        bridge(args.input, args.output)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
