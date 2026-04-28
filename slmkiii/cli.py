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
    a = Template(args.path1)
    b = Template(args.path2)
    diff = a.diff(b)
    if not diff:
        print("Templates are identical")
        return
    for line in diff:
        print(line)


def cmd_validate(args):
    try:
        Template(args.path)
        print("Valid")
    except Exception as e:
        print(f"Invalid: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_push(args):
    from slmkiii import midi
    from slmkiii.errors import ErrorMidiDeviceNotFound
    t = Template(args.path)
    try:
        midi.push_template(t, slot=args.slot - 1)
        print(f"pushed → SL MkIII slot {args.slot}")
    except ErrorMidiDeviceNotFound as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pull(args):
    from slmkiii import midi
    from slmkiii.errors import ErrorMidiDeviceNotFound
    try:
        t = midi.pull_template(slot=args.slot - 1)
        t.save(args.output)
        print(f"pulled SL MkIII slot {args.slot} → {args.output}")
    except ErrorMidiDeviceNotFound as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_ports(args):
    import mido
    print("Input ports:")
    for name in mido.get_input_names():
        print(f"  {name}")
    print("Output ports:")
    for name in mido.get_output_names():
        print(f"  {name}")


def main():
    parser = argparse.ArgumentParser(
        prog="slmkiii",
        description="CLI tool for Novation SL MkIII template management",
    )
    subparsers = parser.add_subparsers(dest="command")

    p_convert = subparsers.add_parser("convert", help="Convert between syx and json formats")
    p_convert.add_argument("input")
    p_convert.add_argument("output")
    p_convert.set_defaults(func=cmd_convert)

    p_inspect = subparsers.add_parser("inspect", help="Print template summary")
    p_inspect.add_argument("path")
    p_inspect.set_defaults(func=cmd_inspect)

    p_grid = subparsers.add_parser("grid", help="Print template grid layout")
    p_grid.add_argument("path")
    p_grid.set_defaults(func=cmd_grid)

    p_diff = subparsers.add_parser("diff", help="Show differences between two templates")
    p_diff.add_argument("path1")
    p_diff.add_argument("path2")
    p_diff.set_defaults(func=cmd_diff)

    p_validate = subparsers.add_parser("validate", help="Validate a template")
    p_validate.add_argument("path")
    p_validate.set_defaults(func=cmd_validate)

    p_push = subparsers.add_parser("push", help="Push template to SL MkIII")
    p_push.add_argument("path")
    p_push.add_argument("--slot", type=int, choices=range(1, 9), default=1)
    p_push.set_defaults(func=cmd_push)

    p_pull = subparsers.add_parser("pull", help="Pull template from SL MkIII")
    p_pull.add_argument("output")
    p_pull.add_argument("--slot", type=int, choices=range(1, 9), default=1)
    p_pull.set_defaults(func=cmd_pull)

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
