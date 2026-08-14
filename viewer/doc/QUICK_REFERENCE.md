# CGOSVIEW - Quick Reference Guide

## Overview
A Python PyQt6 application for viewing live Go games from the CGOS (Computer Go Server). Features real-time game streaming, complete Go rules validation, and tabbed multi-game viewing.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run with defaults (cgos-hg.de:6809)
cgosview

# Run with custom server
cgosview myserver.com 1234

# Run with options
cgosview --max-games 5 --timeout 20
```

---

## Project Structure at a Glance

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| **Game Engine** | Go rules, move validation, capture detection | `game/gogame.py` (457 lines) |
| **Network** | Async CGOS server communication | `network/cgos_client.py` (702 lines) |
| **GUI** | PyQt6 interface, game tabs, board rendering | `gui/*.py` (1,322 lines) |
| **Config** | Command-line arguments, settings | `config.py` (120 lines) |
| **Utils** | Threading, async integration | `utils/threading.py` (120 lines) |
| **Tests** | Unit/integration tests | `tests/*.py` (518+ lines) |

---

## Core Classes

### GoGame (game/gogame.py)
Handles all Go rules and game state.

```python
game = GoGame(19)                    # Create 19x19 game
result = game.make_move("E5")        # Place stone at E5
if result >= 0:
    print(f"Valid, captured {result} stones")
elif result == -1:
    print("Suicide move")
elif result == -2:
    print("KO violation")
```

**Key Methods**:
- `make_move(move)`: Execute move with full validation → int (captures or error code)
- `move_to_index(move)`: Parse "A1" notation → int index
- `undo_move()`: Undo last move → bool (success)
- `get_board()`: Get current state → List[int] (19x19)
- `list_moves()`: Get all moves → List[str]
- `color_to_move`: Property → Stone.BLACK or Stone.WHITE

**Return Codes**:
- `-4`: Format error
- `-3`: Square occupied
- `-2`: KO violation
- `-1`: Suicide
- `0+`: Valid (captures)

### CGOSClient (network/cgos_client.py)
Async CGOS server connection.

```python
client = CGOSClient("cgos-hg.de", 6809)
client.on_game_added = handle_new_game
client.on_game_updated = handle_move
await client.connect_with_retry()
await client.receive_games()
```

**Key Methods**:
- `async connect()`: TCP connection → bool
- `async connect_with_retry()`: Connect with exponential backoff → bool
- `async receive_games()`: Main event loop
- `async send_command(cmd)`: Send command → bool
- `get_state()`: ConnectionState enum

**Callbacks**:
- `on_game_added(GameInfo)`: New game
- `on_game_updated(GameInfo)`: Moves received
- `on_game_finished(GameInfo)`: Game done
- `on_connection_state_changed(state, error)`: Status change

### GameInfo (network/cgos_client.py)
Game metadata from server.

```python
GameInfo(
    gid=12345,                    # Game ID
    date="2026-08-06",            # YYYY-MM-DD
    time="15:30:45",              # HH:MM:SS
    board_size=19,                # 7-25
    komi=7.5,                     # White handicap
    white_player="Computer1",
    black_player="Computer2",
    result=None,                  # None if in progress
    moves=[("E5", 2.5), ...]      # (move, time)
)
```

### MainWindow (gui/main_window.py)
Main Qt application window.

```python
from cgosview.gui.main_window import MainWindow
from cgosview.config import ViewerConfig

config = ViewerConfig(server="cgos-hg.de", port=6809)
window = MainWindow(config)
window.show()
```

**Features**:
- Server connection status
- Active game list
- Up to 10 game tabs
- Real-time updates

### GameTab (gui/game_tab.py)
Single game display with board and moves.

```python
tab = GameTab(gid=123, game_info=info)
# Has: board_widget, move_history_table, nav controls
```

### GameBoardWidget (gui/board_widget.py)
Custom widget rendering Go board.

```python
board = GameBoardWidget(size=19)
board.update_board(game)  # Redraw board
```

---

## Configuration

### ViewerConfig (config.py)

```python
@dataclass
class ViewerConfig:
    server: str = "cgos-hg.de"
    port: int = 6809
    max_games: int = 50
    connection_timeout: float = 10.0
    heartbeat_interval: float = 30.0
    reconnect_max_retries: int = 5
    reconnect_base_delay: float = 1.0
```

### Command-Line Args

```bash
cgosview [server] [port] [options]

Options:
  --max-games N          Max games in game list (default: 50)
  --timeout SECONDS      Connection timeout (default: 10.0)
  --heartbeat SECONDS    Heartbeat interval (default: 30.0)

Examples:
  cgosview
  cgosview other.server.com 1234
  cgosview --max-games 5 --timeout 20
```

---

## Threading Model

**Main Thread** (Qt GUI):
- Qt event loop
- UI updates
- Signal/slot connections

**Async Thread** (Network):
- asyncio event loop
- TCP socket operations
- Game update parsing

**Communication**:
- Qt signals (thread-safe)
- Callbacks from network to GUI

---

## Common Tasks

### Making a Move (as dev, for testing)

```python
game = GoGame(19)
result = game.make_move("E5")
if result >= 0:
    board = game.get_board()  # Get visual board state
```

### Parsing Move Notation

```python
index = game.move_to_index("E5")  # → positive integer index
index = game.move_to_index("PASS") # → 0
index = game.move_to_index("Z99")  # → -4 (format error)
```

### Undoing Moves

```python
while game.undo_move():  # Undo until at start
    pass

# Or undo all
game.undo_all()
```

### Checking Game End

```python
if game.two_pass():  # Both players passed
    print("Game over")
```

### Connecting to Network

```python
client = CGOSClient("cgos-hg.de", 6809)
if await client.connect_with_retry():
    await client.receive_games()
else:
    print("Failed to connect")
```

---

## Error Codes (MoveError)

| Code | Meaning |
|------|---------|
| `-4` | Invalid move notation (not A1-T19 or not PASS) |
| `-3` | Square already occupied |
| `-2` | KO rule violation (board state would repeat) |
| `-1` | Suicide move (stone has no liberties) |
| `0` | Valid pass move |
| `≥1` | Valid move (number is captured stones) |

---

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=cgosview tests/

# Run specific test file
pytest tests/test_gogame.py -v

# Run specific test class
pytest tests/test_gogame.py::TestMoveToIndex -v
```

### Test Files
- `test_gogame.py`: Game rules validation
- `test_cgos_protocol.py`: Network protocol
- `test_network_integration.py`: Client connection
- `test_game_tab_navigation.py`: UI navigation
- `test_move_history_table.py`: Move display

---

## Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/

# All checks
black src/ tests/ && ruff check src/ tests/ && mypy src/
```

---

## Key Numbers

| Setting | Value |
|---------|-------|
| Min board size | 7 |
| Max board size | 25 |
| Max games in game list | 50 |
| Max game tabs | 10 |
| Connection timeout | 10.0s |
| Heartbeat interval | 30.0s |
| Max reconnect attempts | 5 |
| Backoff base | 1.0s (exponential: 1, 2, 4, 8, 16s) |
| Line length | 100 chars |
| Target Python | 3.10+ |

---

## Stone Constants

```python
from cgosview.game.gogame import Stone

Stone.EMPTY    # = 0
Stone.BLACK    # = 1
Stone.WHITE    # = 2
Stone.BORDER   # = 3
```

---

## ConnectionState

```python
from cgosview.network.cgos_client import ConnectionState

ConnectionState.DISCONNECTED    # Not connected
ConnectionState.CONNECTING      # Connection in progress
ConnectionState.CONNECTED       # Active connection
ConnectionState.ERROR           # Connection failed
```

---

## Resources

### Board Graphics
Located in `src/cgosview/resources/`:
- `wood.png` (7.2 KB): Board background texture
- `bstone.png` (1.1 KB): Black stone
- `wstone.png` (1.3 KB): White stone

Falls back to plain colors if images unavailable.

---

## Dependencies

### Required
- PyQt6 ≥6.6.0
- PyQt6-Qt6 ≥6.6.0
- Python ≥3.10

### Development
- pytest, pytest-asyncio, pytest-cov
- black, ruff, mypy
- sphinx

---

## File Sizes Summary

```
Total: ~4,783 lines of Python code
  - Game logic: 457 lines
  - Network: 702 lines
  - GUI: 1,322 lines (board: 310, main: 486, tab: 287, history: 191, signals: 43, init: 5)
  - Config/Utils: 240 lines
  - Tests: 1,963 lines
  - Graphics: 3 PNG files (~10 KB)
```

---

## License

MIT License - See LICENSE file

---

## Troubleshooting

### Connection Fails
- Check server address and port
- Verify network connectivity
- Check firewall rules
- Review logs for error messages

### GUI Won't Start
- Ensure PyQt6 installed: `pip install PyQt6`
- Check Python version (3.10+)
- Look for ImportError messages

### Board Rendering Issues
- Check if PNG files exist in resources/
- Look for texture load warnings in logs
- Fallback to solid colors if images missing

### Move Validation Fails
- Check move notation: must be A1-T19 (not I column)
- Verify stone colors alternate (black first)
- Check for ko/suicide violations in logs

---

## Links

- **CGOS Server**: http://cgos-hg.de
- **Go Rules**: https://en.wikipedia.org/wiki/Rules_of_Go
- **PyQt6 Docs**: https://www.riverbankcomputing.com/static/Docs/PyQt6/
- **Python**: https://www.python.org

