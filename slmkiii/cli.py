import argparse
import contextlib
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


# ── surface subcommands ──────────────────────────────────────────────────────


def cmd_surface_compile(args):
    """Compile a YAML/JSON spec into .syx + .aum_midimap + .mozaic artifacts."""
    from pathlib import Path
    from controlmap import compile_mapping
    from controlmap.spec_loader import load_spec
    from controlmap.emitters.slmkiii_emitter import SlMkIIIEmitter
    from controlmap.emitters.aum_emitter import AumEmitter
    from controlmap.mozaic import pack_moz_file

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = load_spec(args.spec)
    print(f"spec: {spec.name} | controller={spec.controller_id} plugin={spec.plugin_id}")

    resolved = compile_mapping(spec)
    print(f"compiled: {resolved.metadata['param_count']} params, "
          f"{resolved.metadata['page_count']} pages")

    syx_paths = SlMkIIIEmitter().emit(resolved, out_dir)
    for p in syx_paths:
        print(f"  → {p}")

    map_paths = AumEmitter().emit(resolved, out_dir)
    for p in map_paths:
        print(f"  → {p}")

    bridge_src = Path(__file__).parent.parent / 'controlmap' / 'mozaic' / 'slmk_bridge.moz'
    bridge_out = out_dir / 'SLMK-BRIDGE.mozaic'
    pack_moz_file(bridge_src, bridge_out, 'SLMK-BRIDGE')
    print(f"  → {bridge_out}")


def cmd_surface_push(args):
    """Compile (if needed) and push artifacts to SL MkIII + iPad/AUM."""
    from pathlib import Path
    from controlmap.spec_loader import load_spec

    spec = load_spec(args.spec)
    out_dir = Path(args.out_dir)

    syx_paths = sorted(out_dir.glob(f'{spec.name}*.syx'))
    map_paths = sorted(out_dir.glob(f'{spec.name}*.aum_midimap'))
    mozaic_path = out_dir / 'SLMK-BRIDGE.mozaic'

    needs_compile = (not syx_paths or not map_paths or not mozaic_path.exists()
                     or args.force_compile)
    if needs_compile:
        compile_args = argparse.Namespace(spec=args.spec, out_dir=str(out_dir))
        cmd_surface_compile(compile_args)
        syx_paths = sorted(out_dir.glob(f'{spec.name}*.syx'))
        map_paths = sorted(out_dir.glob(f'{spec.name}*.aum_midimap'))

    if not args.skip_slmkiii:
        from slmkiii import Template, midi
        from slmkiii.errors import ErrorMidiDeviceNotFound
        try:
            for i, syx in enumerate(syx_paths):
                t = Template(str(syx))
                midi.push_template(t, slot=args.slot - 1 + i)
                print(f"pushed {syx.name} → SL MkIII slot {args.slot + i}")
        except ErrorMidiDeviceNotFound:
            print("warning: SL MkIII not connected; skipped template push",
                  file=sys.stderr)

    if not args.skip_ipad:
        from controlmap.ipad_push import push_files
        # Channel-level mappings live in /Documents/MIDI Mappings/Channel/
        pairs = [(p, f'/Documents/MIDI Mappings/Channel/{p.name}')
                 for p in map_paths]
        pairs.append((mozaic_path, f'/Documents/{mozaic_path.name}'))
        try:
            written = push_files(pairs, bundle_id=args.aum_bundle)
            for w in written:
                print(f"pushed → {args.aum_bundle} {w}")
        except Exception as e:
            print(f"warning: iPad push failed: {e}", file=sys.stderr)


def cmd_surface_run(args):
    """Start the live surface daemon for a compiled spec."""
    from controlmap import compile_mapping
    from controlmap.spec_loader import load_spec
    from controlmap.surface import ControlSurface

    spec = load_spec(args.spec)
    resolved = compile_mapping(spec)

    surface = ControlSurface(
        resolved,
        midi_output=args.ipad_port,
        feedback_port=args.feedback_port or args.ipad_port,
        spec_path=args.spec if not args.no_hot_reload else None,
    )
    surface.run()


@contextlib.contextmanager
def _bridge_ports(name: str, duplex: bool = True):
    """Open mido I/O port(s) for the iPad/bridge and close them on exit."""
    import mido
    port_out = mido.open_output(name)
    port_in = mido.open_input(name) if duplex else None
    try:
        yield port_out, port_in
    finally:
        port_out.close()
        if port_in is not None:
            port_in.close()


def cmd_surface_monitor(args):
    """Tail bridge events on the iPad port. Supports pre-sending commands
    (HELLO, GET_VALUES, GET_HEALTH, PAGE, SCENE_SAVE/RECALL) before listening.
    """
    import signal
    import time
    import mido
    from controlmap import bridge_protocol as bp

    pre_sends: list[tuple[str, mido.Message]] = []
    if args.hello:
        pre_sends.append(('HELLO', bp.hello()))
    if args.get_health:
        pre_sends.append(('GET_HEALTH', bp.get_health()))
    if args.get_values:
        pre_sends.append(('GET_VALUES', bp.get_values()))
    if args.scene_recall is not None:
        pre_sends.append((f'SCENE_RECALL {args.scene_recall}',
                          bp.scene_recall(args.scene_recall)))
    if args.scene_save is not None:
        pre_sends.append((f'SCENE_SAVE {args.scene_save}',
                          bp.scene_save(args.scene_save)))
    if args.page is not None:
        pre_sends.append((f'PAGE {args.page}', bp.page(args.page)))

    with _bridge_ports(args.ipad_port) as (port_out, port_in):
        for label, msg in pre_sends:
            port_out.send(msg)
            print(f'sent {label}')

        running = True

        def stop(_sig, _frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, stop)
        print(f'monitor: listening on {args.ipad_port} (Ctrl-C to stop)')
        while running:
            for msg in port_in.iter_pending():
                event = bp.parse_event(msg)
                if event is not None:
                    print(event)
                elif args.verbose and msg.type == 'sysex':
                    print(f'raw sysex: {bytes(msg.data).hex()}')
            time.sleep(0.01)


def cmd_surface_scene(args):
    """Send SCENE_SAVE or SCENE_RECALL to the bridge."""
    from controlmap import bridge_protocol as bp

    with _bridge_ports(args.ipad_port, duplex=False) as (port, _):
        if args.action == 'save':
            port.send(bp.scene_save(args.scene))
        else:
            port.send(bp.scene_recall(args.scene))
    print(f'scene {args.action} {args.scene} sent')


def cmd_surface_health(args):
    """Request and display a health snapshot from the bridge."""
    import time
    from controlmap import bridge_protocol as bp

    with _bridge_ports(args.ipad_port) as (port_out, port_in):
        port_out.send(bp.get_health())
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            for msg in port_in.iter_pending():
                event = bp.parse_event(msg)
                if isinstance(event, bp.Health):
                    print(f'msgs_in:    {event.msgs_in}')
                    print(f'msgs_out:   {event.msgs_out}')
                    print(f'routes:     {event.routes}')
                    occupied = [i for i in range(8) if event.has_scene(i)]
                    print(f'scenes:     {event.scene_mask:08b} (occupied: {occupied})')
                    return
            time.sleep(0.01)
    print(f'timeout: no HEALTH reply on {args.ipad_port}', file=sys.stderr)
    sys.exit(1)


def cmd_surface_inspect(args):
    """Print a summary of what the spec compiles into. No I/O."""
    from controlmap import compile_mapping
    from controlmap.spec_loader import load_spec

    spec = load_spec(args.spec)
    resolved = compile_mapping(spec)

    print(f"spec:        {spec.name}")
    print(f"controller:  {spec.controller_id}")
    print(f"plugin:      {spec.plugin_id}")
    print(f"target:      {spec.target_id}")
    print(f"channel:     {spec.midi_channel_base}")
    print(f"params:      {resolved.metadata['param_count']}")
    print(f"pages:       {resolved.metadata['page_count']}")
    print()
    for page in resolved.page_set.pages:
        print(f"  Page {page.index + 1}: {page.name} ({len(page.bindings)} bindings)")
        for b in page.bindings[:8]:
            kind = 'CC' if b.msg_type.name == 'CC' else 'Note'
            data1 = b.midi_cc if b.msg_type.name == 'CC' else b.midi_note
            print(f"    {b.slot.group}[{b.slot.index}] -> "
                  f"{kind}{data1} ch{b.midi_channel}  {b.param.display_name or b.param.param_path}")
        if len(page.bindings) > 8:
            print(f"    ... +{len(page.bindings) - 8} more")


def _add_surface_subparsers(subparsers):
    p_surface = subparsers.add_parser(
        "surface",
        help="Compile, push, or run a controlmap spec end-to-end",
    )
    surface_subs = p_surface.add_subparsers(dest="surface_cmd")
    surface_subs.required = True

    p_compile = surface_subs.add_parser(
        "compile", help="Compile a spec into .syx, .aum_midimap, and .mozaic artifacts")
    p_compile.add_argument("spec", help="Path to YAML/JSON mapping spec")
    p_compile.add_argument(
        "--out-dir", default="build", help="Output directory (default: build/)")
    p_compile.set_defaults(func=cmd_surface_compile)

    p_push = surface_subs.add_parser(
        "push", help="Push compiled artifacts to SL MkIII and iPad/AUM")
    p_push.add_argument("spec", help="Path to YAML/JSON mapping spec")
    p_push.add_argument(
        "--out-dir", default="build", help="Build directory (default: build/)")
    p_push.add_argument(
        "--slot", type=int, choices=range(1, 9), default=1,
        help="SL MkIII template slot (1-8)")
    p_push.add_argument(
        "--aum-bundle", default="com.kymatica.AUM",
        help="iPad app bundle id to receive .mozaic + .aum_midimap (default: com.kymatica.AUM)")
    p_push.add_argument(
        "--skip-slmkiii", action="store_true", help="Don't push to SL MkIII")
    p_push.add_argument(
        "--skip-ipad", action="store_true", help="Don't push to iPad")
    p_push.add_argument(
        "--force-compile", action="store_true",
        help="Re-compile artifacts even if they exist")
    p_push.set_defaults(func=cmd_surface_push)

    p_run = surface_subs.add_parser(
        "run", help="Run the live surface daemon")
    p_run.add_argument("spec", help="Path to YAML/JSON mapping spec")
    p_run.add_argument(
        "--ipad-port", default="iPad",
        help="MIDI port name for iDAM I/O (default: iPad)")
    p_run.add_argument(
        "--feedback-port", default=None,
        help="Separate MIDI input port for bridge echoes (default: same as --ipad-port)")
    p_run.add_argument(
        "--no-hot-reload", action="store_true",
        help="Disable automatic reload on spec file change")
    p_run.set_defaults(func=cmd_surface_run)

    p_inspect = surface_subs.add_parser(
        "inspect", help="Show what a spec compiles to (no I/O)")
    p_inspect.add_argument("spec", help="Path to YAML/JSON mapping spec")
    p_inspect.set_defaults(func=cmd_surface_inspect)

    p_monitor = surface_subs.add_parser(
        "monitor", help="Tail bridge events on the iPad port (for debugging)")
    p_monitor.add_argument(
        "--ipad-port", default="iPad",
        help="MIDI port name for iDAM I/O (default: iPad)")
    p_monitor.add_argument("--hello", action="store_true",
                           help="Send HELLO before listening")
    p_monitor.add_argument("--get-values", action="store_true",
                           help="Request cached CC values from bridge")
    p_monitor.add_argument("--get-health", action="store_true",
                           help="Request a health snapshot")
    p_monitor.add_argument("--page", type=int, default=None,
                           help="Send PAGE command before listening")
    p_monitor.add_argument("--scene-save", type=int, default=None,
                           help="Send SCENE_SAVE for scene N before listening")
    p_monitor.add_argument("--scene-recall", type=int, default=None,
                           help="Send SCENE_RECALL for scene N before listening")
    p_monitor.add_argument("-v", "--verbose", action="store_true",
                           help="Also print raw sysex bytes")
    p_monitor.set_defaults(func=cmd_surface_monitor)

    p_scene = surface_subs.add_parser(
        "scene", help="Save or recall a scene on the bridge")
    p_scene.add_argument("action", choices=["save", "recall"])
    p_scene.add_argument("scene", type=int, help="Scene index 0-7")
    p_scene.add_argument(
        "--ipad-port", default="iPad", help="MIDI port (default: iPad)")
    p_scene.set_defaults(func=cmd_surface_scene)

    p_health = surface_subs.add_parser(
        "health", help="Request a health snapshot from the bridge")
    p_health.add_argument(
        "--ipad-port", default="iPad", help="MIDI port (default: iPad)")
    p_health.set_defaults(func=cmd_surface_health)


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

    # surface (nested subcommands for the controlmap workflow)
    _add_surface_subparsers(subparsers)

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
