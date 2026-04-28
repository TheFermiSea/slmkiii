# iPad validation results

**Status: PENDING USER RUN**

When you have a few minutes with your iPad, run the three tests in `README.md`
and paste your observations below. Each result feeds a specific architecture
decision in commits c11–c16.

---

## Test A — `array_var.moz`

Date: _____
Mozaic version: _____  (Settings → About in the Mozaic AUv3)

Observed log output (paste full Log contents):
```

```

Outcome (circle one):
- [ ] PASS — `array[var]` works correctly. ARCHITECTURE: hand-written runtime + generated data tables.
- [ ] FAIL (parser error) — Mozaic rejected `map[i]`. ARCHITECTURE: per-spec monolithic runtime, fully-unrolled if/elseif.
- [ ] FAIL (silent zeros) — indirect read returns 0. ARCHITECTURE: literal-index codegen with if/elseif on idx.
- [ ] FAIL (crash/stall) — Mozaic became unresponsive. ARCHITECTURE: fully unrolled.

Notes:

---

## Test B — `sysex_bw.moz`

Steady-state ceiling: _____ msgs/sec
(set CC#21 to N → got N×10 msgs/sec, observed smooth at: _____ )

Notes (any drift, missed SysEx, USB warning):

---

## Test C — `runtime_data_proto.moz`

Routing in AUM (describe how you wired Mozaic A ↔ Mozaic B):

Observed log on instance A:
```

```

Observed log on instance B:
```

```

Outcome:
- [ ] PASS — cross-instance round-trip works. Use runtime+data split.
- [ ] FAIL — @OnSysex doesn't fire on the other instance. Use single-instance runtime.

Notes:

---

## Architecture decision (after all three filled)

Based on the above, the iPad-side architecture for `slmkiii.mozaic` is:
- [ ] **Standard:** hand-written `slmk_runtime.moz` + generated `slmk_<spec>_data.moz`, communicating via the `F0 7D 53 4C 4D 4B` protocol between two Mozaic AUv3 instances.
- [ ] **Single-instance:** combined `slmk_<spec>.moz` with both runtime and data inlined. Larger files, no cross-instance routing required.
- [ ] **Fully-unrolled:** per-spec runtime with explicit `if/elseif` dispatch, no array-driven dispatch tables. Simplest, largest files.
