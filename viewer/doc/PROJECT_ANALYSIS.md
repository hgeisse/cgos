# CGOSVIEW - Project Analysis Documentation

## Executive Summary

**CGOSVIEW** is a modern Python application for viewing Go games on the CGOS (Computer Go Server) in real-time. It's a complete port of the original Tcl/Tk viewer, featuring a PyQt6-based GUI, full Go rules implementation, async networking, and comprehensive game replay capabilities.

- **Project Type**: Desktop GUI Application (PyQt6)
- **Language**: Python 3.10+
- **License**: MIT
- **Version**: 1.0.0
- **Total Lines of Code**: ~4,783 (21 Python files: 2,820 source + 1,963 tests)
- **Current Status**: Beta (Development Status :: 4 - Beta)

---

## Project Structure

```
cgosview/
├── LICENSE                          # MIT License
├── pyproject.toml                   # Project metadata and dependencies
├── src/cgosview/                    # Main source directory
│   ├── __init__.py                  # Package initialization
│   ├── __main__.py                  # Application entry point
│   ├── config.py                    # Configuration management (command-line args)
│   ├── game/                        # Go game rules engine
│   │   ├── __init__.py
│   │   └── gogame.py                # Complete Go game implementation (457 lines)
│   ├── network/                     # Network communication layer
│   │   ├── __init__.py
│   │   └── cgos_client.py           # Async CGOS server client (702 lines)
│   ├── gui/                         # PyQt6 graphical interface
│   │   ├── __init__.py
│   │   ├── signals.py               # Thread-safe Qt signals (43 lines)
│   │   ├── main_window.py           # Main application window (486 lines)
│   │   ├── game_tab.py              # Individual game tab widget (287 lines)
│   │   ├── board_widget.py          # Go board rendering widget (310 lines)
│   │   └── move_history_table.py    # Move list display widget (191 lines)
│   ├── utils/                       # Utility modules
│   │   ├── __init__.py
│   │   └── threading.py             # Asyncio/threading integration (120 lines)
│   └── resources/                   # Game board graphics
│       ├── wood.png                 # Board texture (7.2 KB)
│       ├── bstone.png               # Black stone image (1.1 KB)
│       └── wstone.png               # White stone image (1.3 KB)
└── tests/                           # Unit and integration tests
    ├── __init__.py
    ├── test_gogame.py               # Go game rules tests (518 lines)
    ├── test_cgos_protocol.py        # CGOS protocol tests
    ├── test_game_tab_navigation.py  # Game tab UI tests
    ├── test_move_history_table.py   # Move history widget tests
    └── test_network_integration.py  # Network client integration tests
```

---

## Core Components

### 1. **Game Rules Engine** (`game/gogame.py`)
**Responsibility**: Implements complete Go game rules with full validation.

**Key Classes**:
- **`Stone(IntEnum)`**: Board intersection states
  - `EMPTY = 0`: Empty point
  - `BLACK = 1`: Black stone
  - `WHITE = 2`: White stone
  - `BORDER = 3`: Board border (used for boundary detection)

- **`MoveError(IntEnum)`**: Move validation error codes
  - `-4`: Format error (invalid notation)
  - `-3`: Square occupied
  - `-2`: KO violation (board state repeat)
  - `-1`: Suicide (no liberties)
  - `0+`: Valid move (number of captured stones)

- **`GoGame`**: Main game logic
  - Supports board sizes 7-25 (standard Go)
  - Alternating black/white play
  - Full move validation and execution
  - Board history and undo functionality
  - Two-pass game termination detection

**Key Methods**:
- `make_move(move: str) -> int`: Execute and validate a move
- `move_to_index(move: str) -> int`: Parse algebraic notation (e.g., "A1", "T19")
- `_capture_group(target: int) -> List[int]`: Flood-fill algorithm for capture detection
- `undo_move() -> bool`: Undo the last move
- `undo_all()`: Reset to game start
- `two_pass() -> bool`: Check if game should end
- `get_board() -> List[int]`: Get current board state
- `score_board(dead_list: List[str]) -> List[int]`: Calculate final score

**Board Storage**:
- Flat list representation with borders: `(size+2) rows × (size+1) columns`
- Interior only accessible via `get_board()` which returns `size × size` points
- Navigation uses directional offsets: `[-1, 1, n1, -n1]` (left, right, down, up)

**Validation Rules**:
1. Move notation format validation
2. Square occupancy check
3. Capture detection (4-directional flood-fill)
4. Suicide detection (stone with no liberties, unless capturing)
5. KO rule enforcement (board state cannot repeat)

---

### 2. **Network Client** (`network/cgos_client.py`)
**Responsibility**: Async communication with CGOS server for real-time game streaming.

**Key Classes**:
- **`ConnectionState(Enum)`**: Connection lifecycle states
  - `DISCONNECTED`: Not connected
  - `CONNECTING`: Connection in progress
  - `CONNECTED`: Active connection
  - `ERROR`: Connection failed

- **`GameInfo`**: Metadata for a single game
  ```
  gid: int                          # Game ID
  date: str                         # YYYY-MM-DD
  time: str                         # HH:MM:SS
  board_size: int                   # 7-25
  komi: float                       # Handicap points
  white_player: str                 # Player name
  black_player: str                 # Player name
  result: Optional[str]             # "W+2.5", "B+Resign", None if in progress
  moves: List[Tuple[str, float]]   # (move, elapsed_time)
  ```

- **`CGOSClient`**: Async server connection manager
  - Non-blocking TCP connection
  - Automatic reconnection with exponential backoff
  - Protocol handshake (v1 viewer protocol)
  - Heartbeat mechanism for connection health
  - Event callbacks for game updates
  - Maximum of 50 games in game list (configurable)

**Key Methods**:
- `async connect() -> bool`: Establish TCP connection
- `async connect_with_retry() -> bool`: Connect with exponential backoff retry
- `async send_command(command: str) -> bool`: Send command to server
- `async heartbeat()`: Periodic keep-alive ping
- `async receive_games()`: Main event loop receiving game updates
- `get_state() -> ConnectionState`: Get current connection state
- `set_state(state, error)`: Change state and trigger callback

**Callbacks**:
- `on_game_added(GameInfo)`: New game appeared on server
- `on_game_updated(GameInfo)`: Game received new moves
- `on_game_finished(GameInfo)`: Game completed
- `on_connection_state_changed(ConnectionState, error_msg)`: Connection status changed

**Configuration**:
- `connection_timeout`: 10.0 seconds (default)
- `heartbeat_interval`: 30.0 seconds (default)
- `max_retries`: 5 reconnection attempts
- `reconnect_base_delay`: 1.0 second (exponential backoff: 1s, 2s, 4s, 8s, 16s)

---

### 3. **Main Application Window** (`gui/main_window.py`)
**Responsibility**: Primary UI container managing game list and tabbed game views.

**Key Features**:
- Server connection status display
- Active game list with filtering
- Up to 10 concurrent game tabs
- Navigation between games
- Real-time game updates
- Graceful shutdown handling

**Layout**:
```
┌─────────────────────────────────────────┐
│ Connection Status | Server: cgos-hg.de  │
├─────────────────────────────────────────┤
│                                         │
│  Game 1 | Game 2 | Game 3 | Game N    │  (Tabbed games)
│                                         │
│  [Board Widget | Move History Table]   │
│                                         │
│  [Navigation: << < Play >> | >]        │
│                                         │
└─────────────────────────────────────────┘
```

**Key Methods**:
- `_create_ui()`: Initialize UI components
- `_connect_signals()`: Wire up network/GUI connections
- `on_game_added(GameInfo)`: Handle new game, create tab
- `on_game_updated(GameInfo)`: Update game in tab
- `on_connection_state_changed(state, error)`: Update status display
- `_handle_window_close()`: Clean shutdown

**Threading Model**:
- Main thread: Qt GUI event loop
- Async thread: Async event loop for network I/O
- Communication: Qt signals (thread-safe)

---

### 4. **Game Tab Widget** (`gui/game_tab.py`)
**Responsibility**: Single game display with board and navigation controls.

**Components**:
- Game info label (players, board size, komi, result)
- Board widget (left side)
- Move history table (right side)
- Navigation controls (first, previous, next, last, jump)

**Key Methods**:
- `_load_game(game_info)`: Parse moves and populate GoGame
- `_update_board_display()`: Render current position
- `_on_move_table_clicked(move_index)`: Navigate to move
- `_on_nav_first()`, `_on_nav_prev()`, etc.: Navigation handlers

**Navigation**:
- Independent replay position per tab
- Synchronized with move history table
- Board updates on move selection

---

### 5. **Board Rendering Widget** (`gui/board_widget.py`)
**Responsibility**: Custom Qt widget for drawing Go board and stones.

**Features**:
- Configurable board size (7-25)
- Grid rendering
- Stone placement (black/white)
- Board coordinates (A-Z columns, 1-25 rows, skip 'I')
- Handicap point indicators
- Texture-based rendering with fallback

**Rendering Constants**:
- `STONE_SIZE = 22` pixels
- `BOARD_OFFSET = 33` pixels (margin)
- `SQUARE_SIZE = 22` pixels (grid spacing)

**Resource Loading**:
- `wood.png`: Board background texture
- `bstone.png`: Black stone image
- `wstone.png`: White stone image
- Graceful fallback to color rendering if resources missing

---

### 6. **Configuration System** (`config.py`)
**Responsibility**: Command-line argument parsing and configuration management.

**ViewerConfig Dataclass**:
```python
server: str = "cgos-hg.de"
port: int = 6809
max_games: int = 50
connection_timeout: float = 10.0
heartbeat_interval: float = 30.0
reconnect_max_retries: int = 5
reconnect_base_delay: float = 1.0
```

**Command-Line Arguments**:
```bash
cgosview [server] [port] [--max-games N] [--timeout S] [--heartbeat S]
```

**Examples**:
```bash
cgosview                                    # Uses defaults
cgosview other.server.com 1234              # Custom server/port
cgosview --max-games 5 --timeout 20.0       # Custom options
```

---

### 7. **Threading Utilities** (`utils/threading.py`)
**Responsibility**: Integration between asyncio event loop and Qt GUI thread.

**Key Class: `AsyncioThread`**
- Daemon thread running asyncio event loop
- `run_async(coro)`: Schedule coroutine in event loop
- `stop()`: Gracefully shutdown with task cleanup
- Thread-safe task scheduling

**Wrapper Utility**:
- `create_async_callback_wrapper()`: Convert Qt signal to async callback

**Purpose**:
- Main thread: Qt GUI operations
- Async thread: Network I/O and long-running tasks
- Communication: Qt signals + callbacks

---

### 8. **Qt Signals** (`gui/signals.py`)
**Responsibility**: Thread-safe inter-thread communication between network and GUI.

**Signals Defined**:
- `game_added(GameInfo)`: New game on server
- `game_updated(GameInfo)`: Game received new moves
- `game_finished(GameInfo)`: Game completed
- `connection_state_changed(ConnectionState, str)`: Connection status
- `error_occurred(str)`: Error message

---

### 9. **Application Entry Point** (`__main__.py`)
**Responsibility**: Application initialization and startup.

**Startup Sequence**:
1. Configure logging (INFO level, formatted output)
2. Parse command-line configuration
3. Log server/config details
4. Create PyQt6 QApplication
5. Create MainWindow with config
6. Show window and run event loop
7. Graceful error handling with proper exit codes

**Exit Codes**:
- `0`: Successful exit
- `1`: Fatal error (import/runtime exception)

---

## Testing Strategy

### Test Files (6 total, 518+ test lines)

1. **`test_gogame.py`** (518 lines)
   - Board initialization with all valid/invalid sizes
   - Move notation parsing (algebraic coordinates, PASS)
   - Move validation (format, occupation, captures, suicide, KO)
   - Capture detection (flood-fill correctness)
   - Game history and undo functionality
   - Color-to-move alternation
   - Board state tracking

2. **`test_cgos_protocol.py`**
   - Protocol handshake
   - Game info parsing
   - Move encoding/decoding
   - Server response handling

3. **`test_network_integration.py`**
   - Connection establishment
   - Reconnection logic
   - Game update streaming
   - Error recovery

4. **`test_game_tab_navigation.py`**
   - Tab creation/destruction
   - Move navigation
   - Board updates
   - Position synchronization

5. **`test_move_history_table.py`**
   - Table display
   - Move selection
   - Highlight behavior

---

## Dependencies

### Runtime
- **PyQt6** (≥6.6.0): GUI framework
- **PyQt6-Qt6** (≥6.6.0): Qt6 bindings

### Development
- **pytest** (≥7.4): Unit testing
- **pytest-asyncio** (≥0.21): Async test support
- **pytest-cov** (≥4.1): Code coverage
- **black** (≥23.0): Code formatting
- **ruff** (≥0.1): Linting
- **mypy** (≥1.5): Type checking
- **sphinx** (≥7.0): Documentation generation

### Development Installation
```bash
pip install -e ".[dev]"  # Install with dev dependencies
```

---

## Configuration & Code Quality

### Code Style (Black/Ruff)
- Line length: 100 characters
- Target Python: 3.10, 3.11, 3.12
- Enabled rules: E (errors), F (pyflakes), W (warnings), I (imports)
- Ignored: E501 (line too long, handled by formatter)

### Type Checking (MyPy)
- Python version: 3.10
- Warn on return types: Enabled
- Warn on unused configs: Enabled
- Incomplete defs allowed (for now)

---

## Key Design Patterns

### 1. **Async/Await Network Pattern**
```
Main Thread (Qt)          Async Thread
    ↓                         ↓
MainWindow ←→ NetworkSignals ←→ CGOSClient
              (Qt signals)       (asyncio)
```

### 2. **Flat Board Representation**
- 1D array with borders for boundary detection
- Index calculation: `y * n1 + x` where `n1 = size + 1`
- Eliminates boundary checks in move validation

### 3. **Flood-Fill for Capture Detection**
- Recursive stack-based search from stone position
- Terminates on liberty or boundary
- Returns group for multi-stone captures

### 4. **Board History for Move Undo**
- Dictionary mapping move number to board state
- KO detection by comparing full board states
- Enables efficient move replay

### 5. **Tab-Based Multi-Game View**
- Independent GoGame instance per tab
- Separate replay position per game
- Concurrent game viewing up to 10 games

---

## Command Flow Examples

### Starting Application
```
main()
  → parse_args()
  → create QApplication
  → create MainWindow(config)
  → window.show()
  → app.exec() (event loop)
```

### Connecting to Server
```
MainWindow.showEvent()
  → create CGOSClient
  → create AsyncioThread
  → client.connect_with_retry()
  → client.receive_games()
  → emit signals on game updates
```

### Making a Move
```
GameTab._on_move_table_clicked(index)
  → GoGame.make_move(move)
  → validate (format, occupied, captures, suicide, KO)
  → update board state
  → update history
  → render board widget
```

### Game Replay
```
GameTab._on_nav_next()
  → increment replay_position
  → create new GoGame
  → replay all moves up to position
  → render board widget
  → highlight move in table
```

---

## Known Limitations & Future Improvements

### Current Limitations
1. Maximum 10 concurrent game tabs (hardcoded in MainWindow)
2. Board size limited to 7-25 (standard Go sizes only)
3. No SGF (Smart Game Format) import/export
4. No local game play (viewer-only)
5. No score calculation/territory marking UI
6. No handicap game visualization
7. No time display for moves

### Potential Enhancements
1. **SGF Support**: Import/export games
2. **Analysis Tools**: Winrate display, move suggestions
3. **Replay Controls**: Slider for quick navigation, animation
4. **Keyboard Shortcuts**: Numpad for navigation
5. **Game Search**: Filter by player, date, result
6. **Statistics**: Win/loss by player, performance trends
7. **Themes**: Dark mode, custom board colors
8. **Accessibility**: High contrast mode, screen reader support

---

## Testing & Quality Metrics

### Test Coverage
- Game rules: Comprehensive (multiple test classes)
- Network client: Integration tests
- GUI components: Widget/tab tests
- Error handling: Multiple test cases

### Code Quality Tools
```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/

# Run tests with coverage
pytest --cov=cgosview tests/
```

---

## Installation & Usage

### Installation
```bash
# Clone repository and navigate to project
cd /path/to/cgosview

# Install in development mode
pip install -e ".[dev]"

# Or install for regular use
pip install .
```

### Running Application
```bash
# Use default server (cgos-hg.de:6809)
cgosview

# Connect to custom server
cgosview myserver.com 1234

# Set game limits
cgosview --max-games 5

# Set connection timeout
cgosview --timeout 20.0
```

---

## File Manifest

| File | Size | Purpose |
|------|------|---------|
| `__main__.py` | 64 lines | Application startup |
| `__init__.py` | 24 lines | Package metadata |
| `config.py` | 120 lines | Config/arg parsing |
| `gogame.py` | 457 lines | Go rules engine |
| `cgos_client.py` | 702 lines | Network client |
| `main_window.py` | 486 lines | Main UI window |
| `game_tab.py` | 287 lines | Game tab widget |
| `board_widget.py` | 310 lines | Board rendering |
| `move_history_table.py` | 191 lines | Move list display |
| `signals.py` | 43 lines | Qt signals |
| `threading.py` | 120 lines | Async thread helpers |
| Test files | 1,963 lines | Unit/integration tests |
| **Total** | **~4,783** | |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────┐
│         PyQt6 Main Window                   │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┬──────────────────────┐  │
│  │ Status Label │ Game List / Tabs     │  │
│  ├──────────────┼──────────────────────┤  │
│  │              │ GameTab 1            │  │
│  │              │ ┌─────────┬─────────┐│  │
│  │              │ │ Board   │ Moves   ││  │
│  │              │ │Widget   │ Table   ││  │
│  │              │ │         │         ││  │
│  │              │ └─────────┴─────────┘│  │
│  │              │ [Nav Controls]       │  │
│  │              │                      │  │
│  │              │ GameTab 2 ...        │  │
│  │              │                      │  │
│  └──────────────┴──────────────────────┘  │
└──────────────────┬───────────────────────┘
                   │
              Qt Signals
    ┌──────────────┴──────────────┐
    ↓                             ↓
Main Thread              Async Thread
    │                        │
    │                        │
    └──────────────┬─────────┘
                   │ (TCP Socket)
                   ↓
              CGOS Server
              (cgos-hg.de:6809)
```

---

## Performance Considerations

### Optimizations
1. **Board State Caching**: History dictionary prevents full replays
2. **Flat Array Representation**: O(1) index calculations
3. **Flood-Fill Termination**: Early exit on liberty or boundary
4. **Async Network**: Non-blocking I/O with event loop
5. **Lazy Board Rendering**: Only redraw on updates

### Scalability
- Games in game list: Limited to 50 (configured)
- Concurrent game tabs: Limited to 10 (hardcoded)
- Board sizes: 7-25 (all standard Go sizes)
- Network throughput: Depends on server send rate
- Memory: ~1MB per game (history + moves)

---

## Summary

CGOSVIEW is a well-architected, feature-complete Go game viewer with:
- **Robust game rules implementation** with full validation
- **Async network communication** with reconnection logic
- **Professional PyQt6 GUI** with tabbed multi-game support
- **Comprehensive test coverage** for critical components
- **Clean architecture** separating game logic, network, and UI
- **Proper threading** for non-blocking operations

The project demonstrates best practices in Python development: type hints, docstrings, logging, error handling, and testing. It's production-ready for viewing CGOS games with a modern, responsive interface.

