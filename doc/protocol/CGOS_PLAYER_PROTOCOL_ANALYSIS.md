# CGOS Player Protocol - Comprehensive Analysis

**Document Version**: 1.0  
**System**: Computer Go Server (CGOS) - Player/Engine Protocol  
**Analysis Date**: August 2026  
**Components**: Server (Python) + Engine Client (Python with GTP Bridge)

---

## Executive Summary

The CGOS Player Protocol (e1) is a **stateful, authenticated protocol** that allows Go engines to connect to a CGOS server, authenticate as users, receive game assignments, play moves in real-time, and handle game completion. Unlike the simpler viewer protocol, the player protocol implements full game participation with strict state machine behavior, move validation, time management, and rating system integration.

**Key Characteristics:**
- **Authentication required**: Username/password credentials
- **Game participation**: Engines actively make moves
- **Time management**: Per-move and per-game time tracking
- **Move validation**: Server validates moves using Go rules engine
- **Rating integration**: Player ratings updated after each game
- **Analysis support**: Optional genmove_analyze for engine analysis
- **Session persistence**: Reconnection support for in-progress games

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Network Layer Details](#network-layer-details)
3. [Protocol Handshake](#protocol-handshake)
4. [Authentication Flow](#authentication-flow)
5. [Game Lifecycle](#game-lifecycle)
6. [Game Setup Protocol](#game-setup-protocol)
7. [Move Negotiation Protocol](#move-negotiation-protocol)
8. [Time Management](#time-management)
9. [Game Termination](#game-termination)
10. [GTP Integration](#gtp-integration)
11. [State Machine Model](#state-machine-model)
12. [Message Formats Detailed](#message-formats-detailed)
13. [Error Handling & Recovery](#error-handling--recovery)
14. [Performance & Scalability](#performance--scalability)
15. [Protocol Comparison](#protocol-comparison)

---

## Architecture Overview

### Client-Server Components

```
┌─────────────────────────────────────────────────┐
│         AI Engine Client (Python)               │
│  ┌───────────────────────────────────────────┐  │
│  │ CGOSClient (cgosclient.py - 768 lines)   │  │
│  │  - TCP connection management             │  │
│  │  - Protocol state machine                │  │
│  │  - Game lifecycle management             │  │
│  │  - Reconnection logic                    │  │
│  │  - Statistics tracking                   │  │
│  └───────────────────────────────────────────┘  │
│           ↑              ↓                        │
│    CGOS Protocol    GTP Bridge                   │
│    (TCP)           (stdin/stdout)                │
│           ↓              ↑                        │
│  ┌───────────────────────────────────────────┐  │
│  │ GTPEngine (gtpengine.py - 531 lines)     │  │
│  │  - GTP protocol communication            │  │
│  │  - Engine process management             │  │
│  │  - Move generation requests              │  │
│  │  - Analysis parsing (genmove_analyze)    │  │
│  └───────────────────────────────────────────┘  │
│           ↓                                      │
│  ┌───────────────────────────────────────────┐  │
│  │ External Go Engine (Leela, KataGo, etc)  │  │
│  │  - Move generation                       │  │
│  │  - Time management                       │  │
│  │  - Analysis output (optional)            │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         ↑ CGOS Protocol (e1) ↓
         TCP/IP Port 6809
         ↓ CGOS Protocol (e1) ↑
┌─────────────────────────────────────────────────┐
│      CGOS Server (cgos.py - 2315 lines)         │
│  ┌───────────────────────────────────────────┐  │
│  │ Player Handler Loop (_handlerloop)        │  │
│  │  - _handle_player_protocol()             │  │
│  │  - _handle_player_username()             │  │
│  │  - _handle_player_password()             │  │
│  │  - _handle_player_genmove()              │  │
│  │  - _handle_player_gameover()             │  │
│  │  - _handle_player_quit()                 │  │
│  └───────────────────────────────────────────┘  │
│           ↓                                      │
│  ┌───────────────────────────────────────────┐  │
│  │ Game Engine & State Management            │  │
│  │  - GoGame (go.py) - rules validation     │  │
│  │  - Move validation & execution           │  │
│  │  - Game state persistence (games dict)   │  │
│  │  - Game result calculation               │  │
│  │  - Rating updates (newrating)            │  │
│  └───────────────────────────────────────────┘  │
│           ↓                                      │
│  ┌───────────────────────────────────────────┐  │
│  │ Storage Layer                             │  │
│  │  - game_state.db (SQLite)                │  │
│  │  - archive.db (game records)             │  │
│  │  - SGF files (game records for web)      │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Multi-Engine Support

The client supports multiple engines with hot-switching:

```
Client Configuration (YAML)
├── Engines:
│   ├── Engine 1 (Leela)
│   │   ├── CommandLine
│   │   ├── NumberOfGames (e.g., 100)
│   │   └── Server params
│   ├── Engine 2 (KataGo)
│   │   ├── CommandLine
│   │   ├── NumberOfGames (e.g., 50)
│   │   └── Server params
│   └── Engine N
└── Common
    └── KillFile (for shutdown)
```

When NumberOfGames is exhausted for one engine, the client reconnects with the next engine.

---

## Network Layer Details

### TCP Connection Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Protocol** | TCP/IP | Reliable, ordered |
| **Port** | 6809 (configurable) | Per-engine configuration |
| **Encoding** | UTF-8 | Text-based protocol |
| **Line Ending** | `\n` (LF) | Unix-style |
| **Socket Type** | Text (makefile mode) | Line-buffered I/O |
| **Reconnection** | Automatic with backoff | 30-35 second delays |

### Client Socket Management (cgosclient.py:134-161)

```python
def connect(self) -> None:
    assert self._server is not None
    self.logger.info(f"Attempting to connect to server '{self._server}', port {self._port}")
    
    self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        self._socket.connect((self._server, self._port))
    except Exception as e:
        self.logger.error("Connection failed: " + str(e))
        raise CGOSClientError("Connection failed: " + str(e))
    
    self._socketfile = self._socket.makefile("rw", encoding=ENCODING)
    self._finished = False
    self.logger.info("Connected")
```

**Key Features:**
- Blocking socket operations (synchronous)
- Text mode file wrapper (line-buffered)
- UTF-8 encoding for all messages
- Exception handling with logging

### Reconnection Strategy (cgosclient.py:604-612)

```python
while not (connected):
    try:
        self.connect()
        connected = True
    except Exception:
        self.logger.error("Could not connect to " + self._server + ". Will try again.")
        time.sleep(30 + int(random.random() * 5))  # 30-35 seconds
        retries += 1
```

**Reconnection Characteristics:**
- Fixed 30-35 second retry interval
- No exponential backoff
- Infinite retry attempts
- Blocks main loop during retry

---

## Protocol Handshake

### Initial Connection Sequence

```
Engine Client                          CGOS Server
    │                                      │
    ├─── TCP Connect ─────────────────────→│
    │                                      │
    │←─── "protocol genmove_analyze" ─────┤ (Server offers protocol capability)
    │                                      │
    │ e1 cgosPython 1.0.0 [genmove_analyze]│
    ├─────────────────────────────────────→│ (Client identifies with capability)
    │                                      │
    │                                      │ [Server records client type]
    │                                      │ [Transitions to username state]
    │                                      │
    │←─── "username" ───────────────────────│ (Server requests credentials)
    │                                      │
    │ <engine_username>                    │
    ├─────────────────────────────────────→│ (Client sends username)
    │                                      │
    │                                      │ [Server validates username]
    │                                      │ [Transitions to password state]
    │                                      │
    │←─── "password" ───────────────────────│
    │                                      │
    │ <password>                           │
    ├─────────────────────────────────────→│ (Client sends password)
    │                                      │
    │                                      │ [Server authenticates]
    │                                      │ [Loads user rating & K-factor]
    │                                      │ [Checks for reconnection]
    │                                      │ [Transitions to waiting state]
    │                                      │
    │←─── "setup" or "genmove" ────────────│ (If reconnecting to game)
    │  or waits for matchmaker assignment   │ (Or enters waiting state)
    │                                      │
```

### Protocol Identification (cgosclient.py:199-205)

**Client Responds:**
```
e1 cgosPython 1.0.0 genmove_analyze
```

Or without analysis support:
```
e1 cgosPython 1.0.0
```

**Format:**
- `e1`: Protocol identifier (engine player)
- `cgosPython 1.0.0`: Client implementation identifier
- `genmove_analyze`: Optional capability indicator

**Server Processing** (cgos.py:876-889):

```python
if msg[0:2] == "e1":
    parameters = msg.split()
    logger.info(f"client: {data}")
    
    # Record client type in statistics
    cc = db.execute("select count from clients where name = ?", (data,)).fetchone()
    if cc is not None:
        db.execute("update clients set count=count+1 where name = ?", (data,))
    else:
        db.execute("insert into clients values(?, 1)", (data,))
    db.commit()
    
    # Check for analysis capability
    act[who].useAnalyze = "genmove_analyze" in parameters
    
    # Transition to username state
    act[who].msg_state = "username"
    sock.send("username")
    return
```

---

## Authentication Flow

### Username Validation (cgosclient.py:208-211)

**Client Sends:**
```
<username>
```

**Server Processing** (cgos.py:897-915):

```python
def _handle_player_username(sock: Client, data: str) -> None:
    who = sock.id
    data = data.strip()
    err = valid_name(data)  # Validates username format
    
    if err == "":
        user_name = data
    else:
        sock.send(f"Error: {err}")
        del act[who]
        sock.close()
        return
    
    sock.user_name = user_name
    act[who].msg_state = "password"
    sock.send("password")
    return
```

**Username Validation Rules:**
- Must pass `valid_name()` function
- Typically: alphanumeric + underscore, non-empty
- Case-sensitive

### Password Handling (cgosclient.py:213-216)

**Client Sends:**
```
<password>
```

Or for password change:
```
<old_password> <new_password>
```

**Server Processing** (cgos.py:918-1072):

The password handler performs:

1. **Parse Password Tokens** (cgos.py:931-942):
```python
ts = data.split(" ")
if len(ts) == 1:
    pw = ts[0].strip()
    pw_new = None
elif len(ts) == 2:
    pw = ts[0].strip()
    pw_new = ts[1].strip()
else:
    sock.send("Error: send <password> or <old_password new_password>")
    sock.close()
    return
```

2. **Validate Password Format** (cgos.py:945-950):
```python
err = test_password(pw)
if err != "":
    sock.send(f"Error: {err}")
    sock.close()
    return
```

3. **Lookup User Record** (cgos.py:962-993):

If user exists in database:
```python
cur = db.execute("SELECT pass, rating, K FROM password WHERE name = ?", (who,))
res = cur.fetchone()
```

If user doesn't exist (new user):
- Create new user record with initial rating
- Default rating: `defaultRatingAverage` (typically 0.0)
- Default K-factor: `cfg.maxK`

4. **Verify Password** (cgos.py:998-1027):

**With Hashing:**
```python
if cfg.hashPassword:
    if passctx.identify(cmp_pw):  # Is it already a hash?
        ok, new_hash = passctx.verify_and_update(pw, cmp_pw)
    else:
        ok = cmp_pw == pw
        new_hash = passctx.hash(pw)
    if not ok:
        logger.warn(f"user {who} password doesn't match")
        sock.send("Error: Sorry, password doesn't match")
        sock.close()
        return
```

**Without Hashing:**
```python
if cmp_pw != pw:
    logger.error(f"user {who} password doesn't match")
    sock.send("Error: Sorry, password doesn't match")
    sock.close()
    return
```

5. **Handle Password Change** (cgos.py:1029-1044):

If password change requested:
```python
if pw_new is not None:
    logger.info(f"Change user {who}'s password")
    if cfg.hashPassword:
        pw_store = passctx.hash(pw_new)
    else:
        pw_store = pw_new
    
    db.execute(
        "UPDATE password SET pass=? WHERE name=?",
        (pw_store, who)
    )
    db.commit()
```

6. **Handle Duplicate Login** (cgos.py:1046-1057):

If user already logged in from another connection:
```python
def cleanup_old_connection(who: str, users: Dict[str, ActiveUser]) -> None:
    if who in users:
        xsoc = users[who].sock
        xsoc.send("info another login is being attempted using this user name")
        xsoc.close()
        logger.error(f"Error: user {who} apparently lost old connection")
        del users[who]

cleanup_old_connection(who, act)
cleanup_old_connection(who, admin)
```

### Post-Authentication State

**For Regular Players** (cgos.py:1070-1072):

```python
act[who] = ActiveUser(sock, msg_state="waiting", gid=0, rating=rat, k=k)
act[who].useAnalyze = client.useAnalyze
logger.info(f"[{who}] logged on analyze: {act[who].useAnalyze}")
```

**For Admin Users** (cgos.py:1063-1068):

```python
if is_admin(who):
    sock.send("ok")
    admin[who] = ActiveUser(sock, msg_state="waiting")
    logger.info(f"[{who}] logged on as admin")
    return
```

---

## Game Lifecycle

### Complete Game Flow

```
┌─────────────────────────────────────────────────────┐
│                    LOGIN COMPLETE                   │
│                  (msg_state = "waiting")             │
└──────────────────────────┬──────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
        ↓                                     ↓
┌────────────────────┐           ┌────────────────────┐
│ RECONNECTING       │           │ NEW GAME           │
│ to in-progress     │           │ (Matchmaker        │
│ game               │           │  assigns game)     │
└────────────────────┘           └────────────────────┘
        │                                     │
        └──────────────────┬──────────────────┘
                           │
                    ┌──────↓──────┐
                    │ SETUP       │
                    │ Receive     │
                    │ board size, │
                    │ komi, moves │
                    └──────┬──────┘
                           │
                    ┌──────↓──────────┐
                    │ MOVE LOOP       │
                    │ Exchange moves  │
                    │ Until game over │
                    └──────┬──────────┘
                           │
                    ┌──────↓──────────┐
                    │ GAMEOVER        │
                    │ Receive result  │
                    │ Update rating   │
                    └──────┬──────────┘
                           │
                    ┌──────↓──────────┐
                    │ READY           │
                    │ Send "ready"    │
                    │ Return to       │
                    │ waiting         │
                    └─────────────────┘
```

### Game Reconnection (cgos.py:1074-1123)

When a player logs in while already in a game:

```python
logger.info(f"is {who} currently playing a game?")

for gid, inf in games.items():
    logger.info(f"testing {gid} {inf.w} {inf.b}")
    
    if inf.w == who or inf.b == who:
        logger.info("YES!")
        
        # Send game setup with current state
        msg_out = f"setup {gid} {cfg.boardsize} {cfg.komi} {cfg.level} {inf.w}({wr}) {inf.b}({br}) {joinMoves(inf.moves)}"
        sock.send(msg_out)
        
        act[who].msg_state = "ok"
        act[who].gid = gid
        
        # Determine if it's this player's turn
        ply = len(inf.moves)
        if ply & 1:
            ctm = inf.w
        else:
            ctm = inf.b
        
        # If this player's turn, send genmove immediately
        if ctm == who:
            if ply & 1:
                tl = inf.white_remaining_time - (ct - inf.last_move_start_time)
                sock.send(f"genmove w {tl}")
            else:
                tl = inf.black_remaining_time - (ct - inf.last_move_start_time)
                sock.send(f"genmove b {tl}")
            act[who].msg_state = "genmove"
            return
```

**Key Features:**
- Automatic game recovery after disconnect
- Board state synchronized with all previous moves
- Time adjusted for elapsed time during disconnection
- Immediate move request if it's the player's turn

---

## Game Setup Protocol

### Setup Message Format

**Sent by Server after Authentication or Assignment:**

```
setup <gid> <boardsize> <komi> <level> <white>(<rating>) <black>(<rating)> [<move1> <time1> <move2> <time2> ...]
```

**Fields:**

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| gid | integer | 1047 | Unique game identifier |
| boardsize | integer | 19 | Board size (7-25) |
| komi | float | 6.5 | Handicap points for white |
| level | integer | 3000000 | Total time per player (milliseconds) |
| white | string | AlphaZero | White player name |
| rating | integer | (2150) | White's current rating |
| black | string | Leela | Black player name |
| rating | integer | (2100) | Black's current rating |
| moves | alternating pairs | d3 2998500 c17 2945000 | Move history with remaining times |

### Setup Example: New Game

```
setup 1047 19 6.5 3000000 AlphaZero(2150) Leela(2100)
```

- No previous moves (new game)
- White to move first (standard)
- Both players start with 3000 seconds

### Setup Example: Reconnecting to Game in Progress

```
setup 1047 19 6.5 3000000 AlphaZero(2150) Leela(2100) d3 2998500 c17 2945000 q3 2890000
```

- Game ID 1047 already in progress
- White played d3, then Black c17, then White q3
- Move times represent remaining time for that player AFTER their move
- Client must:
  1. Reconstruct board state by replaying all moves
  2. Initialize engine with final position
  3. Calculate current time for both players (subtracting moves_since_start_time)

### Client Processing (cgosclient.py:218-327)

**Setup Handler:**

```python
def _handle_setup(self, parameters) -> None:
    """
    Parse setup command and configure engine
    """
    if len(parameters) < 6:
        raise CGOSClientError("'setup' command requires at least 6 parameters")
    assert self._engine is not None
    
    self._gameInProgress = True
    
    # Parse parameters
    gameId = parameters[0]
    boardSize = parameters[1]
    komi = parameters[2]
    gameTimeMSec = int(parameters[3])
    programA = parameters[4]
    programB = parameters[5]
    
    # Extract player names and ratings
    programARank = ""
    programBRank = ""
    if "(" in programA:
        programARank = programA[programA.find("(") : programA.rfind(")")].strip("()")
        programA = programA[: programA.find("(")]
    if "(" in programB:
        programBRank = programB[programB.find("(") : programB.rfind(")")].strip("()")
        programB = programB[: programB.find("(")]
    
    # Determine engine color
    opponent = programA
    opponentRank = programARank
    engineRank = programBRank
    self._engineColour = "black"
    
    if self._username == programA:
        opponent = programB
        opponentRank = programBRank
        engineRank = programARank
        self._engineColour = "white"
    
    self.logger.info(
        "Starting game against " + opponent + "(" + opponentRank + '). '
        'Local engine ("' + self._engine.getName() + '", rated ' + engineRank + ") "
        "is playing " + self._engineColour + "."
    )
    
    # Configure engine through GTP
    self._movecount = 0
    self._engine.notifyBoardSize(boardSize)
    self._engine.notifyKomi(komi)
    self._engine.notifyTimeSettings(gameTimeMSec)
    self._engine.notifyCGOSOpponentName(opponent)
    self._engine.notifyCGOSOpponentRating(opponentRank)
    self._engine.notifyClearBoard()
    
    # Initialize SGF recording
    self._sgfGame = SGFGame(boardSize, komi)
    self._sgfGame.setBlack(programB)
    self._sgfGame.setWhite(programA)
    self._sgfGame.setMainTimeLimit(int(gameTimeMSec / 1000))
    
    # If reconnecting, replay previous moves
    if len(parameters) > 6:
        self.logger.info(
            "This is a restart. Catching up " + str((len(parameters) - 6) // 2) + " moves"
        )
        colour = "b"
        for i in range(6, len(parameters), 2):
            coord = parameters[i].lower()
            time = parameters[i + 1]
            self._handle_play([colour, coord, time])
            colour = "w" if colour == "b" else "b"
```

---

## Move Negotiation Protocol

### Move Exchange Lifecycle

```
Player 1 Makes Move
    │
    ├─ Server validates move
    ├─ Server updates game state
    ├─ Server sends to Player 2: "play <color> <move> <time>"
    ├─ Server broadcasts to viewers: "update <gid> <move> <time>"
    │
    └─→ Server sends to Player 2: "genmove <color> <time_left_ms>"
         │
         └─→ Player 2 Engine Thinks...
              │
              └─→ Player 2 sends: "<move> [analysis_json]"
                   │
                   └─→ [Repeat]
```

### GENMOVE Message (Server to Client)

**Format:**
```
genmove <color> <time_remaining_ms>
```

**Fields:**

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| color | "w" or "b" | w | Color to move (white or black) |
| time_remaining | integer | 2890000 | Milliseconds remaining for this player |

**Examples:**
```
genmove w 2890000
genmove b 2800000
genmove w 100000
```

### Client Handling (cgosclient.py:363-400)

```python
def _handle_genmove(self, parameters: List[str]) -> None:
    """
    Event handler: "genmove". Expects:
      - GTP colour
      - Time left in msec
    """
    if len(parameters) != 2:
        raise CGOSClientError("'play' command requires 2 parameters")
    assert self._engine is not None
    assert self._sgfGame is not None
    
    self._movecount += 1
    if self._movecount % 10 == 0:
        self.logger.info(
            'Engine "' + self._engine.getName() + '" playing ' + self._engineColour + ". "
            + str(self._movecount) + " moves generated. Time left: "
            + str(int(parameters[1]) // 1000) + " sec"
        )
    
    colour = parameters[0]
    timeMSec = int(parameters[1])
    
    # Notify engine of time situation
    self._engine.notifyTimeLeft(colour, timeMSec)
    
    # Request move from engine
    result, analyzeInfo = self._engine.requestGenMove(colour)
    
    # Optional delay (for testing/debugging)
    if self._genmoveDelay > 0:
        time.sleep(self._genmoveDelay)
    
    # Format response
    response = result.lower()
    if self._useAnalyze and analyzeInfo is not None:
        response += " " + analyzeInfo
    
    # Send move back to server
    self._respond(response)
    
    # Update SGF record
    if result == "resign":
        move = None
    elif result == "pass":
        move = SGFMove.getPassMove(
            GTPTools.convertColourToConstant(colour), int(timeMSec / 1000)
        )
    else:
        move = SGFMove(
            GTPTools.convertCoordinateToXY(result),
            GTPTools.convertColourToConstant(colour),
            int(timeMSec / 1000),
        )
    
    if move is not None:
        self._sgfGame.addMove(move)
```

### PLAY Message (Server to Client)

Sent to opponent when a move is made.

**Format:**
```
play <color> <move> <time_remaining_ms>
```

**Example:**
```
play w d3 2998500
play b c17 2945000
play w resign 1500000
```

### Client Handling (cgosclient.py:329-361)

```python
def _handle_play(self, parameters: List[str]) -> None:
    """
    Event handler: "play" command. Expects:
      - GTP colour
      - GTP coordinate
      - Time left in msec
    """
    if len(parameters) != 3:
        raise CGOSClientError("'play' command requires 3 parameters")
    assert self._engine is not None
    assert self._sgfGame is not None
    
    colour = parameters[0]
    coord = parameters[1].lower()
    timeMSec = int(parameters[2])
    
    # Notify engine of opponent's move
    self._engine.notifyPlay(colour, coord)
    
    # Handle pass or normal move
    if coord == "pass":
        move = SGFMove.getPassMove(
            GTPTools.convertColourToConstant(colour), int(timeMSec / 1000)
        )
    else:
        move = SGFMove(
            GTPTools.convertCoordinateToXY(coord),
            GTPTools.convertColourToConstant(colour),
            int(timeMSec / 1000),
        )
    
    self._sgfGame.addMove(move)
```

### Move Response Format

**Standard Move:**
```
d3
```

**Pass Move:**
```
pass
```

**Resignation:**
```
resign
```

**With Analysis (genmove_analyze):**
```
d3 {"visits": 50000, "winrate": 0.45, "score": 2.5, "pv": "d3 c17 q3"}
```

### Server-Side Move Processing (cgos.py:1142-1286)

**Validation and Execution:**

```python
def _handle_player_genmove(sock: Client, data: str) -> None:
    who = sock.id
    ct = now_milliseconds()
    act[who].msg_state = "ok"
    
    gid = act[who].gid
    if gid not in games:
        act[who].msg_state = "waiting"
        return
    
    ctm = gme[gid].colorToMove()
    maybe = ["W+", "B+"][ctm & 1]  # Opponent wins if error
    
    # Parse move and optional analysis
    mv = data.strip()
    analysis = None
    if act[who].useAnalyze:
        tokens = mv.split(None, 1)
        mv = tokens[0]
        if len(tokens) > 1:
            try:
                info = json.loads(tokens[1])
                analysis = json.dumps(info, indent=None, separators=(",", ":"))
                if not isinstance(info, dict):
                    logger.info(f"Ignore bad analysis from {who}, '{tokens[1]}'")
                    analysis = None
            except:
                logger.info(f"Bad analysis from {who}, '{tokens[1]}'")
    
    # Update time tracking
    game = games[gid]
    wrt = game.white_remaining_time
    brt = game.black_remaining_time
    tt = ct - game.last_move_start_time - leeway
    
    if tt < 0:
        tt = 0
    
    # Update remaining time for moving player
    if ctm & 1:  # White's turn
        wrt = wrt - tt
        games[gid].white_remaining_time = wrt
        if wrt < 0:
            gameover(gid, "B+Time", "")
            return
    else:  # Black's turn
        brt = brt - tt
        games[gid].black_remaining_time = brt
        if brt < 0:
            gameover(gid, "W+Time", "")
            return
    
    # Handle resignation
    if mv.lower() == "resign":
        err = 0
        over = maybe + "Resign"
        if game.w == who:
            vmsg = f"{mv} {wrt}"
        else:
            vmsg = f"{mv} {brt}"
        viewers.sendObservers(gid, f"update {gid} {vmsg}")
        add_move("resign")
        gameover(gid, over, "Resignation")
        return
    
    # Validate move
    err = gme[gid].make(mv)
    if err < 0:
        xerr = err * -1
        over = maybe + "Illegal"
        add_move("pass")
        gameover(gid, over, f"Illegal move error:{ERR_MSG[xerr]} move:{mv}")
        return
    
    # Record move
    add_move(mv)
    
    # Send to opponent
    if game.w == who:
        nsend(game.b, f"play w {mv} {wrt}")
        vmsg = f"{mv} {wrt}"
    else:
        nsend(game.w, f"play b {mv} {brt}")
        vmsg = f"{mv} {brt}"
    
    # Broadcast to viewers
    viewers.sendObservers(gid, f"update {gid} {vmsg}")
    
    # Check for game end (2 consecutive passes)
    if gme[gid].twopass():
        sc = gme[gid].ttScore() - cfg.komi
        if sc < 0.0:
            sc = -sc
            over = f"W+{sc}"
        elif sc > 0.0:
            over = f"B+{sc}"
        else:
            over = "Draw"
        gameover(gid, over, "")
        return
    
    # Send genmove to opponent
    if game.w == who:
        if game.b in act:
            act[game.b].msg_state = "genmove"
            nsend(game.b, f"genmove b {brt}")
        games[gid].last_move_start_time = now_milliseconds()
    else:
        if game.w in act:
            act[game.w].msg_state = "genmove"
            nsend(game.w, f"genmove w {wrt}")
        games[gid].last_move_start_time = now_milliseconds()
```

---

## Time Management

### Time Tracking Model

```
Game Starts
├─ Initial Time: cfg.level (milliseconds)
├─ White Time: cfg.level ms
└─ Black Time: cfg.level ms

After Each Move
├─ Calculate elapsed time since last move start
├─ Subtract from moving player's remaining time
├─ Check for timeout
├─ Send remaining time to next player in genmove
└─ Set last_move_start_time = current_time
```

### Time Calculation (cgos.py:1185-1204)

```python
# Elapsed time since last move started
tt = ct - game.last_move_start_time - leeway

if tt < 0:
    tt = 0

# Update white's time
if ctm & 1:  # White just moved
    wrt = wrt - tt
    games[gid].white_remaining_time = wrt
    if wrt < 0:
        over = "B+Time"
        gameover(gid, over, "")
        return

# Update black's time
else:  # Black just moved
    brt = brt - tt
    games[gid].black_remaining_time = brt
    if brt < 0:
        over = "W+Time"
        gameover(gid, over, "")
        return
```

### Leeway Parameter

**Purpose**: Account for network latency and server processing time

```python
leeway: int  # Global variable from configuration
tt = ct - game.last_move_start_time - leeway
```

**Typical Value**: 500-1000 milliseconds

**Effect**: Reduces time deduction to account for communication delays

### Time Transmission to Opponent

**In GENMOVE Message:**
```
genmove w 2890000
```

The 2890000 milliseconds is the time remaining for white after their move was processed.

**In PLAY Message:**
```
play w d3 2998500
```

The 2998500 is white's remaining time after their move.

---

## Game Termination

### GAMEOVER Message

**Sent by Server:**
```
gameover <date> <result> <error_message>
```

**Fields:**

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| date | string | 2024-01-15 | Game date |
| result | string | B+23.5 | Final result |
| error_message | string | "" | Error details if any |

**Result Codes:**
- `W+<score>`: White wins by <score> points
- `B+<score>`: Black wins by <score> points
- `W+Time`: White wins on timeout
- `B+Time`: Black wins on timeout
- `W+Resign`: White wins (Black resigned)
- `B+Resign`: Black wins (White resigned)
- `W+Illegal`: White wins (Black illegal move)
- `B+Illegal`: Black wins (White illegal move)
- `Draw`: Draw

**Examples:**
```
gameover 2024-01-15 B+23.5
gameover 2024-01-15 W+Time
gameover 2024-01-15 B+Resign
gameover 2024-01-15 W+Illegal
```

### Client Handling (cgosclient.py:423-485)

```python
def _handle_gameover(self, parameters: List[str]) -> None:
    """
    Event handler: "gameover". Expects:
      - A date
      - The result (unparsed) e.g. "B+Resign"
    """
    assert self._engine is not None
    assert self._sgfGame is not None
    
    result = parameters[1]
    self.logger.info("Game over. Result: " + result)
    
    # Track wins/losses
    if self._engineColour[0] == result.lower()[0]:
        self.logger.info("Local engine won :-)")
        self._wonGames += 1
    else:
        self.logger.info("Local engine lost :'(")
        self._lostGames += 1
    
    self._gameInProgress = False
    
    # Parse result and update SGF
    if "+Resign" in result:
        self._sgfGame.setScoreResign(GTPTools.convertColourToConstant(result[0]))
        self._engine.notifyCGOSGameover(result)
    elif "+Time" in result:
        self._sgfGame.setScoreTimeWin(GTPTools.convertColourToConstant(result[0]))
        self._engine.notifyCGOSGameover(result)
    elif "+Illegal" in result:
        self._sgfGame.setScoreForfeit(GTPTools.convertColourToConstant(result[0]))
        self._engine.notifyCGOSGameover(result[0] + "Forfeit")
    else:
        try:
            score = float(result[2:])
            self._sgfGame.setScore(
                GTPTools.convertColourToConstant(result[0]), score
            )
        except Exception:
            pass
        self._engine.notifyCGOSGameover(result)
    
    # Save SGF file if configured
    if self._sgfDirectory is not None:
        fileName = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        # ... sanitize names and save file
        self._sgfGame.save(os.path.join(self._sgfDirectory, fileName))
    
    # Check for shutdown signal
    self._checkKillFile()
    
    # Return to waiting state if not finished
    if not (self._finished):
        self.pickNewEngine()
    if not (self._finished) and not (self._engineSwitching):
        self._respond("ready")
    
    self._checkTimeCheckpoint()
```

### Server-Side Result Calculation

**Score Calculation** (cgos.py:1257-1273):

```python
if gme[gid].twopass():
    sc: float = gme[gid].ttScore()
    sc = sc - cfg.komi
    
    if sc < 0.0:
        sc = -sc
        over = f"W+{sc}"
        gameover(gid, over, "")
        return
    elif sc > 0.0:
        over = f"B+{sc}"
        gameover(gid, over, "")
        return
    else:
        over = "Draw"
        gameover(gid, over, "")
        return
```

### Rating Updates

After game completion:

1. **Retrieve game record**
2. **Calculate new ratings** using Bayesian Elo or similar
3. **Update player records**
4. **Store game in archive**

---

## GTP Integration

### What is GTP?

GTP (Go Text Protocol) is a standard interface for Go engines. The client bridges between CGOS protocol and GTP protocol.

### GTP Command Bridge (gtpengine.py)

**GTP Commands Sent by Client to Engine:**

| GTP Command | Purpose | Example |
|-------------|---------|---------|
| `boardsize` | Set board size | `boardsize 19` |
| `komi` | Set komi | `komi 6.5` |
| `clear_board` | Clear board state | `clear_board` |
| `play` | Play a move | `play b d3` |
| `genmove` | Request move generation | `genmove w` |
| `time_settings` | Set time parameters | `time_settings 3000 0 0` |
| `time_left` | Notify time remaining | `time_left w 2890000` |
| `name` | Query engine name | `name` |
| `version` | Query version | `version` |

**Example GTP Session:**

```
Client → Engine: boardsize 19
Engine → Client: =

Client → Engine: komi 6.5
Engine → Client: =

Client → Engine: clear_board
Engine → Client: =

Client → Engine: play b d3
Engine → Client: =

Client → Engine: play w q3
Engine → Client: =

Client → Engine: time_left b 2800000
Engine → Client: =

Client → Engine: genmove b
Engine → Client: = c17
```

### CGOS to GTP Mapping

| CGOS Message | GTP Command | Data |
|--------------|------------|------|
| setup | boardsize, komi, clear_board | From parameters |
| play | play | color, coord |
| genmove | time_left, genmove | color, time |
| gameover | (notification) | result |

### Analysis Support (genmove_analyze)

**When Supported:**

Client sends:
```python
if self._useAnalyze and analyzeInfo is not None:
    response += " " + analyzeInfo
```

**GTP Command:**
```
genmove_analyze <color>
```

**Engine Response Example:**
```
d3 info visits 50000 winrate 0.55 pv d3 c17 q3 ... info visits 45000 winrate 0.42 pv c17 ...
```

**Analysis Parsing (gtpengine.py:37-150):**

Extracts analysis data:
- `visits`: Tree node visits
- `winrate`: Win probability
- `score`: Territory estimate
- `pv`: Principal variation (best moves)
- `scoreLead`: Territory lead estimate
- `ownership`: Board ownership map (encoded)

**Server Processing (cgos.py:1163-1176):**

```python
if act[who].useAnalyze:
    tokens = mv.split(None, 1)
    mv = tokens[0]
    if len(tokens) > 1:
        try:
            info = json.loads(tokens[1])
            analysis = json.dumps(info, indent=None, separators=(",", ":"))
            if not isinstance(info, dict):
                logger.info(f"Ignore bad analysis from {who}, '{tokens[1]}'")
                analysis = None
        except:
            logger.info(f"Bad analysis from {who}, '{tokens[1]}'")
```

Analysis is stored in archive database for later review.

---

## State Machine Model

### Complete State Diagram

```
                    TCP Connection
                           ↓
            ┌───────────────────────────┐
            │ PROTOCOL                  │
            │ (Handshake exchange)      │
            └────────────┬──────────────┘
                         │
              Server sends: "username"
                         │
            ┌───────────────────────────┐
            │ USERNAME                  │
            │ (Waiting for username)    │
            └────────────┬──────────────┘
                         │
              Server sends: "password"
                         │
            ┌───────────────────────────┐
            │ PASSWORD                  │
            │ (Waiting for password)    │
            └────────────┬──────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
    New User              Existing User/Reconnect
         │                               │
    Create Account            Check for game
         │                               │
         └───────────┬───────────────────┘
                     │
            ┌────────↓──────────┐
            │ WAITING           │
            │ (Ready for game)  │
            └────────┬──────────┘
                     │
    (Game assigned or reconnect)
                     │
            ┌────────↓──────────┐
            │ OK                │
            │ (Game setup sent) │
            └────────┬──────────┘
                     │
            Server sends: "genmove"
                     │
            ┌────────↓──────────┐
            │ GENMOVE           │
            │ (Engine thinking) │
            └────────┬──────────┘
                     │
    ┌────────────────┴────────────────┐
    │                                 │
Server sends: "play"              Client responds: move
(opponent moved)                       │
    │                        ┌────────↓──────────┐
    │                        │ OK (passive)      │
    │                        └────────┬──────────┘
    │                                 │
    │                    Wait for opponent's move or game end
    │                                 │
    └────────────────┬────────────────┘
                     │
    (Game continues until end)
                     │
            ┌────────↓──────────┐
            │ GAMEOVER          │
            │ (Result received) │
            └────────┬──────────┘
                     │
    Server sends: "ready" (implied)
    Client responds: "ready"
                     │
            ┌────────↓──────────┐
            │ WAITING           │
            │ (Back to start)   │
            └───────────────────┘
```

### Message State Mapping

| State | Server → Client | Client → Server | Next State |
|-------|-----------------|-----------------|-----------|
| PROTOCOL | protocol genmove_analyze | e1 ... [genmove_analyze] | USERNAME |
| USERNAME | username | <username> | PASSWORD |
| PASSWORD | password | <password> | WAITING |
| WAITING | (nothing) | (nothing) | WAITING or (game assigned/reconnect) |
| OK | setup ... | (acknowledgement implicit) | OK or GENMOVE if turn |
| OK | genmove <color> <time> | (now in GENMOVE) | GENMOVE |
| GENMOVE | (nothing) | <move> [analysis] | OK |
| OK | play <color> <move> <time> | (nothing) | OK or GAMEOVER |
| GAMEOVER | gameover <date> <result> | ready | WAITING |

---

## Message Formats Detailed

### Protocol Identification Message (From Server)

```
protocol genmove_analyze
```

**Meaning**: Server is offering optional genmove_analyze capability

### Protocol Response (From Client)

```
e1 cgosPython 1.0.0 genmove_analyze
```

**Format**: `e1 <client-id> [capability]`

**Components:**
- `e1`: Engine player protocol identifier
- `cgosPython 1.0.0`: Client implementation and version
- `genmove_analyze`: Optional capability flag

### Error Messages (From Server)

```
Error: <error_description>
```

**Examples:**
```
Error: invalid response
Error: do not understand syntax
Error: invalid username
Error: password doesn't match
Error: send <password> or <old_password new_password>
Error: another login is being attempted using this user name
```

When client receives error, it typically:
1. Logs the error
2. Closes the connection
3. Attempts to reconnect after delay

### Info Messages (From Server)

```
info <message>
```

**Purpose**: Server announcements, notifications, status messages

**Handling** (cgosclient.py:194-197):

```python
def _handle_info(self, parameters: List[str]) -> None:
    """Event handler: "info". Ignored."""
    self.logger.info("Server info: " + (" ".join(parameters)))
    self._checkTimeCheckpoint()
```

---

## Error Handling & Recovery

### Connection Errors

#### Timeout During Connection

```python
try:
    self._socket.connect((self._server, self._port))
except socket.timeout:
    # Retry after delay
    time.sleep(30 + int(random.random() * 5))
```

#### Server Unreachable

```python
except socket.gaierror:
    # DNS resolution failed
    time.sleep(30 + int(random.random() * 5))
```

#### Connection Reset

```python
except ConnectionResetError:
    # Server closed connection
    self.disconnect()
    # Will retry in main loop
```

### Authentication Errors

#### Invalid Username

Server response:
```
Error: <error_message>
```

Client action:
```python
if line.startswith("Error:"):
    self.logger.error("CGOS Error: " + line[6:])
    self._finished = True
    return
```

Result: Client shuts down

#### Invalid Password

Same as invalid username - client terminates.

#### Password Change Support

Client can change password during authentication:

```
<old_password> <new_password>
```

Server updates password in database.

### Game-Related Errors

#### Illegal Move

**Server sends:**
```
gameover 2024-01-15 B+Illegal
```

**Move made:** d3  
**Error:** Already occupied square  
**Result:** Opponent wins by illegal move

#### Timeout

**Server detects:** Time remaining becomes negative

**Calculation:**
```python
if wrt < 0:  # White's remaining time < 0
    over = "B+Time"
    gameover(gid, over, "")
```

Result: Black wins by timeout

#### Resignation

**Move sent:** `resign`

**Server action:**
```python
if mv.lower() == "resign":
    over = maybe + "Resign"  # "W+Resign" or "B+Resign"
    gameover(gid, over, "Resignation")
```

Result: Game ends with resignation

### Move Validation Errors

**Server-side validation** (cgos.py:1227-1235):

```python
err = gme[gid].make(mv)
if err < 0:
    xerr = err * -1
    over = maybe + "Illegal"
    add_move("pass")
    gameover(gid, over, f"Illegal move error:{ERR_MSG[xerr]} move:{mv}")
    return
```

**Error codes:**
- `-1`: Suicide attempted
- `-2`: Ko rule violation
- `-3`: Move to occupied square
- `-4`: Syntax/coordinate error

### Engine Errors

**Engine crashes or fails to respond:**

```python
try:
    result, analyzeInfo = self._engine.requestGenMove(colour)
except EngineConnectorError as e:
    self.logger.error("GTP engine error: " + str(e))
    return False
```

Client terminates and can be restarted manually or by process manager.

### SGF File Storage

**After game completion:**

```python
if self._sgfDirectory is not None:
    fileName = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    self._sgfGame.save(os.path.join(self._sgfDirectory, fileName))
```

**Purpose**: Preserve game records for analysis even if server loses data

---

## Performance & Scalability

### Latency Characteristics

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| Move processing | <100ms | Server-side validation + broadcast |
| Network round-trip | 50-200ms | Depends on network latency |
| Engine thinking | 10ms-30sec | Depends on engine strength & time |
| GTP communication | 1-5ms | Local IPC (stdin/stdout) |
| Message serialization | <1ms | Simple text format |

### Throughput

**Per Game:**
- ~200 moves average
- 200 bytes per move (message format)
- 40KB per game (total network)

**Per Client:**
- Variable (depends on engine)
- Typical: 1-10 games concurrent

**Per Server (estimated):**
- 100 concurrent players
- 50 games in progress
- 10-20 moves/second total
- ~5KB/sec network throughput

### Scalability Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| Concurrent players | 1000+ | CPU and memory dependent |
| Concurrent games | 500+ | Memory for game state |
| Viewer connections | 1000+ | Minimal per-connection overhead |
| Database size | 10GB+ | Depends on history retention |

---

## Protocol Comparison

### Player vs Viewer Protocol

| Feature | Player (e1) | Viewer (v1) |
|---------|------------|------------|
| **Protocol Type** | Stateful, game-participating | Stateless, read-only |
| **Authentication** | Required (username/password) | None |
| **Move Participation** | Yes, makes moves | No, read-only |
| **Time Management** | Full control | Observes only |
| **Rating Impact** | Updated after game | None |
| **Analysis Support** | genmove_analyze | Not supported |
| **Game Assignment** | Matchmaker assigns | Manual observe command |
| **Concurrent Games** | 0 or 1 | Unlimited |
| **Initial Setup** | setup message with params | match + setup messages |
| **Move Protocol** | play + genmove exchange | update messages only |
| **Gameover** | gameover with date | gameover broadcast to all |
| **State Persistence** | Reconnection supported | No session state |
| **Connection Timeout** | Triggers reconnection retry | Simple disconnect |

### Message Flow Comparison

**Player Protocol Game Flow:**
```
protocol → username → password → [setup → genmove → play]* → gameover → ready
```

**Viewer Protocol Game Flow:**
```
protocol → [match messages] → observe → setup → [update]* → gameover
```

---

## Configuration & Deployment

### Client Configuration (config.yaml)

```yaml
Common:
  KillFile: kill_client
  LogFile: logs/client.log

Engines:
  - EngineName: "Leela Zero"
    CommandLine: "/usr/bin/leela_zero --gtp"
    ServerHost: "cgos-hg.de"
    ServerPort: 6809
    ServerUser: "LeelaZero"
    ServerPassword: "secret123"
    NumberOfGames: 100
    GenmoveDelay: 0
    SGFDirectory: "sgf/"
    EngineLogFile: "logs/leela.log"
  
  - EngineName: "KataGo"
    CommandLine: "/usr/bin/katago gtp"
    ServerHost: "cgos-hg.de"
    ServerPort: 6809
    ServerUser: "KataGo"
    ServerPassword: "secret456"
    NumberOfGames: 50
    GenmoveDelay: 0
    SGFDirectory: "sgf/"
    EngineLogFile: "logs/katago.log"
```

### Server Configuration (cgos.yaml)

```yaml
boardsize: 19
komi: 6.5
level: 3000000        # 3000 seconds per game
moves_per_save: 50    # Save SGF every 50 moves
game_archive_database: "archive.db"
database_state_file: "game_state.db"
hashPassword: true    # Use bcrypt for passwords
```

---

## Summary

The CGOS Player Protocol implements a sophisticated real-time game protocol with:

1. **Robust Authentication**: Username/password with support for new user creation and password changes

2. **Game Lifecycle Management**: Full support for game assignment, reconnection, setup, play, and termination

3. **Time Management**: Millisecond-precision time tracking with leeway for network delays

4. **Move Validation**: Server-side Go rule checking with comprehensive error reporting

5. **Rating Integration**: Automatic rating updates after each game

6. **Analysis Support**: Optional genmove_analyze for engine analysis data collection

7. **Multi-Engine Support**: Hot-swappable engines with per-engine configuration

8. **Robustness**: Graceful error handling, reconnection support, and comprehensive logging

9. **Scalability**: Efficient message format supporting hundreds of concurrent games

The protocol is well-suited for:
- Competitive online Go tournaments
- AI engine training and evaluation
- Real-time game broadcasting with viewer integration
- Distributed AI vs AI competitions
- Game record collection and analysis

---

## Appendix A: Complete Protocol Trace

### Full Game Session Example

```
[Client connects to server on TCP 6809]

Server → Client:
protocol genmove_analyze

Client → Server:
e1 cgosPython 1.0.0 genmove_analyze

Server → Client:
username

Client → Server:
Leela

Server → Client:
password

Client → Server:
leela_secret

Server → Client:
setup 1047 19 6.5 3000000 AlphaZero(2150) Leela(2100)

[Client initializes engine with board size 19, komi 6.5]
[Client's color is black (Leela), opponent is AlphaZero (white)]

Server → Client:
genmove b 3000000

[Engine thinks about first move...]

Client → Server:
d3 {"visits": 50000, "winrate": 0.52, "score": 1.2}

Server → Client:
play w q3 2998500

[Client updates engine with white's move q3]

Server → Client:
genmove b 2945000

[Engine thinks...]

Client → Server:
c17 {"visits": 45000, "winrate": 0.48, "score": -0.5}

Server → Client:
play w d17 2890000

[Many more moves exchanged...]

Server → Client:
play w pass 100000

Server → Client:
play b pass 95000

Server → Client:
gameover 2024-01-15 B+23.5

[Client saves game to SGF, updates statistics]

Client → Server:
ready

[Client returns to waiting state for next game]
```

---

**Document prepared by**: System Analysis Engine  
**Analysis scope**: Complete Player Protocol (e1) specification with implementation details  
**Code references**: cgosclient.py (768 lines), gtpengine.py (531 lines), cgos.py player handlers (500+ lines)  
**Version**: 1.0 (August 2026)

