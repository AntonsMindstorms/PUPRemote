<div align="center">
  <img alt="PUPRemote logo" src="https://raw.githubusercontent.com/antonvh/PUPRemote/main/img/pupremote.png" width="200">

# PUPRemote

[![License: GPLv3](https://img.shields.io/github/license/antonvh/PUPRemote?color=blue)](https://github.com/antonvh/PUPRemote/blob/main/LICENSE.txt)
![MicroPython Compatible](https://img.shields.io/badge/MicroPython-Compatible-brightgreen)
![Platforms: Pybricks | SPIKE2 | Robot Inventor](https://img.shields.io/badge/Platforms-Pybricks%20%7C%20SPIKE2%20%7C%20Robot%20Inventor-red)

PUPRemote lets microcontrollers present themselves as LEGO Powered Up sensors. It includes a low-level LPF2 emulator and a higher-level remote-procedure-style API for quick sensor prototypes.

</div>


## Table of Contents

- [PUPRemote](#pupremote)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Supported Platforms](#supported-platforms)
  - [Installation](#installation)
    - [LMS-ESP32 firmware](#lms-esp32-firmware)
    - [OpenMV](#openmv)
    - [Pybricks hubs](#pybricks-hubs)
  - [Quick Start](#quick-start)
    - [LMS-ESP32 demo](#lms-esp32-demo)
    - [OpenMV demo](#openmv-demo)
    - [Pybricks demo](#pybricks-demo)
  - [Compatibility Notes](#compatibility-notes)
  - [Project Structure](#project-structure)
  - [Development Notes (MicroPython first)](#development-notes-micropython-first)
  - [Contributing](#contributing)
  - [License](#license)

## Features

- Emulate LEGO LPF2 sensors from MicroPython boards
- Higher-level RPC-style API (`PUPRemoteSensor`, `PUPRemoteHub`)
- Supports both synchronous (`process()`) and asynchronous (`process_async()`) modes
- Works with Pybricks, SPIKE 2, and Robot Inventor hubs
- Example scripts for LMS-ESP32, OpenMV, and Pybricks
- Optional lightweight `pupremote_hub.py` for Pybricks-only deployments

## Supported Platforms

- LMS-ESP32 firmware (bundles `pupremote.py` and `lpf2.py`)
- OpenMV (copy `pupremote.py` and `lpf2.py` onto the board)
- Pybricks hubs (use the smaller `pupremote_hub.py` when space matters)
- Other MicroPython-capable boards with LPF2 physical connection

## Installation

### LMS-ESP32 firmware

1. The firmware already contains `pupremote.py` and `lpf2.py`.
2. Copy an example (for instance `examples/esp32_dummy_data/pup_demo_esp32.py`) to the board as `main.py`.
3. Connect the LMS-ESP32 to your hub (e.g., SPIKE Prime port A) and reboot.

### OpenMV

1. Copy `src/pupremote.py` and `src/lpf2.py` to the OpenMV board.
2. Deploy an example such as `examples/openmv_simple/main.py`.
3. Run from the OpenMV IDE or reboot to start.

### Pybricks hubs

1. Copy `src/pupremote_hub.py` to the hub (use this smaller file instead of the full `pupremote.py`).
2. Upload an example such as `examples/openmv_simple/pybricks_spike.py` and adjust imports to `from pupremote_hub import PUPRemoteHub` if needed.
3. Run the program from the Pybricks app.

## Quick Start

### LMS-ESP32 demo

Copy to the LMS-ESP32 as `main.py` and reboot:

```python
# examples/esp32_dummy_data/pup_demo_esp32.py
from pupremote import PUPRemoteSensor, SPIKE_ULTRASONIC

def msg(*argv):
    return "demo"

p = PUPRemoteSensor(sensor_id=SPIKE_ULTRASONIC, power=True)
p.add_command('msg', "repr", "repr")

while True:
    p.process()
```

### OpenMV demo

Copy `src/pupremote.py` and `src/lpf2.py` to the board, then run:

```python
# examples/openmv_simple/main.py
from pupremote import PUPRemoteSensor, ESP32, SPIKE_ULTRASONIC
from time import sleep_ms

p = PUPRemoteSensor(sensor_id=SPIKE_ULTRASONIC, platform=ESP32)
p.add_channel('cntr', to_hub_fmt="b")

while True:
    p.process()
    p.update_channel('cntr', 1)
    sleep_ms(20)
```

### Pybricks demo

Place `src/pupremote_hub.py` on the hub and reference it:

```python
# examples/openmv_simple/pybricks_spike.py
from pupremote_hub import PUPRemoteHub

hub = PUPRemoteHub()
hub.add_channel('demo', to_hub_fmt="b")

while True:
    hub.process()
    hub.update_channel('demo', 1)
```

## Compatibility Notes

- **Async/Sync modes**: Use `process()` for synchronous polling in loops, or `process_async()` + `call_multitask()` for concurrent async operations with callback queues.
- Pybricks has a known 32-byte packet limitation. Pass `max_packet_size=16` when constructing `PUPRemoteHub` or `PUPRemoteSensor` to avoid checksum errors.
- For Pybricks, prefer `pupremote_hub.py` to save space (it only contains `PUPRemoteHub`).
- LMS-ESP32 firmware already includes dependencies; do not re-upload `pupremote.py` or `lpf2.py` there.

## Project Structure

- `src/` core implementation (`pupremote.py`, `pupremote_hub.py`, `lpf2.py`)
- `examples/` runnable demos for LMS-ESP32, OpenMV, and Pybricks
- `docs/` Sphinx docs with API references
- `img/` project assets (logo)

## Development Notes (MicroPython first)

- Target runtime is MicroPython; verify every proposed import exists there (e.g., `inspect` is unavailable—avoid it).
- Prefer `ustruct`, `uasyncio`, and `micropython.const`; gate CPython-only helpers behind `try/except ImportError`.
- Keep memory and dependency footprint small; avoid modules that pull in large transitive imports.
- In control applications, a derivative computed numerically in real time is usually called a **discrete derivative**; when low-pass filtered to suppress noise, it is often called a **dirty derivative**.

## Contributing

Contributions and protocol refinements are welcome. Please open an issue or PR with your ideas or projects built on PUPRemote.

## License

GPL-3.0. See the [LICENSE](LICENSE.txt) file for details.
