# LPF2 connect timing — logic analysis & experiments

Notes from logic-analyzer captures and LMS-ESP32 connect experiments (Pybricks 4,
official LEGO hardware, third-party `lpf2.py` sensor). **Last updated: 2026-06.**

## What works (production path)

**Slow connect @ 2400 baud** (default `fast_connect=False` in `lpf2.py` v2.1+):

1. GPIO hello + DCM on RX (no UART during DCM — required on LMS-ESP32).
2. `slow_uart()` @ 2400, pad to ~450 ms total DCM window.
3. Send registration sequence (CMD_TYPE, CMD_MODES, CMD_SPEED, CMD_VERSION, MSG_INFO…).
4. Wait for hub `BYTE_ACK` (0x04).
5. Switch to `fast_uart()` @ 115200 for runtime.

Verified on LMS-ESP32 (rx=8, tx=7) with Pybricks 4 and official SPIKE. Fallback
after a failed fast attempt also works (full GPIO hello + DCM retry).

---

## Logic analyzer captures (official LEGO motor on PB4)

Files: `pybricks_4.0_motor.sal`, `pybricks_4.0_color.sal`, `pybricks_4.0_distance.sal`,
export `digital_motor.csv`.

Setup (from `.sal` meta):

- 4 MHz digital, hub TX/RX @ 115200 on analyzer channels
- Async @ 2400 on other channels during DCM

### DCM pattern (hub TX, official motor)

- ~20–22 cycles of **~16 ms high / ~2 ms low** (Pybricks 4).
- Final high **shortened to ~14 ms** (truncated last pulse).
- Total from negotiation start to probe: **~370–402 ms**.

### Hub CMD_SPEED probe (official motor → device)

Decoded from `digital_motor.csv` (sliding sync on raw edges):

```
0x52 0x00 0xc2 0x01 0x00 0x6e   = CMD_Baud(115200) @ 115200 baud
```

Timing:

| Event | Time (from capture start) |
|--------|---------------------------|
| Last DCM high ends | +402.1 ms |
| CMD_SPEED starts | +402.1 ms (~17 µs after high ends) |
| Probe duration | ~0.5 ms (6 bytes) |
| Official motor ACK 0x04 | ~+0.6 ms after probe |
| Motor registration @ 115200 | ~+6 ms after probe |

Saleae may show **framing errors** on the probe — line is idle-high before the
start bit; bytes still decode correctly from edge timing.

### Official device fast path (hub side)

Per [Pybricks UART protocol](https://github.com/pybricks/technical-info/blob/master/uart-protocol.md):

1. Hub finishes DCM.
2. Hub sends **CMD_SPEED @ 115200** to the device.
3. Device replies **BYTE_ACK** if it supports high-speed registration.
4. Device sends info sequence @ 115200.
5. Hub ACKs; both stay @ 115200.

If step 3 fails, hub **falls back to 2400** — which is exactly what our slow path uses.

---

## Third-party ESP32 experiments (fast_connect)

Goal: skip 2400 registration; open UART @ 115200, catch hub `CMD_SPEED`, ACK,
register @ 115200 (like official motor).

### Hard constraints (LMS-ESP32)

- **Do not open UART during GPIO DCM** — breaks connect (regression in v2.0).
- **Do not use `uart.init(rxbuf=…)`** — `EPERM` on LMS-ESP32; use fresh
  `machine.UART(...)`.
- Probe is **~0.5 ms** — 1-byte-per-ms polling can miss it entirely; bulk
  `uart.read()` required.
- 1 ms GPIO sampling: 14 ms truncated pulse often reads as **15 ms**; **16 ms**
  and **15 ms** pulses are not a reliable “last pulse” discriminator alone.

### Attempts (lpf2 versions)

| Version | Strategy | Result |
|---------|----------|--------|
| v2.0 | `uart.init` + buffers, fast heuristic `n<16` / `n>21` | EPERM; PB4 false triggers |
| v2.1 | Slow path only; removed fast heuristic | **Works** (SPIKE + PB4) |
| v2.2–v2.5 | Re-introduce `fast_connect`; exit DCM at drop 18–21 or @330–400 ms | CMD_SPEED not seen |
| v2.6 | Exit after drop 19; UART open @~355 ms; bulk read 150 ms | 7× `0x00` only, no `0x52` |

### Representative ESP32 logs

**v2.5** — exit too late (after drop 21 @ 386 ms):

```
connect: dcm fast exit @386ms drop 21 high 21ms
connect: no CMD_SPEED in 150ms (0 bytes)
→ slow fallback OK
```

**v2.6** — exit after drop 19 @ 355 ms (before drop 20):

```
connect: dcm listen from drop 20 @355ms
connect: no CMD_SPEED in 150ms (7 bytes)
connect: rx capture 0x0 0x0 0x0 0x0 0x0 0x0 0x0
→ slow fallback OK (@444ms DCM, ACK after 289ms)
```

After failed fast attempt, slow-path DCM often shows **21 ms highs** (drops 20+),
similar to official SPIKE DCM — hub state changes after missed negotiation.

### Latest conclusions (why fast_connect failed)

1. **Timing window is sub-millisecond on the wire** but our DCM loop uses
   **1 ms GPIO sleeps**. We cannot reliably open UART in the same instant the hub
   sends the probe (~17 µs after last high ends on official hardware).

2. **Opening UART earlier** (330 ms) sometimes captured bytes; opening **later**
   (386 ms) captured **nothing** — probe is a **single short burst**, not an
   ongoing stream.

3. **Third-party device may not receive `0x52` at all** — v2.6 at 355 ms got
   **seven `BYTE_SYNC` (0x00) bytes**, not `CMD_SPEED`. Possible explanations:
   - Hub sends SYNC to devices that did not ACK an earlier probe (already missed).
   - Hub treats unknown devices differently from official LEGO IDs.
   - Partial / mis-framed UART data at 115200 while line is still settling.

4. **Logic analyzer ≠ device RX path** — LA probes the port cleanly; ESP32 UART
   opens **after** pin mux from GPIO, with init latency, while TX may still be
   in GPIO drive from hello (`wrt_tx_pin(0)`). Separate RX/TX wires on PUP, but
   timing still differs from LA.

5. **Official motor** registers @ 115200 natively; **third-party** devices were
   always designed around **2400 registration + hub fallback** (v1.5 main branch).
   That path is what Pybricks documents as the fallback when high-speed negotiation
   fails.

6. **Guessing constants** (`CONNECT_FAST_MIN_MS`, drop index, `n<=15`) did not
   generalize across runs (drop 0 length varies 1–11 ms; 15 vs 16 ms highs).

### Tooling added

- `tests/measure_lpf2_timing.py` — `measure_once(uart_drop=N)` per plug-in.
- `LPF2.measure_fast_probe()` — DCM log + raw RX hex dump.
- `tests/hub_uart_sniffer.py` — Pybricks hub-side sniffer.

Use these if revisiting fast connect; tune from **measured** `CMD_SPEED` byte offset,
not fixed ms constants.

---

## Recommendation

- **Ship with `fast_connect=False`** (default). Use slow @2400 connect.
- **Boot-time**: call `connect()` immediately in `main.py` (see
  `test_lpf2_connect_boot.py`) so the hub does not time out waiting — this is
  about **2400 registration timing**, not the 115200 probe.
- **Do not merge fast_connect** until `measure_fast_probe()` reliably finds
  `0x52 0x00 0xc2 0x01 0x00 0x6e` on target hardware on **first plug-in**
  without replug tuning.

---

## Possible routes to explore

Ordered by evidence strength. Slow @ 2400 remains production; these are research
only unless noted otherwise.

### 1. Late RX-only UART after GPIO DCM (most promising — SPIKE 2026-06)

**Evidence:** Official SPIKE `experiment_rx_only_listen()` (2500 ms) received
`0xc2 0x01 0x00` ×3 at **~434 ms** — the 115200 LE interior of `CMD_SPEED` — but
header was `0x5a` not `0x52` and checksum garbled. Listening from hello left UART
**byte-misaligned** after DCM garbage (75× `0x00` from 37 ms).

**Route:** Keep current GPIO DCM through ~400 ms (no UART during DCM). Then:

1. Fresh `listen_only_uart()` (`tx=-1`, TX GPIO **low**).
2. Listen ~50–100 ms; match exact `HUB_CMD_SPEED` **or** signature `0xc2 0x01 0x00`.
3. `deinit` → `fast_uart()` → ACK `0x04` + registration @ 115200.

**Why it may work:** Probe timing confirmed on SPIKE; corruption was from early
listen, not absence of probe. Avoids TX idle-high during DCM (full-duplex confound).

**Open questions:** Sub-ms ACK latency after match; PB4 vs SPIKE behaviour for
third-party device IDs; whether signature match is enough without exact `0x52`.

### 2. RX-only listen from hello (tested — partial success)

**Status:** Tested on official SPIKE (`tests/experiment_rx_only_listen.py`).

**Result:** Hub probe **is present** but **mis-framed** if UART open from t=0. TX-low
RX-only fixes the idle-high confound but **not** the mis-sync problem (see route 1).

**Do not pursue:** Scan-from-hello as the primary fast-connect strategy.

### 3. Count `0xF0` as DCM drop marker (ruled out)

**Status:** Tested on official SPIKE — **0× `0xF0`** vs ~20 DCM drops on LA.

ESP32 hardware UART discards framing errors; LA decodes edges aggressively. Not
1:1 with drops (prior runs: 134× `0xF0?`, 7× `0x00`).

**Do not pursue** as drop counter. Sliding search for `0x52` or `0xc2 0x01 0x00`
in a buffer remains valid if UART is opened at the right time.

### 4. Fixed delay instead of GPIO DCM counting

Open UART @ 115200 after hello + fixed ~400 ms delay (skip drop counting).

**Untested.** May break LMS-ESP32 if UART opens during hub DCM on RX pin. Lower
priority than route 1 (GPIO DCM already works for timing the cut-over).

### 5. Toggle UART on each DCM high, TX forced low

Re-open UART on every hub-high rising edge; close and pull TX low if no probe in
14 ms.

**Unlikely:** UART init is ms-scale; DCM lows are ~2 ms; probe arrives **after**
last high ends (~17 µs), not during 16 ms highs. See § UART TX idle vs DCM.

### 6. RMT / bit-bang capture on RX

Hardware-specific sub-ms capture during last DCM ms or post-DCM window.

**Untested.** Only if route 1 still misses probe after late UART reopen.

### 7. Hub-side / Pybricks change

Third-party sensor registration policy — out of scope for `lpf2.py`.

---

## UART TX idle vs DCM (2026 follow-up)

### Does opening UART pull ESP TX high?

**Yes.** After hello, `wrt_tx_pin(0)` holds **TX low** via GPIO (`Pin.OUT,
PULL_DOWN`). Calling `machine.UART(..., tx=TX_PIN)` gives the pin to the UART
peripheral; async idle is **HIGH**. Slow path opens UART only after the full GPIO
DCM window (~450 ms).

### Does that interfere with DCM?

**Two separate wires on PUP** (hub TX → sensor RX, sensor TX → hub RX):

| Line | During GPIO DCM | When UART opens |
|------|-----------------|-----------------|
| Hub TX → sensor RX (yellow) | Hub drives DCM pulses | Sensor **RX** owned by UART — cannot GPIO-count DCM on same pin |
| Sensor TX → hub RX (green) | Held **LOW** by GPIO | UART idle → **HIGH** |

So opening UART does **not** pull the **hub TX / yellow** line high. DCM pulses
on yellow are hub-driven. The screenshot (green **low** for all DCM highs, then
activity only at the end) matches **GPIO DCM with TX held low** — not UART open
during the pulse train.

What UART open *does* do:

1. **Stops GPIO on sensor RX** — same pin; cannot watch DCM and listen on UART at once.
2. **Pulls sensor TX high** — hub RX sees idle-high while hub may still be in DCM
   on its side; may affect hub state (unverified, but plausible).
3. **Init latency** (ms on ESP32) — misses the ~0.5 ms `CMD_SPEED` burst if opened
   too late; opening too early while hub still pulsing may be too early for the probe.

The yellow `0x` labels in LA are **mis-decoded UART** on a GPIO/DCM waveform (same
class of error as “framing error” on idle-high before start bit) — not valid bytes.

### `CMD_SPEED` timing vs “open on every DCM high”

From `digital_motor.csv`: probe starts **~17 µs after the last DCM high ends**, not
during the 16 ms high phases. Re-opening UART on each rising edge would:

- Run `UART()` init/deinit **~20×** (ms each on ESP32, not µs).
- Listen during **high** phases when the hub is **not** sending `CMD_SPEED`.
- Still miss the probe if deinit/re-GPIO happens before the last high falls.

A **14 ms listen window on each high** does not align with protocol timing; the
**2 ms low** gaps are far too short for UART setup on MicroPython.

### Toggle UART on hub-high / pull TX down (user idea)

Concept: on hub TX rising edge → open UART → if no `CMD_SPEED` within 14 ms →
close UART, drive TX low again.

**Why it is unlikely to work on LMS-ESP32:**

| Issue | Detail |
|-------|--------|
| Init cost | `machine.UART()` is **milliseconds**; DCM lows are **~2 ms** |
| Pin mux | RX cannot be GPIO and UART simultaneously |
| Probe placement | `0x52…` comes **after** last high, not inside 16 ms highs |
| v2.6 capture | At 355 ms UART open: **7× `0x00`**, no `0x52` — SYNC/garbage, not probe |
| Prior regression | Any UART activity during DCM window correlated with failed connect |

If revisited: **one** UART open on the **last** DCM edge (after drop 19 low), TX
forced low until probe received (non-standard; may need RX-only UART or external
transceiver). Still needs sub-ms capture (RMT/dedicated hardware), not ms loops.

### Half-duplex RX-only listen, TX held low (tested 2026-06)

**Idea:** Open UART **receive-only** (`tx=-1` on ESP32 MicroPython) so sensor TX
stays under **GPIO** and can be held **LOW** (hub RX not seeing idle-high) while
listening for `CMD_SPEED` on sensor RX.

**Result (official SPIKE):** Probe received at ~434 ms with corrupted framing when
listening from hello. See **Possible routes to explore §1** — late UART reopen
after GPIO DCM is the follow-on, not listen-from-hello.

**What this fixes**

| Problem with full-duplex `fast_uart()` | RX-only + GPIO TX low |
|----------------------------------------|------------------------|
| UART idle pulls sensor TX **HIGH** | TX stays **LOW** — matches screenshot / slow-path GPIO behaviour |
| Hub RX may see “device already talking” during DCM | Hub RX stays low until we deliberately ACK |
| Same as official motor passive listen phase? | Closer to “listen only, don’t assert TX” |

**What it does not fix**

- **Timing:** `CMD_SPEED` is still ~0.5 ms; must have RX-only UART **open and
  polling** when the burst arrives (~370–400 ms).
- **RX pin conflict:** Cannot GPIO-count DCM and UART-listen on the **same**
  pin at once — use GPIO DCM first, then cut over (route 1).
- **Mis-sync from early listen:** DCM garbage @ 115200 desynchronizes UART before
  probe; **do not** listen from t=0.
- **Re-init for reply:** After probe, need **full-duplex** UART for ACK + registration.

### Count `0xF0` instead of GPIO DCM drops? (ruled out — SPIKE 2026-06)

**Observation:** Logic analyzer @ 115200 on hub TX during DCM shows spurious decode
labels (`0x`, framing errors, sometimes `0xF0?` in our ACK-failure histograms).
**Idea:** RX-only UART from hello; count `0xF0` (or any garbage byte) per DCM
transition instead of `rx_pin.value()` + `sleep_ms(1)`.

**Why it is attractive**

- One path only: **no GPIO/UART mux conflict** on sensor RX.
- TX stays GPIO-low (`tx=-1` on UART).
- Same peripheral listens for DCM progress **and** `CMD_SPEED` (`0x52…`).

**Why it may not work as a drop counter**

| Issue | Detail |
|-------|--------|
| LA ≠ ESP32 UART | Saleae decodes **raw edges** aggressively; ESP32 hardware UART **discards** most framing errors — you often get **no byte**, not a reliable `0xF0` per pulse. |
| Not 1:1 with drops | Failed slow wait logged **134× `0xF0?`** vs ~20 DCM drops — far too many. v2.6 fast listen got **7× `0x00`**, not `0xF0`. Pattern is **not** one marker per drop. |
| DCM is ms-scale | 16 ms high / 2 ms low at **115200** (8.7 µs/bit) is not valid UART; occasional random bytes at best, not a clean protocol. |
| `0x52` in noise | Must **continuously drain** RX and sliding-window search — if garbage fills the buffer, probe can still be missed. |

**Better use of the idea (if experimented)**

Do **not** count `0xF0` as a drop index. Instead:

1. RX-only @ 115200 from hello, TX GPIO **low**.
2. Loop until 450 ms: `read()` everything, append to buffer.
3. **Primary:** sliding search for `HUB_CMD_SPEED` anywhere in buffer.
4. **Secondary (debug only):** histogram all bytes — see if `0xF0`/`0x00` correlate
   with drops on **this** board, not on LA.

That replaces GPIO timing guesses with “capture everything, find `0x52`” — counting
`0xF0` is only useful after a measurement proves it is stable on LMS-ESP32 hardware.

**Experiment (2026-06):** `tests/experiment_rx_only_listen.py` — run on LMS-ESP32
after plug-in:

```python
import experiment_rx_only_listen
experiment_rx_only_listen.run()
```

Or `LPF2.experiment_rx_only_listen()` from REPL. Prints byte histogram (incl.
`0xF0`, `0x00`), first-seen times, and whether `HUB_CMD_SPEED` appears in the
capture. **Does not connect** — safe to run alongside slow-path production code.

#### Results: official SPIKE firmware (2026-06, listen 2500 ms)

```
total 90 bytes
  SYNC (0x00): 75 @37ms
  0x5a: 3 @434ms
  0xc2: 3 @435ms
  0x67: 3 @435ms
  0x01: 6 @435ms
0xF0 count: 0
hex fragment: 0x5a 0x0 0xc2 0x1 0x0 0x1 ... 0x67 ...
CMD_SPEED exact match: not found
```

**Conclusions from this run**

| Finding | Implication |
|---------|-------------|
| **0× `0xF0`** | Drop-counting via `0xF0` is **ruled out** on ESP32 (LA ≠ device). |
| **75× `0x00` from 37 ms** | DCM GPIO on hub TX mis-read as `BYTE_SYNC` @ 115200 — not one per drop. |
| **Activity @ ~434–435 ms** | Matches LA/log timing for hub probe window (~400 ms). |
| **`0xc2 0x01 0x00` ×3** | Interior of **115200 LE** in `CMD_SPEED` — hub **does** send speed probe. |
| **`0x5a` not `0x52`** | First header byte corrupted (`0x52`→`0x5a`); UART **bit/byte mis-sync** after DCM garbage. |
| **`0x67` near `0x6e` checksum** | Checksum byte also corrupted — exact 6-byte match fails. |

**Interpretation:** RX-only + TX-low **receives** the probe on official SPIKE, but listening
from hello through DCM leaves the UART **out of frame** when the real @115200 packet
arrives. → **See [Possible routes to explore §1](#1-late-rx-only-uart-after-gpio-dcm-most-promising--spike-2026-06).**

Pybricks 4 third-party runs saw only **7× `0x00`** at 355 ms — hub may not send
`0x52` to unknown devices, or probe already passed.

---

## File reference

| File | Contents |
|------|----------|
| `pybricks_4.0_motor.sal` | LA session, official motor connect |
| `digital_motor.csv` | Hub TX/RX @ 115200, timing-only export |
| `motor_connection/digital.csv` | Additional capture |
| `../tests/measure_lpf2_timing.py` | GPIO DCM + late full-duplex UART open |
| `../tests/experiment_rx_only_listen.py` | **RX-only listen experiment** (`tx=-1`) |
| `../src/lpf2.py` | `experiment_rx_only_listen()`, `fast_connect` experimental |
