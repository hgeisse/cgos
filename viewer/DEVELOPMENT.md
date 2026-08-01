# CGOSVIEW Development Guide

Complete guide for developers working on the CGOSVIEW Python port.

## Getting Started

### 1. Clone and Setup

```bash
# Clone repository
git clone <repo-url>
cd cgosview-python

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"
```

### 2. Verify Installation

```bash
# Run tests
pytest tests/ -v

# Check code quality
mypy src/cgosview
black --check src/
ruff check src/

# Run application
python -m cgosview
```

## Project Structure

```
cgosview-python/
├── src/cgosview/           # Main package
│   ├── __init__.py
│   ├── __main__.py         # Entry point
│   ├── game/               # Go game engine
│   │   ├── __init__.py
│   │   └── gogame.py       # 400+ lines, fully tested
│   ├── network/            # CGOS server communication
│   │   ├── __init__.py
│   │   └── cgos_client.py  # Async client
│   ├── gui/                # PyQt6 GUI components
│   │   ├── __init__.py
│   │   ├── main_window.py  # Main application
│   │   └── board_widget.py # Board rendering
│   └── utils/              # Utilities
│       └── __init__.py
├── tests/                  # Unit tests
│   ├── __init__.py
│   ├── test_gogame.py      # 70+ game tests
│   ├── test_network.py     # Network tests (future)
│   └── test_gui.py         # GUI tests (future)
├── pyproject.toml          # Project configuration
├── README.md               # User guide
├── DEVELOPMENT.md          # This file
└── LICENSE                 # MIT License
```

## Development Workflow

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_gogame.py -v

# Run specific test class
pytest tests/test_gogame.py::TestSimpleMoves -v

# Run specific test
pytest tests/test_gogame.py::TestSimpleMoves::test_simple_move -v

# Run with coverage report
pytest tests/ --cov=src/cgosview --cov-report=html

# Run tests matching pattern
pytest tests/ -k "capture" -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Check formatting
black --check src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/cgosview --strict

# All checks
make check  # (if Makefile available)
```

### Running Application

```bash
# Via console script
cgosview

# Via module
python -m cgosview

# With debug logging
LOGLEVEL=DEBUG python -m cgosview
```

## Architecture Deep Dive

### Game Engine (`gogame.py`)

**Key Classes:**
- `Stone` (IntEnum): Board states (EMPTY=0, BLACK=1, WHITE=2, BORDER=3)
- `MoveError` (IntEnum): Error codes (-4 to -1)
- `GoGame`: Main game logic class

**Core Methods:**

```python
class GoGame:
    def __init__(self, size: int)
        """Initialize game, size 7-25"""
    
    def make_move(move: str) -> int
        """Execute move, return error code or capture count"""
    
    def _capture_group(target: int) -> List[int]
        """Find captured stones using flood-fill"""
    
    def get_board() -> List[int]
        """Return current board state (interior only)"""
```

**Board Representation:**

- Flat list with borders
- Layout: `(size+2) rows × (size+1) columns`
- Index calculation: `index = y * n1 + x`
- Borders prevent boundary checks

**Example:**
```python
# 19x19 board
board = [BORDER, BORDER, ..., EMPTY, BLACK, ..., BORDER, ...]
# size = 19
# n1 = 20
# nnn = 420 (21*20)
# Position E5 = (5*20) + 5 = 105
```

### Network Client (`cgos_client.py`)

**Key Classes:**
- `GameInfo`: Game metadata dataclass
- `CGOSClient`: Async CGOS server connection

**Protocol Reference**: See `CGOS_PROTOCOL.md` for complete specification of the CGOS protocol, including:
- Message format and field specifications
- Data exchange flow and examples
- Move notation and error handling
- Connection lifecycle and streaming behavior

**Usage:**

```python
# Create client
client = CGOSClient("cgos.boardspace.net", 6867)

# Set callback
client.on_game_update = handle_game

# Connect and receive
await client.connect()
await client.receive_games()  # Blocks until disconnect
```

### GUI Components

**MainWindow:**
- Game list display
- Connection controls
- Board display
- Navigation buttons

**GameBoardWidget:**
- Custom QPainter rendering
- Stone drawing (circles)
- Grid lines
- Coordinate labels
- Handicap points

## Common Development Tasks

### Adding a New Move Validation Rule

1. Add test first in `test_gogame.py`:
```python
def test_my_new_rule(self):
    game = GoGame(9)
    result = game.make_move("E5")
    assert result == expected_value
```

2. Implement in `GoGame.make_move()`:
```python
def make_move(self, move: str) -> int:
    # ... existing code ...
    
    # NEW: My validation rule
    if some_condition:
        return MoveError.SOME_ERROR
```

3. Run tests:
```bash
pytest tests/test_gogame.py::TestMyNewRule -v
```

### Adding a GUI Feature

1. Create new widget in appropriate file
2. Add to MainWindow
3. Connect signals/slots
4. Add tests in `test_gui.py`

Example:
```python
# In main_window.py
self.my_button = QPushButton("My Feature")
self.my_button.clicked.connect(self._on_my_feature)

def _on_my_feature(self):
    # Handle button click
    pass
```

### Adding Network Functionality

1. Extend `CGOSClient` in `cgos_client.py`
2. Add protocol parsing in `_parse_game_line()`
3. Add async methods as needed
4. Add tests in `test_network.py`

Example:
```python
async def send_command(self, cmd: str) -> bool:
    if not self.writer:
        return False
    self.writer.write((cmd + "\n").encode())
    await self.writer.drain()
    return True
```

## Testing Strategy

### Unit Tests (70+ tests in test_gogame.py)

Categories:
- **Initialization**: Board setup, size validation
- **Move Parsing**: Notation handling, errors
- **Move Execution**: Simple moves, alternating colors
- **Captures**: Single/multiple stones, surrounding
- **Suicide**: Detection, prevention
- **KO Rule**: Enforcement, validation
- **Undo**: Move reversal, history
- **Edge Cases**: Corners, boundaries

### Test Structure

```python
class TestCategory:
    """Test a specific feature."""
    
    @pytest.fixture
    def game(self):
        """Setup fixture."""
        return GoGame(9)
    
    def test_specific_case(self, game):
        """Test specific case."""
        result = game.make_move("E5")
        assert result == expected
```

### Running Specific Tests

```bash
# By category
pytest tests/test_gogame.py::TestCaptures -v

# By pattern
pytest tests/test_gogame.py -k "capture" -v

# With coverage for specific file
pytest tests/test_gogame.py --cov=src/cgosview/game
```

## Code Style Guide

### Python Style

- Follow PEP 8
- Use type hints for all functions
- Use docstrings for all public functions
- Maximum line length: 100 characters

### Type Hints

```python
def function(param: str, count: int = 5) -> bool:
    """Function description with type hints."""
    pass

# For complex types
from typing import List, Dict, Optional, Tuple

def complex_func(
    items: List[str],
    mapping: Dict[str, int],
    optional: Optional[str] = None
) -> Tuple[bool, str]:
    """Complex function with type hints."""
    pass
```

### Docstrings

```python
def method(self, param: str) -> int:
    """
    Short description on first line.
    
    Longer description can go here with more details
    about what the method does and why.
    
    Args:
        param: Description of param
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When something is invalid
    
    Example:
        >>> result = method("test")
        >>> print(result)
        0
    """
    pass
```

## Debugging

### Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.exception("Exception occurred")
```

### Using PyCharm Debugger

1. Set breakpoint (click line number)
2. Run with debugging: `Debug > Debug 'pytest'`
3. Step through code with F10/F11
4. Inspect variables in Variables panel

### Using pdb

```python
import pdb; pdb.set_trace()  # Breakpoint
```

Or run with:
```bash
pytest tests/test_gogame.py --pdb
```

## Performance Optimization

### Profiling

```python
import cProfile
import pstats

cProfile.run('game.make_move("E5")', 'profile_stats')
p = pstats.Stats('profile_stats')
p.sort_stats('cumulative').print_stats(10)
```

### Memory Usage

```python
import tracemalloc

tracemalloc.start()
game = GoGame(19)
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 10**6}MB; Peak: {peak / 10**6}MB")
```

## Documentation

### Building Docs

```bash
# Install Sphinx
pip install sphinx

# Create docs
sphinx-quickstart docs/

# Build HTML
cd docs/
make html
```

### Writing Documentation

- Use Markdown for standalone docs
- Use docstrings for code documentation
- Keep examples up-to-date
- Update CHANGELOG.md for significant changes

## CI/CD

### GitHub Actions (example)

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.10, 3.11, 3.12]
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov
      - run: mypy src/
      - run: black --check src/
```

## Troubleshooting

### Import Errors

```python
# If "ModuleNotFoundError: No module named 'cgosview'"
pip install -e .  # Reinstall in development mode
```

### Test Failures

```bash
# Run with verbose output
pytest tests/ -vv

# Run with print statements shown
pytest tests/ -s

# Run specific test with debug
pytest tests/test_gogame.py::TestMyTest -vv --tb=short
```

### Type Checking Errors

```bash
# Run mypy
mypy src/cgosview

# Show full error
mypy src/cgosview --show-traceback

# Ignore file temporarily
# Add: # type: ignore at end of line
```

## Release Checklist

Before releasing a new version:

- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md`
- [ ] Run all tests: `pytest tests/ -v`
- [ ] Check coverage: `pytest --cov=src/cgosview`
- [ ] Type check: `mypy src/cgosview --strict`
- [ ] Format code: `black src/`
- [ ] Build package: `python -m build`
- [ ] Test installation: `pip install dist/cgosview-*.whl`
- [ ] Create git tag: `git tag v1.0.0`
- [ ] Push to repository

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes and commit: `git commit -am 'Add my feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Create Pull Request
6. Ensure all checks pass

## Project Documentation

- **CGOS_PROTOCOL.md** - Complete CGOS protocol specification
- **README.md** - User guide and overview
- **IMPLEMENTATION_SUMMARY.md** - Implementation status and details
- **PROJECT_SUMMARY.txt** - Quick reference guide

## External Resources

- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [asyncio Tutorial](https://docs.python.org/3/library/asyncio.html)
- [pytest Documentation](https://docs.pytest.org/)
- [PEP 8 Style Guide](https://pep8.org/)
- [mypy Documentation](http://mypy-lang.org/)

## Support

For questions or issues:
- Check existing GitHub issues
- Create new issue with detailed description
- Contact maintainers
