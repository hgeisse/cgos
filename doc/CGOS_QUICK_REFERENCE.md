# CGOS System - Quick Reference Guide

## System Overview
CGOS (Computer Go Server) is a client-server system for automated Go game scheduling and rating of computer Go engines.

- **Server:** Python asyncio-based TCP server
- **Client:** Python with blocking I/O to external Go engines via GTP
- **Protocol:** Text-based, line-delimited TCP
- **Boards:** Multiple instances (9x9, 13x13, 19x19)
- **Rating:** Elo system with dynamic K-factors

---

## Architecture Components

### Server Side
```
server.py (entry point)
  └─> runServer()
       └─> server_main() [asyncio]
            ├─> accept_connection() [per client connection]
            ├─> handle_client() [per client dispatcher]
            │   ├─> player_respond()
            │   ├─> viewer_respond()
            │   └─> admin_respond()
            └─> schedule_games_task() [singleton, runs every ~15s]
                 ├─> Check timeouts
                 ├─> match_games()
                 └─> update web data
```

### Client Side
```
cgosclient.py
  └─> CGOSClient()
       ├─> connect()
       └─> mainloop()
            └─> _handlerloop()
                 ├─> _handle_protocol()
                 ├─> _handle_username()
                 ├─> _handle_password()
                 ├─> _handle_setup()
                 ├─> _handle_play()
                 ├─> _handle_genmove()
                 └─> _handle_gameover()
            └─> Engine Subprocess (GTP)
```

---

## Message Flow Example

```
1. CLIENT connects to SERVER:6819
2. SERVER: "protocol genmove_analyze"
3. CLIENT: "e1 cgosPython 1.0.0 genmove_analyze"
4. SERVER: "username"
5. CLIENT: "mybot"
6. SERVER: "password"
7. CLIENT: "secretpassword"
8. SERVER: "setup 1 19 7.5 1200000 bot1(1800?) bot2(1750?) [catch-up moves]"
9. CLIENT: "ready"
   [server schedules game, sends genmove when ready]
10. SERVER: "genmove w 1200000"
11. CLIENT: "D4" (or "D4 {\"visits\":1000,\"winrate\":0.65}")
12. SERVER: "play b Q4 1199500"
13. CLIENT: "ready" (if bot needs to wait)
14. SERVER: "genmove b 1199500"
15. CLIENT: "D16"
... [continue until game end] ...
16. SERVER: "gameover 2024-01-15 B+2.5"
17. CLIENT: "ready"
```

---

## Key Files and Their Purpose

| File | Lines | Purpose |
|------|-------|---------|
| `server/cgos/app/cgos.py` | 2026 | Main server logic, message handlers, game scheduling |
| `server/cgos/app/client.py` | 111 | Async I/O wrapper for client connections |
| `server/cgos/gogame/go.py` | - | Go board implementation, move validation |
| `server/cgos/gogame/game.py` | 137 | Game state, SGF generation |
| `client/src/cgosclient.py` | 768 | Main client, message handling, engine control |
| `client/src/gtpengine.py` | 531 | GTP protocol implementation, analyze parsing |
| `client/src/sgf.py` | 184 | SGF game record handling |

---

## Critical Functions

### Server
- `handle_client()` - Main message dispatcher
- `player_respond()` - Routes player messages by state
- `_handle_player_genmove()` - Move validation and game state update
- `schedule_games()` - Periodic task: timeout check, game matching
- `match_games()` - Create new game pairings
- `init_game()` - Initialize a new game

### Client
- `mainloop()` - Reconnect loop
- `_handlerloop()` - Message read loop
- `_handle_setup()` - Game setup
- `_handle_genmove()` - Request move from engine
- `_handle_gameover()` - Game completion
- `requestGenMove()` - Call GTP genmove on engine

---

## State Machine: Server Client Handler

```
PROTOCOL
  ├─ e1 (player) ──> USERNAME
  │                    ├─ valid name ──> PASSWORD
  │                    └─ invalid ──> close
  │
  └─ v1 (viewer) ──> (send matches immediately)

PASSWORD
  ├─ valid pw ──> WAITING (add to act dict)
  │                 ├─ game in progress? ──> OK + GENMOVE
  │                 └─ waiting for match
  ├─ invalid pw ──> close
  └─ new user ──> create account ──> WAITING

WAITING
  └─ [scheduled by match_games] ──> OK + GENMOVE

OK (passive, waiting for genmove to complete)
  └─ [engine responds] ──> GENMOVE

GENMOVE (expecting move response)
  ├─ valid move ──> OK
  │                  ├─ game over? ──> GAMEOVER
  │                  └─ opponent's turn ──> GENMOVE (opponent)
  ├─ illegal move ──> GAMEOVER (forfeit)
  ├─ resignation ──> GAMEOVER
  └─ timeout ──> GAMEOVER (forfeit)

GAMEOVER (expecting "ready" response)
  └─ ready ──> WAITING
```

---

## Database Tables

### state.db
- `gameid` - Current game ID counter
- `password` - Player credentials and ratings
- `games` - Game results and history
- `anchors` - Rating anchors for calibration
- `clients` - Client connection statistics

### archive.db
- `games` - Compressed game records (SGF)

---

## Message Types Summary

### Server → Client
| Command | Params | Notes |
|---------|--------|-------|
| `protocol` | [genmove_analyze] | Query capabilities |
| `username` | - | Request login |
| `password` | - | Request password |
| `setup` | gid bs komi level w b [moves] | Game init |
| `play` | color coord time_ms | Opponent move |
| `genmove` | color time_ms | Request move |
| `gameover` | date result | Game end |
| `info` | text... | Status message |

### Client → Server
| Command | Params | Notes |
|---------|--------|-------|
| `e1` | client_id [genmove_analyze] | Player protocol |
| `v1` | viewer_id | Viewer protocol |
| `ready` | - | Ready for game |
| `quit` | - | Disconnect |
| (move) | [analysis_json] | Move response (raw coord) |
| username | - | Login response |
| password | - | Password response |

---

## Configuration

### Server (YAML)
```yaml
serverName: "CGOS 19x19"
boardsize: 19
komi: 7.0
level: 1200              # seconds per player
timeGift: 0.25           # Fischer increment in seconds
portNumber: 6819
matchMode: "AUTO"        # or "ADMIN"
defaultRating: 1800.0
minK: 3.0
maxK: 200.0
```

### Client (YAML)
```yaml
Common:
  KillFile: "kill_client"
Engines:
  - EngineName: "Engine"
    CommandLine: "gnugo --mode gtp"
    ServerHost: "localhost"
    ServerPort: 6819
    ServerUser: "bot"
    ServerPassword: "pass"
```

---

## Time Management

- **Level:** Total time per player (e.g., 1200 seconds = 20 minutes)
- **TimeGift:** Fischer time increment per move (e.g., 0.25 seconds = 250ms)
- **Setup message:** Time in milliseconds
- **Move response:** Time in milliseconds (remaining)
- **Leeway:** Buffer for network latency (derived from timeGift)

Example:
```
setup ... level=1200000ms
genmove b 1200000ms  (black has 20 minutes)
[black uses 5 seconds, gets 250ms back]
play w move 1195250ms (white receives opponent's remaining time)
```

---

## Rating System

**Elo Formula:**
```
E(A vs B) = 1 / (1 + 10^((B-A)/400))
newRating(A) = currentRating(A) + K * (result - E(A vs B))
```

**K-factor:**
- Starts at maxK (200) for new players
- Decreases to minK (3) as player establishes record
- Adjusts based on provisional/established status

---

## Game Result Formats

- `B+2.5` - Black wins by 2.5 points
- `W+Resign` - White resigns
- `B+Time` - Black wins by timeout
- `W+Illegal` - White wins by illegal move
- `Draw` - Even game (rare)

---

## Error Codes (Go Move Validation)

```
0:  OK
-1: Suicide
-2: Ko violation
-3: Occupied square
-4: Syntax error
```

---

## File Operations

### Kill Files
- Creating `kill_cgos19` stops the server after current games
- Creating `kill_webuild19` stops the web builder
- File is automatically deleted after shutdown

### SGF Files
- Generated per game in `htmlDir/19x19/SGF/[date]/`
- Can be gzip-compressed if `compressSgf: true`
- Includes moves, times, ratings, analysis if available

### Web Data File
- Updated every round: `wdata.txt`
- Contains player standings, recent games, ongoing games
- Used by web builder to generate HTML pages

---

## Key Implementation Details

### Blocking Points
- Server: Database transactions (40s timeout)
- Client: GTP genmove response (blocks until engine responds)
- Both: Network I/O (socket read/write)

### Graceful Shutdown
- **Server:** Kill file check in schedule_games loop
- **Client:** Kill file check in _handlerloop

### Multi-Player Matching
- Random pairing with anchor matching
- Avoids same-player rematches
- Supports asymmetric game assignment

### Connection Recovery
- **Server:** Auto-detect client disconnect on empty read
- **Client:** Reconnect with exponential backoff
- Both: Existing games resume on reconnect

---

## Performance Notes

- Asyncio: 1000s of concurrent games
- SQLite: Single process, 40s transaction timeout
- Network: Line-buffered text protocol (minimal overhead)
- GTP: Subprocess communication via stdin/stdout
- Web: Offline batch generation (not real-time)

---

## Common Issues & Debugging

**Client Won't Connect:**
- Check server running: `ps aux | grep server.py`
- Check port: `netstat -tlnp | grep 6819`
- Verify config: serverHost, serverPort, credentials

**Game Hangs:**
- Check GTP engine: test with `gnugo --mode gtp`
- Check network: can reach server from client
- Check logs: client and server log files

**Move Validation Fails:**
- Verify board size, komi match config
- Check for double-pass situations
- Verify Ko rule setting

---

## Links to Source

- Main analysis: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/CGOS_SYSTEM_ANALYSIS.md`
- Server code: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/`
- Client code: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/`
- Docs: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/doc/doc.txt`
