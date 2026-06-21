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

Alternative directions (not implemented):

- Open UART @ 115200 immediately after hello and **discard** DCM GPIO counting
  (use fixed delay only) — untested; may break LMS-ESP32.
- Hub-side / Pybricks change for third-party sensors — out of scope for `lpf2.py`.
- Bit-bang or **RMT** capture on RX during last DCM ms — hardware-specific.

---

## File reference

| File | Contents |
|------|----------|
| `pybricks_4.0_motor.sal` | LA session, official motor connect |
| `digital_motor.csv` | Hub TX/RX @ 115200, timing-only export |
| `motor_connection/digital.csv` | Additional capture |
| `../tests/measure_lpf2_timing.py` | On-device timing measurement |
| `../src/lpf2.py` | `fast_connect` opt-in (experimental), slow path production |
