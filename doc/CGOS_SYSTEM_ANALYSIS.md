# CGOS (Computer Go Server) - Client-Server System Analysis

## 1. PROJECT STRUCTURE

### Directory Layout
```
/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/
├── README                          # Main project overview
├── LICENSE                         # License file
├── client/                         # Client application directory
│   ├── README                      # Client setup instructions
│   ├── src/                        # Client source code
│   │   ├── cgosclient.py          # Main client program (768 lines)
│   │   ├── gtpengine.py           # GTP engine communication (531 lines)
│   │   ├── sgf.py                 # SGF game record handling (184 lines)
│   │   ├── config.py              # Client configuration parsing (112 lines)
│   │   └── common.py              # Common definitions
│   ├── configs/                   # Configuration files
│   │   ├── generic/               # Template configuration files
│   │   │   ├── simple.yaml        # Simple configuration example
│   │   │   ├── sample.yaml        # Sample configuration
│   │   │   └── client.yaml        # Full client configuration template
│   │   ├── examples/              # Example configurations (client1-4.yaml)
│   │   └── tests/                 # Test configurations (sample0-7.yaml)
│   ├── doc/                       # Client documentation
│   └── killfiles/
│       └── kill_client            # Kill file to stop client
│
├── server/                        # Server application directory
│   ├── README                     # Server setup instructions
│   ├── cgos/                      # Server source code package
│   │   ├── server.py             # Server entry point (17 lines)
│   │   ├── webuild.py            # Web page builder
│   │   ├── set_anchors.py        # Anchor management
│   │   ├── reset_password.py     # Password reset utility
│   │   ├── app/                  # Application logic
│   │   │   ├── cgos.py           # Main server logic (2026 lines)
│   │   │   ├── client.py         # Client connection handler (111 lines)
│   │   │   ├── config.py         # Server configuration (135 lines)
│   │   │   └── rating.py         # Elo rating calculations (24 lines)
│   │   ├── gogame/               # Go game logic
│   │   │   ├── __init__.py      # Package exports
│   │   │   ├── go.py            # Go board implementation
│   │   │   └── game.py          # Game state and SGF generation
│   │   ├── util/                # Utility modules
│   │   │   ├── logutils.py      # Logging utilities
│   │   │   └── timeutils.py     # Time utilities
│   │   ├── webuild_html/        # Static web assets
│   │   │   ├── index.html       # Root HTML page
│   │   │   └── cgosLogo.png     # Logo image
│   │   └── webuild_templates/   # Jinja2 HTML templates
│   │       ├── standings.jinja.html
│   │       ├── crosstable.jinja.html
│   │       └── archive.jinja.html
│   ├── configs/                 # Configuration files
│   │   ├── generic/             # Generic configurations
│   │   │   ├── cgos9.yaml      # 9x9 board config
│   │   │   ├── cgos13.yaml     # 13x13 board config
│   │   │   └── cgos19.yaml     # 19x19 board config
│   │   ├── examples/            # Example configurations
│   │   └── logging/
│   │       └── log.yaml         # Logging configuration
│   ├── requirements.txt          # Python dependencies
│   ├── killfiles/               # Kill files for stopping services
│   │   ├── kill_cgos9
│   │   ├── kill_cgos13
│   │   ├── kill_cgos19
│   │   ├── kill_webuild9
│   │   ├── kill_webuild13
│   │   └── kill_webuild19
│   ├── check.sh                 # Checker script
│   └── run_test.sh             # Test runner script
│
├── STASH/
└── doc/
    └── doc.txt                  # Internal documentation notes
```

---

## 2. SERVER IMPLEMENTATION

### 2.1 Entry Point & Main Components

**File:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/server.py`
- Entry point that calls `runServer()` from `app.cgos`
- Error handling and tracebacks

**Main Server File:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/cgos.py` (2026 lines)

#### Key Functions:
1. **`runServer()`** (Lines 1970-2026)
   - Loads configuration from YAML file
   - Initializes database
   - Sets up logging
   - Launches asyncio event loop with `server_main()`

2. **`server_main()`** (Lines 1954-1968)
   - Starts TCP server listening on configured port
   - Creates schedule_games_task
   - Awaits server.serve_forever()

3. **`accept_connection()`** (Lines 1418+)
   - Accepts incoming client connections
   - Creates Client objects with reader/writer streams
   - Launches handle_client and read/write tasks

4. **`handle_client()`** (Lines 1456-1486)
   - Main client message dispatcher
   - Routes to player_respond, viewer_respond, or admin_respond based on client type
   - Async loop reading lines from client

### 2.2 Server State Management

**Global State (Lines 51-64):**
- `db`: SQLite3 state database connection
- `dbrec`: SQLite3 archive database connection
- `gme`: Dictionary of active games (key=gid, value=GoGame objects)
- `act`: Dictionary of active players (key=username, value=ActiveUser)
- `games`: Dictionary of Game objects in progress
- `ratingOf`: Cache of player ratings
- `viewers`: ViewerList object for game observers
- `admin`: Dictionary of admin clients

### 2.3 Client Handler - Server Side

**File:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/client.py`

The Client class manages async I/O:
- **Constructor**: Stores asyncio StreamReader/StreamWriter, creates message queues
- **readTask()**: Continuously reads from socket into _readQueue
  - Handles both new-style (with newlines) and old Python clients
- **writeTask()**: Continuously writes _writeQueue to socket
- **send()**: Enqueues messages for writing
- **readLine()**: Awaits next message from queue

### 2.4 Message Handlers

**Player Connection Flow:**

1. **Protocol Stage** (`_handle_player_protocol`)
   - Client sends protocol ID (e1 for players, v1 for viewers)
   - Sets msg_state to "username"
   
2. **Username Stage** (`_handle_player_username`)
   - Player sends username
   - Validates name format
   - Sets msg_state to "password"

3. **Password Stage** (`_handle_player_password`)
   - Player sends password (with optional new password)
   - Validates against database
   - Creates new user if needed
   - Updates player entry in `act` dictionary
   - Sets msg_state to "waiting"

4. **Game Playing** (`_handle_player_genmove`)
   - Receives move from engine
   - Validates move using GoGame logic
   - Updates game state
   - Sends move to opponent
   - Handles time management
   - Detects game end conditions

5. **Game Over** (`_handle_player_gameover`)
   - Confirms game completion
   - Records result in database
   - Updates Elo ratings

---

## 3. CLIENT IMPLEMENTATION

### 3.1 Entry Point

**File:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/cgosclient.py` (768 lines)

**CGOSClient Class:**
- Main client application managing engine and server communication
- Uses socket-based communication (not async)
- Blocking I/O with makefile wrapper

### 3.2 Key Methods

**Initialization (`__init__`):**
- Takes list of engine configurations
- Initializes logging (file + console)
- Sets up state variables for game management
- Configures kill file for graceful shutdown

**Connection (`connect`):**
- Establishes TCP socket to server
- Wraps in text mode with UTF-8 encoding
- Creates socketfile for line-based I/O

**Main Loop (`mainloop`):**
- Attempts connection with backoff retry
- Calls _handlerloop for command processing
- Handles engine switching
- Reconnects on failure

**Handler Loop (`_handlerloop`):**
- Reads lines from server socket
- Dispatches to `_handle_*` methods via reflection
- Exits on finished flag or engine switch

### 3.3 Client Message Handlers

1. **`_handle_protocol`**
   - Receives "protocol genmove_analyze" from server
   - Responds with client ID and capability flag
   - Determines if server supports analyze info

2. **`_handle_username`**
   - Server requests username
   - Client responds with configured username

3. **`_handle_password`**
   - Server requests password
   - Client responds with configured password

4. **`_handle_setup`** (Most Complex)
   - Receives game setup parameters:
     - Game ID
     - Board size
     - Komi
     - Time per player (milliseconds)
     - Player names with ratings
     - Optional: moves to catch up on
   - Configures GTP engine via EngineConnector
   - Creates SGF game record
   - Plays catch-up moves if resuming

5. **`_handle_play`**
   - Server sends opponent move
   - Parameters: color, coordinate, time left
   - Notifies engine of opponent move
   - Updates SGF record

6. **`_handle_genmove`**
   - Server requests move from engine
   - Parameters: color, time left in milliseconds
   - Calls engine.requestGenMove()
   - Optionally includes analyze information
   - Responds with move and analysis

7. **`_handle_gameover`**
   - Server announces game result
   - Parameters: date, result string (e.g., "B+Resign")
   - Updates statistics (won/lost count)
   - Saves SGF file to disk if configured
   - Engine switches if configured

8. **`_handle_info`**
   - Informational message from server (logging only)
   - May trigger checkpoint time checks

### 3.4 Engine Integration

**File:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/gtpengine.py` (531 lines)

**EngineConnector Class:**
- Manages subprocess for Go engine
- Communicates via GTP (Go Text Protocol)
- Methods:
  - `notifyBoardSize(size)`: GTP "boardsize"
  - `notifyKomi(komi)`: GTP "komi"
  - `notifyTimeSettings(time_ms)`: GTP "time_settings"
  - `notifyPlay(color, coord)`: GTP "play"
  - `notifyClearBoard()`: GTP "clear_board"
  - `requestGenMove(color)`: GTP "genmove" - waits for response

**AnalyzeResultParser Class:**
- Parses "genmove_analyze" response
- Extracts move analysis info:
  - visits, winrate, prior, lcb
  - score, scaleLead
  - principal variation (pv)
  - ownership information

---

## 4. COMMUNICATION MECHANISM

### 4.1 Protocol Overview

**Type:** Text-based, line-delimited TCP protocol
**Encoding:** UTF-8
**Format:** Command followed by parameters separated by spaces

### 4.2 Client-Server Message Flow

```
CLIENT                              SERVER
|                                    |
+--- Connect (TCP) ----------------->|
|<---- protocol genmove_analyze -----|
+--- e1 cgosPython 1.0.0 ...-------->|
|<---- username ----------------------|
+--- <username> --------------------->|
|<---- password ----------------------|
+--- <password> --------------------->|
|<---- waiting (implicit) ------------|
|                                    | (Server schedules game)
|<---- setup 1 19 7.5 1800000 ....----|
+--- ready --------------------------->|
|                                    |
|                                    | (Game starts)
|<---- genmove w <time_ms> ---------|
+--- <move> [<analysis_json>] ------->|
|<---- play b <move> <time_left> ----|
+--- ready (if no next move) -------->|
|                                    |
|<---- genmove b <time_ms> ---------|
+--- <move> [<analysis_json>] ------->|
|<---- play w <move> <time_left> ----|
|                                    |
|         ... (game continues) ...   |
|                                    |
|<---- gameover <date> <result> ------|
+--- ready --------------------------->|
|                                    | (Back to waiting)
+--- quit --------------------------->|
|<---- (connection closes) ----------|
```

### 4.3 Message Types

#### Server to Client Messages:

| Message | Parameters | Purpose |
|---------|-----------|---------|
| `protocol` | `[genmove_analyze]` | Query capabilities |
| `username` | - | Request username |
| `password` | - | Request password |
| `setup` | gid boardsize komi level playerA playerB [moves...] | Initialize game |
| `play` | color coord time_left_ms | Opponent move |
| `genmove` | color time_left_ms | Request move generation |
| `gameover` | date result | Announce game end |
| `info` | message... | Informational message |

#### Client to Server Messages:

| Message | Parameters | Purpose |
|---------|-----------|---------|
| `e1` | client_id [genmove_analyze] | Protocol announcement |
| `v1` | viewer_id | Viewer protocol |
| username | - | Username response |
| password | - | Password response |
| move | [analysis_json] | Move response (line without command name) |
| `ready` | - | Ready for next game |
| `quit` | - | Disconnect |

### 4.4 Server-side Handlers

**Message Dispatching** (`player_respond` function, line 655):
- Routes based on `msg_state` (state machine):
  - `protocol`: _handle_player_protocol
  - `username`: _handle_player_username
  - `password`: _handle_player_password
  - `genmove`: _handle_player_genmove
  - `gameover`: _handle_player_gameover
  - `waiting`: (game matching/scheduling)
  - `ok`: (passive state, error if data received)

---

## 5. KEY DATA STRUCTURES AND MESSAGE FORMATS

### 5.1 Game State

**Game Class** (`/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/gogame/game.py`):
```python
class Game:
    w: str                                          # White player name
    b: str                                          # Black player name
    last_move_start_time: int                       # Timestamp in ms
    white_remaining_time: int                       # Time in ms
    black_remaining_time: int                       # Time in ms
    white_rate: str                                 # Rating string (e.g., "1800?")
    black_rate: str                                 # Rating string
    moves: List[Tuple[str, int, Optional[str]]]     # (move, time_left_ms, analysis_json)
    ctime: datetime.datetime                        # Game creation time
```

### 5.2 Setup Message Format

```
setup <gid> <boardsize> <komi> <level> <playerA(rating)> <playerB(rating)> [<move> <time_ms>] ...
```

Example:
```
setup 1 19 7.5 1200000 gnugo(1800?) leela(1750?) E4 1199000 Q4 1198500
```

### 5.3 Move Message Format

**From client to server:**
- For normal moves: just the move coordinate (e.g., `D4`, `PASS`, `resign`)
- With analysis: `D4 {"visits": 1000, "winrate": 0.65, "pv": "D4 C3 C4"}`

**From server to client:**
- `play <color> <move> <time_remaining_ms>`

Example:
```
play b d4 1198500
```

### 5.4 Game Result Formats

Standard Go game results:
- `B+2.5` - Black wins by 2.5 points
- `W+Resign` - White wins by resignation
- `B+Time` - Black wins by timeout
- `W+Illegal` - White wins by illegal move
- `Draw` - Game drawn

### 5.5 Database Schema

**state.db - gameid table:**
```sql
CREATE TABLE gameid(gid int)
-- Stores current game ID counter
```

**state.db - password table:**
```sql
CREATE TABLE password(
    name TEXT PRIMARY KEY,
    pass TEXT,              -- Password hash or plain
    games INT,              -- Number of games played
    rating FLOAT,           -- Elo rating
    K FLOAT,                -- K-factor
    last_game TIMESTAMP     -- Last game timestamp
)
```

**state.db - games table:**
```sql
CREATE TABLE games(
    gid INT PRIMARY KEY,
    w TEXT,                 -- White player
    wr TEXT,                -- White rating
    b TEXT,                 -- Black player
    br TEXT,                -- Black rating
    dte TIMESTAMP,          -- Date
    wtu INT,                -- White time used (ms)
    btu INT,                -- Black time used (ms)
    res TEXT,               -- Result
    final BOOL              -- Game finalized
)
```

**state.db - anchors table:**
```sql
CREATE TABLE anchors(
    name TEXT PRIMARY KEY,
    rating FLOAT            -- Anchor rating
)
```

**archive.db - games table:**
```sql
CREATE TABLE games(
    gid INT,
    dta TEXT,               -- Serialized game data
    analysis TEXT           -- Analysis data
)
```

### 5.6 SGF Record Format

**Generated by:** `game.py:sgf()` function

Example structure:
```
(;GM[1]FF[4]CA[UTF-8]
RU[POSITIONAL]SZ[19]KM[7.0]TM[1200]
PW[Engine1]PB[Engine2]WR[1800?]BR[1750?]DT[2024-01-15]
PC[CGOS Server]RE[B+2.5]GN[1]
;B[pd];W[cp];B[ed];W[pq]...
)
```

---

## 6. MAIN WORKFLOWS/FLOWS

### 6.1 Client Connection Workflow

```
1. Client Configuration Loading
   - Read YAML config file
   - Validate required fields
   - Load list of engines

2. Engine Selection
   - If multiple engines: random selection with weights
   - If single engine: use it

3. TCP Connection Establishment
   - Create socket to server:port
   - Wrap in text mode (UTF-8)

4. Authentication Flow
   a. Receive "protocol genmove_analyze"
   b. Send "e1 cgosPython 1.0.0 [genmove_analyze]"
   c. Receive "username"
   d. Send username
   e. Receive "password"
   f. Send password
   g. Server validates and logs in

5. Game Scheduling Loop
   - Wait in "waiting" state
   - Receive game setup
   - Or: Game in progress, catch up on moves

6. Game Execution Loop
   a. Receive setup or catch-up moves
   b. Setup GTP engine (boardsize, komi, time settings)
   c. Play catch-up moves
   d. Receive genmove request
   e. Request move from engine
   f. Send move with analysis if available
   g. Receive opponent move via "play"
   h. Repeat until gameover
   i. Receive gameover with result
   j. Save SGF file
   k. Return to waiting state

7. Shutdown
   - Check for kill file
   - Send "quit"
   - Close socket
   - Kill engine subprocess
```

### 6.2 Server Game Scheduling Workflow

**`schedule_games()` function (Lines 1525-1605):**

1. **Check Active Games for Timeout**
   - Iterate through all active games
   - Calculate elapsed time since last move
   - Forfeit games exceeding time limit

2. **Update Game Progress Information**
   - Count active games
   - Estimate time until next round
   - Broadcast info messages to all clients

3. **Check Kill File**
   - If kill_cgos19 exists, initiate shutdown

4. **Schedule New Round** (if AUTO mode and no games in progress)
   - Call `match_games()`
   - Creates new game pairings

**`match_games()` function (Lines 1801+):**

1. Collect all waiting players
2. Apply anchor matching (10% of games vs rating anchors)
3. Pair remaining players for games
4. Call `init_game()` for each pairing

### 6.3 Game Execution Flow

**Move Exchange in `_handle_player_genmove()` (Lines 1017-1149):**

1. **Receive Move from Player**
   - Extract move coordinate
   - Parse optional analysis JSON

2. **Validate Move**
   - Call `gme[gid].make(mv)`
   - Check for illegal moves:
     - Occupied square
     - Ko violation
     - Suicide

3. **Update Game State**
   - Deduct time from remaining time
   - Add move to game.moves list
   - Update last_move_start_time

4. **Send Move to Opponent**
   - Call `nsend(opponent, f"play {color} {move} {time_left}")`

5. **Broadcast to Viewers**
   - Send "update {gid} {move} {time_left}" to observers

6. **Check End Conditions**
   - Two consecutive passes → score game
   - Resignation → gameover
   - Time forfeit → gameover
   - Illegal move → gameover

7. **Game Over Processing**
   - Calculate final score
   - Record in database
   - Update player ratings (Elo)
   - Save SGF file
   - Send gameover to both players

### 6.4 Rating Update Workflow

**`batchRate()` function (implicit):**

1. After each round completes:
   - Calculate expected win probability:
     ```
     E(A vs B) = 1 / (1 + 10^((B-A)/400))
     ```

2. Update ratings:
   ```
   newRating = currentRating + K * (result - expected)
   where result = 1.0 (win), 0.5 (draw), 0.0 (loss)
   ```

3. Adjust K-factor:
   - Provisional (few games): higher K
   - Established (many games): lower K
   - Range: minK to maxK

4. Store updated rating in database

---

## 7. TECHNOLOGIES AND FRAMEWORKS USED

### 7.1 Server-Side

**Python Version:** 3.12.0

**Core Libraries:**
- `asyncio` - Async I/O for concurrent client handling
- `sqlite3` - Game and state database
- `socket` - TCP/IP networking (wrapped by asyncio)

**Third-Party Dependencies** (`requirements.txt`):
- `Jinja2==3.0.3` - HTML template rendering for web pages
- `passlib==1.7.4` - Password hashing (optional)
- `pyyaml==6.0.3` - YAML configuration parsing

**Project-Specific Modules:**
- `gogame.go.GoGame` - Go board implementation
- `gogame.go.Rule, KoRule` - Ko rule handling
- `gogame.game.Game, sgf()` - Game state and SGF generation
- `app.rating.newrating, expectation` - Elo rating calculations
- `util.logutils` - Structured logging
- `util.timeutils` - Time utility functions

**Architecture:**
- Event-driven with asyncio
- Single-threaded (no threads/processes)
- Database: SQLite (good for single-process, concurrent reads)
- Web generation: Offline batch processing (separate webuild process)

### 7.2 Client-Side

**Python Version:** 3.x compatible

**Core Libraries:**
- `socket` - TCP/IP networking (blocking I/O)
- `subprocess` - Engine process management
- `logging` - Structured logging
- `yaml` - Configuration parsing
- `os, sys, time` - Standard library utilities

**Project-Specific Modules:**
- `gtpengine.EngineConnector` - GTP subprocess communication
- `gtpengine.AnalyzeResultParser` - Move analysis parsing
- `sgf.SGFGame, SGFMove` - SGF game record handling
- `config.load_config, validate` - Configuration management

**Communication Protocol:**
- GTP (Go Text Protocol) to engines
- Custom text protocol to CGOS server
- Line-based, UTF-8 encoded

**Architecture:**
- Single-threaded with blocking I/O
- Main loop with reconnect backoff
- Kill file for graceful shutdown
- Engine switching support (multi-engine configuration)

### 7.3 Protocol Standards

**GTP (Go Text Protocol):**
- Standard for Go engine communication
- Used by Gnugo, Leela Zero, AlphaGo, etc.
- Commands: `boardsize`, `komi`, `play`, `genmove`, `clear_board`, etc.
- Response format: ID# result (success/failure)

**SGF (Smart Game Format):**
- Standard for recording Go games
- Compact text format with move sequences
- Metadata: player names, ratings, komi, ko rule, result, date

**Elo Rating System:**
- Standard chess rating system (adapted for Go)
- Accounts for expected win probability
- K-factor varies based on player experience

### 7.4 Configuration Management

**Server Configuration** (YAML):
- `serverName`: Descriptive server name
- `boardsize`: 9, 13, or 19
- `komi`: Komi value (usually 7.0)
- `koRule`: "SIMPLE" or "POSITIONAL"
- `level`: Time per player in seconds
- `timeGift`: Fischer time increment
- `portNumber`: TCP port
- `database_state_file`: SQLite state DB path
- `game_archive_database`: SGF archive DB path
- `htmlDir`: Web page output directory
- `sgfDir`: SGF storage directory
- `defaultRating`: New player starting rating
- `minK, maxK`: K-factor bounds

**Client Configuration** (YAML):
```yaml
Common:
  KillFile: "kill_client"
  LogFile: "logs/cgos.log"

Engines:
  - EngineName: "Engine Name"
    CommandLine: "command-line args"
    ServerHost: "server.example.com"
    ServerPort: 6819
    ServerUser: "username"
    ServerPassword: "password"
    NumberOfGames: 10        # Optional
    SGFDirectory: "sgf/"     # Optional
    EngineLogFile: "logs/"   # Optional
```

---

## 8. CONCURRENCY MODEL

### 8.1 Server Concurrency (asyncio-based)

**Async Tasks Created** (from `doc.txt`):

1. **handle_client(client)** - Per client
   - Main message dispatcher
   - Routes to player/viewer/admin handlers

2. **readTask()** - Per client
   - Continuously reads socket
   - Populates _readQueue

3. **writeTask()** - Per client
   - Continuously writes _writeQueue
   - Drains socket

4. **schedule_games_task()** - Singleton
   - Runs every ~15 seconds
   - Handles timeouts
   - Matches new games
   - Updates web data

5. **accept_connection()** - Singleton
   - Accepts incoming connections
   - Creates Client objects
   - Spawns tasks

**Concurrency Features:**
- No locks/mutexes needed (single event loop)
- Shared state: `act`, `games`, `gme`, `db`
- Non-blocking operations via asyncio queues
- Database has 40-second transaction timeout

### 8.2 Client Concurrency (single-threaded blocking I/O)

**Execution Model:**
- Main thread: mainloop()
- Subprocess: GTP engine process
- No threading or async/await
- Blocking socket I/O
- Poll for kill file between moves

---

## 9. KEY CONFIGURATION FILES

### 9.1 Server Configuration Example
**File:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/configs/generic/cgos19.yaml`

```yaml
serverName: "(CGOS) 19x19 Computer Go Server"
boardsize: 19
komi: 7.0
koRule: "POSITIONAL"
level: 1200                    # 20 minutes
timeGift: 0.25                 # 250ms increment
portNumber: 6819
database_state_file: "<server-data>/19x19/state.db"
game_archive_database: "<server-data>/19x19/archive.db"
defaultRating: 1800.0
minK: 3.0
maxK: 200.0
htmlDir: "<server-html>/19x19"
sgfDir: "SGF"
compressSgf: true
provisionalAge: 0.04           # 1 hour
establishedAge: 31.0           # 31 days
matchMode: "AUTO"              # or "ADMIN"
hashPassword: false
```

### 9.2 Client Configuration Example
**File:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/configs/generic/simple.yaml`

```yaml
Common:
  KillFile: "kill_client"
  LogFile: "logs/cgos.log"

Engines:
  - EngineName: "Gnugo Level 8"
    CommandLine: >
      gnugo --mode gtp --score aftermath --capture-all-dead
      --chinese-rules --level 8
    ServerHost: "yss-aya.com"
    ServerPort: 6819
    ServerUser: "myuser"
    ServerPassword: "mypw"
    NumberOfGames: 5
    SGFDirectory: "sgf/engine1"
    EngineLogFile: "logs/engine1.log"
```

---

## 10. FILE PATHS SUMMARY

### Server Core Files:
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/server.py`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/cgos.py`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/client.py`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/config.py`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/rating.py`

### Server Game Logic:
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/gogame/go.py`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/gogame/game.py`

### Client Core Files:
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/cgosclient.py`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/gtpengine.py`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/sgf.py`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/config.py`

### Configuration Files:
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/configs/generic/cgos19.yaml`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/configs/generic/cgos9.yaml`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/configs/generic/cgos13.yaml`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/configs/generic/simple.yaml`
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/configs/generic/client.yaml`

---

## Summary

CGOS is a specialized online platform for computer Go programs to play against each other with automatic scheduling and Elo rating. 

**Architecture Highlights:**
- **Server:** Python with asyncio for handling multiple concurrent clients
- **Client:** Python with blocking I/O connecting to external Go engines via GTP
- **Protocol:** Custom text-based, line-delimited command protocol
- **Data:** SQLite databases for state and game archive, SGF format for records
- **Rating:** Elo system with dynamic K-factors

The system separates concerns into:
1. Server (game scheduling, player management, rating calculation)
2. Client (engine management, move generation, game participation)
3. Web UI builder (offline generation of standings and archives)
4. Go engine (external process via GTP)

Multiple board sizes (9x9, 13x13, 19x19) are supported via separate server instances, each with independent configuration and databases.
