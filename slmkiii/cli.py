import argparse
import sys

from slmkiii import Template


def cmd_convert(args):
    t = Template(args.input)
    t.save(args.output)


def cmd_inspect(args):
    t = Template(args.path)
    print(t.summary())


def cmd_grid(args):
    t = Template(args.path)
    print(t.to_grid())


def cmd_diff(args):
    t1 = Template(args.path1)
    t2 = Template(args.path2)
    print(t1.diff_summary(t2))


def cmd_validate(args):
    t = Template(args.path)
    issues = t.validate()
    if issues:
        for issue in issues:
            print(issue)
        sys.exit(1)
    else:
        print("Valid")


def cmd_push(args):
    from slmkiii import midi
    from slmkiii.errors import ErrorMidiDeviceNotFound

    t = Template(args.path)
    slot = args.slot - 1
    try:
        midi.push_template(t, slot=slot)
    except ErrorMidiDeviceNotFound:
        print("Error: Novation SL MkIII not found. Is it connected and powered on?", file=sys.stderr)
        sys.exit(1)


def cmd_pull(args):
    from slmkiii import midi
    from slmkiii.errors import ErrorMidiDeviceNotFound

    slot = args.slot - 1
    try:
        t = midi.pull_template(slot=slot)
    except ErrorMidiDeviceNotFound:
        print("Error: Novation SL MkIII not found. Is it connected and powered on?", file=sys.stderr)
        sys.exit(1)
    t.save(args.output)


def cmd_ports(args):
    from slmkiii import midi

    ports = midi.list_midi_ports()
    print("Input ports:")
    for port in ports.get("input", []):
        print(f"  {port}")
    print("Output ports:")
    for port in ports.get("output", []):
        print(f"  {port}")


def main():
    parser = argparse.ArgumentParser(
        prog="slmkiii",
        description="CLI tool for Novation SL MkIII template management",
    )
    subparsers = parser.add_subparsers(dest="command")

    # convert
    p_convert = subparsers.add_parser("convert", help="Convert between syx and json formats")
    p_convert.add_argument("input", help="Input file path (.syx or .json)")
    p_convert.add_argument("output", help="Output file path (.syx or .json)")
    p_convert.set_defaults(func=cmd_convert)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Print template summary")
    p_inspect.add_argument("path", help="Template file path")
    p_inspect.set_defaults(func=cmd_inspect)

    # grid
    p_grid = subparsers.add_parser("grid", help="Print template grid layout")
    p_grid.add_argument("path", help="Template file path")
    p_grid.set_defaults(func=cmd_grid)

    # diff
    p_diff = subparsers.add_parser("diff", help="Show differences between two templates")
    p_diff.add_argument("path1", help="First template file path")
    p_diff.add_argument("path2", help="Second template file path")
    p_diff.set_defaults(func=cmd_diff)

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate a template")
    p_validate.add_argument("path", help="Template file path")
    p_validate.set_defaults(func=cmd_validate)

    # push
    p_push = subparsers.add_parser("push", help="Push template to SL MkIII")
    p_push.add_argument("path", help="Template file path")
    p_push.add_argument("--slot", type=int, choices=range(1, 9), default=1, help="Template slot (1-8)")
    p_push.set_defaults(func=cmd_push)

    # pull
    p_pull = subparsers.add_parser("pull", help="Pull template from SL MkIII")
    p_pull.add_argument("output", help="Output file path")
    p_pull.add_argument("--slot", type=int, choices=range(1, 9), default=1, help="Template slot (1-8)")
    p_pull.set_defaults(func=cmd_pull)

    # ports
    p_ports = subparsers.add_parser("ports", help="List available MIDI ports")
    p_ports.set_defaults(func=cmd_ports)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
