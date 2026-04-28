# iPad validation test harness

Three small Mozaic scripts that gate the architecture of `slmkiii`'s iPad-side
runtime. **You must run these on iPad before commits c11+ are written.**

The outcomes determine which architecture branch we take. See `RESULTS.md`
(written by you after running) for the decision.

## Why these tests exist

The slmkiii Mozaic compiler design hinges on three behaviors that are not
fully documented and have shifted between Mozaic builds:

1. **`array[var]` indirect indexing**. Reliable indirect array reads enable
   a small, generic `slmk_runtime.moz` that interprets per-spec data tables.
   If broken, the runtime must be regenerated per spec with fully-unrolled
   `if/elseif` dispatch — bigger files, but still works.

2. **SysEx output throughput**. The runtime sends SysEx for every screen
   update + LED change. We need to know the steady-state ceiling so the
   compile-time burst-stagger (`SendMIDICC ..., i*5`) is correctly tuned.

3. **Cross-instance SysEx routing in AUM**. The runtime+data architecture
   uses a custom `F0 7D 53 4C 4D 4B` private protocol between two Mozaic
   instances. If AUM doesn't route this between instances, we must collapse
   to a single-instance design.

## Setup (one-time)

1. Open AUM on iPad.
2. Make sure Mozaic AUv3 is installed.
3. Use one of the file-transfer paths to copy these `.moz` files to the iPad:
   - **Files.app share**: drop them into AUM's Documents folder
   - `slmkiii-controller push` (if the iPad is currently connected)
   - AirDrop directly into AUM
4. Once on the iPad, in any Mozaic AUv3 instance, tap the script icon and
   "Load" the .moz file.

## Test A — `array_var.moz` (~30s)

Tests whether `arr[var]` indirect indexing works.

1. Load `array_var.moz` into a Mozaic instance.
2. In Mozaic's Log pane, you should see lines like:
   ```
   -- array[var] test --
   map[0] = 10
   map[1] = 20
   ...
   map[7] = 80
   direct map[3] via var = 40
   map[j+1] via expr = 50
   ```
3. Send CC #20 (e.g. from any AUM "MIDI Control" source, or the SL MkIII
   knob 1 if you have InControl mode enabled). Try values 0, 1, 3, 7.
4. The log should show: `CC val=0 -> map[0] = 10`, `CC val=1 -> map[1] = 20`,
   `CC val=3 -> map[3] = 40`, `CC val=7 -> map[7] = 80`.

**Pass criteria:** all values match. Record "PASS — array[var] works" in
`RESULTS.md`.

**Failure modes:** see comment in `array_var.moz` for fallback architectures.

## Test B — `sysex_bw.moz` (~5min)

Measures sustained SysEx throughput.

1. Route Mozaic output to your SL MkIII InControl USB port (in AUM's MIDI
   matrix).
2. Load `sysex_bw.moz`. It will start sending 1 message per 100ms tick.
3. Send CC #21 with values: 1, 5, 10, 20, 50.
   ```
   CC #21 = 1   →  10 msgs/sec  (very light)
   CC #21 = 5   →  50 msgs/sec
   CC #21 = 10  →  100 msgs/sec
   CC #21 = 20  →  200 msgs/sec  (typical comfortable cap)
   CC #21 = 50  →  500 msgs/sec  (likely above ceiling)
   ```
4. Watch the SL MkIII screens: their values should keep updating smoothly.
   The first rate at which screens visibly stutter, freeze, or skip values
   = your **steady-state ceiling**.

**Record in `RESULTS.md`:** the highest rate that worked smoothly. We will
budget the runtime at 50% of this number.

## Test C — `runtime_data_proto.moz` (~2min)

Tests the cross-instance SysEx round-trip.

1. Add **two** Mozaic AUv3 instances to your AUM session.
2. In AUM's MIDI matrix, route:
   - Mozaic A output → Mozaic B input
   - Mozaic B output → Mozaic A input
3. Load `runtime_data_proto.moz` into BOTH instances.
4. Each instance should log on @OnLoad:
   ```
   requested idx=2
   ```
5. Each instance, on receiving the other's request, should log:
   ```
   got request idx=2, replying with 127
   ```
   (the value depends on which instance's `data` table it reads from)
6. Each instance, on receiving the reply, should log:
   ```
   got reply idx=2 val=127
   ```

**Pass criteria:** all 6 log lines appear (3 per instance). Record "PASS —
cross-instance SysEx round-trip works" in `RESULTS.md`.

**Failure modes:** see comment in `runtime_data_proto.moz`.

## After running

Fill in `RESULTS.md` with your observations. The values determine which
branch of the architecture we lock in for c11+.
