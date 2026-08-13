# CGOSVIEW - Developer Guide

This guide covers development setup, architecture deep-dives, and extension patterns for CGOSVIEW contributors.

---

## Development Setup

### Prerequisites
- Python 3.10 or higher
- pip and virtual environment tools
- Git
- C++ compiler (for building PyQt6 from source if needed)

### Initial Setup

```bash
# Clone repository
cd cgosview

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Verify installation
python -m cgosview
```

### IDE Setup

**PyCharm/IntelliJ**:
- Mark `src/` as Sources Root
- Mark `tests/` as Test Sources Root
- Enable pytest plugin

**VSCode**:
- Install Python extension
- Configure `.vscode/settings.json`:
```json
{
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"]
}
```

---

## Architecture Deep Dive

### Board Representation

The board is stored as a flat 1D list with borders:

```
Physical Layout (19x19 with borders):
┌─ Border row ─┐
│ B B B B ... B │  (BORDER = 3)
│ B . . . ... . │  (first interior row, B=border, .=empty/stone)
│ B . . . ... . │
│ B . . . ... . │
│ ... 
│ B B B B ... B │
└─ Border ─────┘

Array Index Calculation:
  y * (size + 1) + x
  where y,x are 1-indexed board coordinates (1-20 for 19x19 with borders)

Navigation Offsets:
  self.directions = [-1, 1, n1, -n1]
  Left: -1, Right: +1, Down: +n1, Up: -n1
  (n1 = size + 1)

Benefits:
- No boundary checks needed (borders act as walls)
- O(1) index calculation
- Flood-fill terminates on borders naturally
```

### Flood-Fill Algorithm

```python
def _capture_group(self, target: int) -> List[int]:
    """
    Finds all connected stones of same color starting from target.
    Returns empty list if group has at least one liberty (empty adjacent space).
    
    Algorithm:
    1. Initialize visited set with target position
    2. Initialize stack with target for DFS
    3. For each position in stack:
       - Check 4 adjacent positions
       - If empty (liberty found): return [] (group alive)
       - If same color: add to group and stack
    4. If stack empties without finding liberty: group captured
    """
    target_stone = self.board[target]
    visited = {target}
    captured = [target]
    stack = [target]
    
    while stack:
        pos = stack.pop()
        for direction in self.directions:
            neighbor = pos + direction
            if neighbor in visited:
                continue
            visited.add(neighbor)
            neighbor_stone = self.board[neighbor]
            
            if neighbor_stone == Stone.EMPTY:
                return []  # Found liberty - group alive
            if neighbor_stone == target_stone:
                captured.append(neighbor)
                stack.append(neighbor)
    
    return captured  # No liberties - captured
```

**Time Complexity**: O(board_size²) worst case (entire board)
**Space Complexity**: O(board_size²) for visited set

### Move Validation Pipeline

```
make_move(move: str) → int
    ↓
1. Parse Move
   move_to_index(move) → index or error code (-4)
   
2. Check Preconditions
   - Correct player color? (black on even moves)
   - Target square empty? (-3: occupied)
   
3. Simulate Move
   - Place stone temporarily
   - Check captures (enemy groups)
   - Remove captured stones
   
4. Validate Suicide Rule
   - After captures, does own group have liberties?
   - If no: undo move, return -1 (suicide)
   
5. Check KO Rule
   - Does this board state exist in history?
   - If yes: undo move, return -2 (KO)
   
6. Commit Move
   - Record in history
   - Increment move counter
   - Return capture count (≥0)
```

### Move History

```python
self.history: Dict[int, List[int]] = {0: initial_board}
self.moves: Dict[int, str] = {}

# After move 1: A5
self.history[1] = board_after_A5
self.moves[0] = "A5"

# After move 2: B5
self.history[2] = board_after_B5
self.moves[1] = "B5"

# Undo last move
self.current_move_number = 1
self.board = self.history[1].copy()
```

**Purpose**: 
- KO detection (compare full boards)
- Move replay (reconstructable without move list)
- Game navigation (jump to any position)

---

## Network Protocol

### CGOS Protocol (v1 Viewer)

```
Client Connection Flow:
1. TCP connect to cgos-hg.de:6809
2. Send: "VERSION 1\n" (protocol handshake)
3. Server responds with game list
4. Receive game updates as they occur

Game Update Format (example):
gid:12345 date:2026-08-06 time:15:30:45 size:19 komi:7.5
white:Computer1 black:Computer2 result:
E5 T15 C3 D4 ...  (move sequence, space-delimited)

Game Finished Format:
... result:W+2.5  (or B+Resign, W+Resign, etc.)
```

### Client State Machine

```
        ┌──────────────┐
        │ DISCONNECTED │
        └──────┬───────┘
               │ connect()
               ↓
        ┌──────────────┐
        │ CONNECTING   │
        └──────┬───────┘
               │
      ┌────────┴────────┐
      ↓                 ↓
  ┌─────────┐    ┌─────────┐
  │CONNECTED│    │  ERROR  │
  └────┬────┘    └────┬────┘
       │ disconnect() |
       │              | retry logic
       └──────┬───────┘
              ↓
         DISCONNECTED
```

### Reconnection Strategy

```python
# Exponential backoff
async def connect_with_retry():
    for attempt in range(max_retries):
        if await connect():
            return True
        
        if attempt < max_retries - 1:
            delay = reconnect_base_delay * (2 ** attempt)
            # Delays: 1s, 2s, 4s, 8s, 16s
            await asyncio.sleep(delay)
    
    return False
```

---

## GUI Architecture

### Signal Flow

```
Network Thread                    Main Thread
    │                                  │
    ├─ on_game_added() ────────────────→ game_added.emit()
    │                                        │
    │                                        ↓
    │                           main_window.on_game_added()
    │                                  - Create GameTab
    │                                  - Add to QTabWidget
    │                                  - Update game list
    │
    ├─ on_game_updated() ───────────────→ game_updated.emit()
    │                                        │
    │                                        ↓
    │                           main_window.on_game_updated()
    │                                  - Get GameTab
    │                                  - Replay moves
    │                                  - Redraw board
```

### Widget Hierarchy

```
MainWindow (QMainWindow)
├── Central Widget (QWidget)
│   └── Main Layout (QVBoxLayout)
│       ├── Status Bar
│       │   ├── Connection Status Label
│       │   ├── Server Info Label
│       │   └── Game Count Label
│       │
│       ├── Tab Widget (QTabWidget)
│       │   ├── GameTab 1 (QWidget)
│       │   │   └── Layout (QVBoxLayout)
│       │   │       ├── Game Info Label
│       │   │       ├── Splitter (QSplitter)
│       │   │       │   ├── GameBoardWidget (custom)
│       │   │       │   └── MoveHistoryTable (custom)
│       │   │       └── Navigation Controls
│       │   │           ├── << (first)
│       │   │           ├── < (prev)
│       │   │           ├── > (next)
│       │   │           └── >> (last)
│       │   │
│       │   ├── GameTab 2
│       │   │   └── (same structure)
│       │   │
│       │   └── ...
│       │
│       └── Game List Sidebar
│           └── QListWidget (active games)
```

### Threading

```python
class MainWindow:
    def __init__(self):
        self.async_thread = AsyncioThread()  # Create async thread
        self.async_thread.start()            # Start event loop
        self.client = CGOSClient(...)
        
        # Connect network callbacks to GUI signals
        self.network_signals = NetworkSignals()
        self.network_signals.game_added.connect(self.on_game_added)
        
        # Run network code in async thread
        self.async_thread.run_async(self.client.receive_games())
    
    @pyqtSlot(GameInfo)  # Runs on main thread (thread-safe)
    def on_game_added(self, game_info: GameInfo):
        # GUI updates here are thread-safe (Qt handles it)
        tab = GameTab(game_info.gid, game_info)
        self.tabs.addTab(tab, f"Game {game_info.gid}")
```

---

## Extension Points

### Adding New Board Rendering Features

```python
# In game_tab.py
class GameTab(QWidget):
    def _create_ui(self):
        # ... existing code ...
        
        # Add new feature
        self.variation_board = VariationBoardWidget()
        splitter.addWidget(self.variation_board)
    
    def _load_game(self, game_info):
        # ... existing code ...
        
        # Populate variation board
        self.variation_board.show_variations(variations)
```

### Adding Game Analysis

```python
# New file: gui/analysis_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

class AnalysisPanel(QWidget):
    move_analyzed = pyqtSignal(str, float)  # move, evaluation
    
    def __init__(self):
        super().__init__()
        # Create panel UI
    
    def analyze_position(self, game: GoGame):
        # Call AI engine, emit results
        pass

# In GameTab._create_ui():
self.analysis_panel = AnalysisPanel()
splitter.addWidget(self.analysis_panel)
```

### Adding Configuration UI

```python
# New file: gui/preferences_dialog.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout
from cgosview.config import ViewerConfig

class PreferencesDialog(QDialog):
    def __init__(self, config: ViewerConfig):
        super().__init__()
        self.config = config
        # Create preference controls
        # Save settings to file
    
    def accept(self):
        # Update config from controls
        super().accept()

# In MainWindow._create_ui():
menu = self.menuBar().addMenu("File")
menu.addAction("Preferences", self._show_preferences)

def _show_preferences(self):
    dialog = PreferencesDialog(self.config)
    dialog.exec()
```

### Adding SGF Import/Export

```python
# New module: utils/sgf.py
from cgosview.game.gogame import GoGame
from pathlib import Path

class SGFWriter:
    def __init__(self, game: GoGame, game_info: GameInfo):
        self.game = game
        self.game_info = game_info
    
    def write(self, path: Path) -> bool:
        sgf = self._build_sgf()
        path.write_text(sgf)
        return True
    
    def _build_sgf(self) -> str:
        # Build SGF format
        moves = self.game.list_moves()
        sgf = f"""(;GM[1]FF[4]
CA[UTF-8]
AP[CGOSVIEW:1.0]
RU[Japanese]
SZ[{self.game.size}]
KM[{self.game_info.komi}]
PW[{self.game_info.white_player}]
PB[{self.game_info.black_player}]
RE[{self.game_info.result}]
"""
        # Add moves...
        return sgf

class SGFReader:
    @staticmethod
    def read(path: Path) -> Tuple[GoGame, GameInfo]:
        # Parse SGF, replay moves
        pass

# In MainWindow:
def _export_sgf(self):
    tab = self.current_tab()
    if tab:
        writer = SGFWriter(tab.current_game, tab.game_info)
        path = Path("game_export.sgf")
        writer.write(path)
```

### Adding Custom Themes

```python
# New file: gui/themes.py
from typing import Dict

class Theme:
    def __init__(self, name: str, styles: Dict[str, str]):
        self.name = name
        self.styles = styles
    
    @property
    def stylesheet(self) -> str:
        return "\n".join(f"{k} {{ {v} }}" 
                        for k, v in self.styles.items())

DARK_THEME = Theme("Dark", {
    "MainWindow": "background-color: #1e1e1e; color: #ffffff;",
    "GameBoardWidget": "background-color: #2d2d2d;",
})

LIGHT_THEME = Theme("Light", {
    "MainWindow": "background-color: #ffffff; color: #000000;",
    "GameBoardWidget": "background-color: #f5f5f5;",
})

# In MainWindow:
def set_theme(self, theme: Theme):
    self.setStyleSheet(theme.stylesheet)
```

---

## Testing Strategy

### Unit Testing GoGame

```python
# tests/test_gogame.py
import pytest
from cgosview.game.gogame import GoGame, MoveError, Stone

class TestCaptures:
    def test_simple_capture(self):
        game = GoGame(9)
        # Black plays around white stone
        game.make_move("E5")  # Black
        game.make_move("E4")  # White
        game.make_move("E6")  # Black
        game.make_move("E3")  # White
        game.make_move("D4")  # Black
        game.make_move("F4")  # White
        result = game.make_move("F5")  # Black captures
        
        assert result == 1  # Captured 1 stone
        assert game.board[game.move_to_index("E4")] == Stone.EMPTY

    def test_no_suicide(self):
        """Verify suicide moves are rejected"""
        game = GoGame(9)
        # Setup surrounded black group
        # ...
        result = game.make_move("illegal_suicide_move")
        assert result == MoveError.SUICIDE
```

### Mock Network Testing

```python
# tests/conftest.py
@pytest.fixture
def mock_cgos_server():
    """Mock CGOS server for testing"""
    class MockServer:
        async def handle_connection(self, reader, writer):
            # Simulate server responses
            pass
    
    return MockServer()

@pytest.fixture
async def cgos_client():
    """Create client connected to mock server"""
    client = CGOSClient("localhost", 9999)
    await client.connect()
    yield client
    await client.disconnect()

# tests/test_network_integration.py
async def test_game_update(cgos_client):
    games = []
    cgos_client.on_game_added = lambda g: games.append(g)
    
    # Trigger server to send game
    await asyncio.sleep(0.1)
    
    assert len(games) == 1
```

### GUI Testing

```python
# tests/test_gui_integration.py
import pytest
from PyQt6.QtWidgets import QApplication
from cgosview.gui.main_window import MainWindow

@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])

def test_main_window_creation(qapp):
    window = MainWindow()
    assert window.isVisible() == False  # Not shown yet
    window.show()
    assert window.isVisible()

def test_game_tab_creation(qapp):
    from cgosview.gui.game_tab import GameTab
    from cgosview.network.cgos_client import GameInfo
    
    info = GameInfo(
        gid=1,
        date="2026-08-06",
        time="15:30:00",
        board_size=19,
        komi=7.5,
        white_player="CPU1",
        black_player="CPU2"
    )
    
    tab = GameTab(1, info)
    assert tab.gid == 1
    assert tab.board_widget is not None
    assert tab.move_history_table is not None
```

### Coverage Targets

```bash
# Generate coverage report
pytest --cov=cgosview --cov-report=html tests/

# View report
open htmlcov/index.html

# Target: 80% overall, 90% for game logic
```

---

## Performance Optimization

### Profiling

```python
# In development
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
game = GoGame(19)
for move in move_list:
    game.make_move(move)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20
```

### Optimization Ideas

1. **Board Rendering**:
   - Cache stone pixmaps (already done)
   - Use OpenGL for large boards
   - Batch Qt drawing calls

2. **Game Logic**:
   - Profile flood-fill (should be fast)
   - Cache board state hashes for KO detection
   - Lazy board cloning

3. **Network**:
   - Buffer game updates
   - Compress move sequences
   - Implement game streaming protocol

---

## Debugging

### Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Move: %s, Index: %d", move, index)
logger.info("Game started: %s vs %s", black, white)
logger.warning("Slow move processing: %0.2f ms", duration)
logger.error("Failed to parse move: %s", error)
```

### Breakpoints

```python
# PyCharm: Shift+F8 to set breakpoint
game.make_move("E5")  # Stop here
# Variables visible in debugger

# Command-line debugging
python -m pdb -m cgosview
(pdb) break cgosview/game/gogame.py:220  # Set breakpoint
(pdb) continue
```

### Assertions

```python
# Enable in development
assert len(self.board) == self.nnn, f"Board size mismatch: {len(self.board)}"
assert 0 <= index < len(self.board), f"Index out of range: {index}"
```

---

## Code Style Guide

### Naming Conventions

```python
# Functions: lowercase_with_underscores
def make_move(move: str) -> int:
    pass

# Classes: CamelCase
class GoGame:
    pass

# Constants: UPPER_CASE
BOARD_SIZE = 19

# Private methods: _leading_underscore
def _capture_group(self, target: int) -> List[int]:
    pass

# Type hints: Always use
def make_move(self, move: str) -> int:
    pass

def get_games(self) -> Dict[int, GameInfo]:
    pass
```

### Docstring Format

```python
def make_move(self, move: str) -> int:
    """
    Execute a move with full validation.
    
    Validates according to all Go rules:
    1. Move format is valid
    2. Target square is empty
    3. Move doesn't result in suicide (unless capturing)
    4. Move doesn't violate KO rule
    
    Args:
        move: Move in algebraic notation or "PASS"
    
    Returns:
        -4: Format error
        -3: Square occupied
        -2: KO violation
        -1: Suicide
        0: Valid pass
        ≥1: Captures
    
    Side effects:
        - Updates board state and move history
        - Does NOT update if validation fails
    
    Example:
        >>> game = GoGame(19)
        >>> result = game.make_move("E5")
        >>> if result >= 0:
        ...     print(f"Valid, captured {result}")
    """
```

### Line Length and Formatting

```python
# Black will format to 100 chars max
self.long_function_name(
    argument1,
    argument2,
    argument3,
)

# Dict/List formatting
config = ViewerConfig(
    server="cgos-hg.de",
    port=6809,
    max_games=50,
)
```

---

## Release Process

### Version Bumping

```bash
# In pyproject.toml
[project]
version = "1.0.1"  # Increment version

# Update changelog
# git add pyproject.toml CHANGELOG.md
# git commit -m "Release 1.0.1"
# git tag -a v1.0.1 -m "Version 1.0.1"
# git push origin main --tags
```

### Building Distribution

```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Test upload
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

---

## Contributing

### Pull Request Process

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes with tests
3. Run quality checks:
   ```bash
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   pytest tests/
   ```
4. Push branch and create PR
5. Address review feedback
6. Squash commits: `git rebase -i main`
7. Merge to main

### Commit Messages

```
[CATEGORY] Brief description (50 chars max)

Longer explanation if needed (wrap at 72 chars).
Explain why this change is needed, not what changed.

Fixes #123
```

Categories:
- `[FEAT]` - New feature
- `[FIX]` - Bug fix
- `[REFACTOR]` - Code refactoring
- `[TEST]` - Test additions/fixes
- `[DOCS]` - Documentation
- `[PERF]` - Performance improvement

---

## Resources

### Python Best Practices
- [PEP 8](https://pep8.org/) - Style Guide
- [PEP 484](https://www.python.org/dev/peps/pep-0484/) - Type Hints
- [PEP 257](https://www.python.org/dev/peps/pep-0257/) - Docstrings

### PyQt6
- [Official Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Qt for Python](https://doc.qt.io/qtforpython/)
- [Threading Guide](https://www.riverbankcomputing.com/static/Docs/PyQt6/qthread.html)

### Go Rules
- [Rules of Go](https://en.wikipedia.org/wiki/Rules_of_Go)
- [KO Rule](https://en.wikipedia.org/wiki/Rules_of_Go#Ko_rule)
- [Capture Mechanics](https://en.wikipedia.org/wiki/Rules_of_Go#Captures)

### Asyncio
- [Asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [Real Python: Async I/O](https://realpython.com/async-io-python/)

---

## Summary

CGOSVIEW is architected for extensibility with clear separation of concerns:
- **Game Logic**: Pure, testable Go rules engine
- **Network**: Async, reconnection-resilient CGOS client
- **GUI**: Modular PyQt6 with signal-based threading
- **Config**: Flexible command-line configuration

Extend it by adding new GUI panels, analysis engines, or persistence layers while keeping the core game logic isolated and well-tested.

