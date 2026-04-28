# Adding a new plugin project

The canonical workflow for wiring a new AUv3 plugin to the SL MkIII.

## 1. Author a YAML spec

Create `slmkiii/data/specs/<plugin>.yaml`. Minimal example:

```yaml
# yaml-language-server: $schema=../../../schemas/mapping-spec-v1.json
spec_version: 1
name: myplugin
label: MyPlugin
project_id: myplugin

plugin:
  name: My Plugin
  au_id: My Plugin.AU-<hex>     # find via slmkiii-aum inspect-session
  vendor: SomeVendor

defaults:
  channel: 5

modes:
  main:
    knobs:
      - { label: Cutoff,  cc: 20, channel: 5, param_path: filter.cutoff }
      - { label: Reso,    cc: 21, channel: 5, param_path: filter.reso   }
    faders:
      - { label: Volume,  cc: 7,  channel: 5, param_path: master.volume }

pages:
  - name: main
    label: My Plugin
    color: PURPLE
    mode: main
```

Validate it:

```sh
slmkiii-spec validate slmkiii/data/specs/myplugin.yaml
```

## 2. (Optional) parametric pages with focus_set

If your plugin has N similar instances (drums, voices, sends), use a
parametric mode + focus_set:

```yaml
modes:
  voice_focus:
    knobs:
      - { label: "V$n Cut",  cc: "$base+0", channel: 5, param_path: "voice$nparams.cutoff" }
      - { label: "V$n Reso", cc: "$base+1", channel: 5, param_path: "voice$nparams.reso"   }

pages:
  - name: voices
    label: Voices
    color: CYAN
    mode: voice_focus
    focus_set:
      - { id: voice1, label: Voice 1, vars: { n: 1, base: 30 } }
      - { id: voice2, label: Voice 2, vars: { n: 2, base: 32 } }
      - { id: voice3, label: Voice 3, vars: { n: 3, base: 34 } }
```

Substitution rules:
- `$name` is replaced by `vars[name]`. Longest-prefix wins, so
  `$nparams` with `vars = {n: 1}` becomes `1params`.
- `$base+N` / `$base-N` arithmetic supported in `cc` fields only.

## 3. Auto-discovery picks it up

`slmkiii.controller.pages.__init__._discover_yaml_specs()` scans
`slmkiii/data/specs/*.yaml` at controller startup. YAML wins over
any legacy `.py` page module of the same name.

## 4. Generate AUM mappings + push to iPad

```sh
slmkiii-controller generate-mappings   # writes output/SLMK MyPlugin.aum_midimap
slmkiii-controller push-mappings       # pymobiledevice3 USB push
```

In AUM on iPad, on the plugin instance: tap MIDI → load `SLMK MyPlugin`.

## 5. Run live (Mac dev mode)

```sh
slmkiii-controller run --project myplugin
```

The Mac controller renders SL screens/LEDs and forwards CC/notes via
iDAM to AUM.

## 6. Compile to Mozaic for iPad-only runtime

(Forthcoming once the iPad-validation results land — see
`tests/ipad_validation/RESULTS.md`.) The flow will be:

```sh
slmkiii-mozaic compile --project myplugin --out build/
slmkiii-mozaic push   --project myplugin   # pushes runtime + data .mozaic to iPad
```

User then loads both `.mozaic` files into AUM (in two Mozaic AUv3
instances, with data.output → runtime.input) and runs untethered.

## Migrating an existing Python page module

If you have an old `slmkiii/controller/pages/<name>.py` you want to
convert to YAML:

```sh
slmkiii-spec migrate \
  --module slmkiii.controller.pages.<name> \
  --out slmkiii/data/specs/<name>.yaml \
  --verify
```

`--verify` round-trips the YAML through `compile_spec` and byte-compares
the resulting `.aum_midimap` against what the original Python module
produces. Refuses to write if they diverge.

For parametric structure (e.g. battalion's 8 drum focus pages) the
migrate tool produces an expanded form; hand-edit afterwards to use
`focus_set` if you want the parametric ergonomic form. See
`slmkiii/data/specs/battalion.yaml` for a worked example.

## Schema reference

Run `slmkiii-spec emit-schema` to dump the JSON Schema. Editors that
support `# yaml-language-server: $schema=...` directives will give you
autocomplete + inline validation.
