# CGOSVIEW

A Python PyQt6 application for viewing live Go games on the CGOS (Computer Go Online Server) in real-time.

## Features

- **Real-time game streaming** from the CGOS server
- **Full Go rules implementation** with move validation (captures, KO, suicide detection)
- **Multi-game viewer** with tabbed interface supporting up to 10 concurrent games
- **Game replay** with navigation controls
- **Professional GUI** built with PyQt6
- **Async networking** with automatic reconnection

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run
cgosview

# Connect to custom server
cgosview myserver.com 1234
```

## Project Structure

- **`game/gogame.py`** - Complete Go rules engine
- **`network/cgos_client.py`** - Async CGOS server client
- **`gui/`** - PyQt6 interface (main window, game tabs, board rendering)
- **`config.py`** - Configuration and command-line arguments
- **`utils/threading.py`** - Async/threading integration

## Technical Highlights

- **~4,337 lines** of well-tested Python code
- Board representation using flat arrays for O(1) performance
- Flood-fill algorithm for capture detection
- Comprehensive test suite (6 test files, 518+ lines)
- Full type hints and proper error handling

## Requirements

- Python 3.10+
- PyQt6 ≥6.6.0

## License

MIT
