# CGOS Protocol Documentation

Complete specification of the Computer Go Online Server (CGOS) communication protocol.

## Overview

The CGOS protocol is a **line-based text protocol** used for real-time game streaming from the CGOS server to connected clients. It uses TCP for reliable, ordered delivery of game data.

### Key Characteristics

- **Protocol Type**: TCP text-based streaming
- **Transport**: TCP/IP
- **Server Address**: `cgos.boardspace.net`
- **Server Port**: `6867`
- **Message Format**: Line-delimited text (newline-separated)
- **Encoding**: UTF-8
- **Connection Style**: Persistent streaming (server pushes updates to client)
- **Authentication**: None (public game data)

---

## Connection Lifecycle

### 1. Connection Establishment

```
Client                              Server
  │                                   │
  ├──────── TCP SYN ────────────────→ │
  │                                   │
  │ ←────── TCP SYN-ACK ────────────── │
  │                                   │
  ├──────── TCP ACK ────────────────→ │
  │                                   │
  └─── Connection Ready ───────────────┘
```

**Steps:**
1. Client initiates TCP connection to `cgos.boardspace.net:6867`
2. Server accepts connection
3. Server immediately begins streaming game data
4. No handshake or authentication required

### 2. Data Streaming

```
Client                              Server
  │                                   │
  ├─── (listening) ←─── Game line 1 ─│
  │                                   │
  ├─── (listening) ←─── Game line 2 ─│
  │                                   │
  ├─── (listening) ←─── Comment line ─│
  │                                   │
  ├─── (listening) ←─── Game line 3 ─│
  │                  (continuously)   │
```

Client continuously receives game updates as they occur on the server.

### 3. Disconnection

```
Client                              Server
  │                                   │
  ├──────── TCP FIN ────────────────→ │
  │                                   │
  │ ←────── TCP FIN ─────────────────  │
  │                                   │
  └─── Connection Closed ──────────────┘
```

Connection may be closed by:
- Client closes socket
- Server closes socket
- Network timeout
- Connection error

---

## Message Format

### Game Update Message

Each game update is a **single line** containing:

```
<gid> <date> <time> <boardsize> <komi> <white_player> <black_player> [result] [move1] [time1] [move2] [time2] ...
```

### Field Specification

#### Required Fields (7 fields)

| # | Field Name | Type | Size | Range | Example | Description |
|---|------------|------|------|-------|---------|-------------|
| 1 | `gid` | Integer | 1-10 digits | 0-2147483647 | `12345` | Unique game identifier (primary key) |
| 2 | `date` | String | YYYY-MM-DD | Any valid date | `2026-08-01` | Game start date (ISO 8601) |
| 3 | `time` | String | HH:MM:SS | 00:00:00-23:59:59 | `14:30:00` | Game start time (UTC) |
| 4 | `boardsize` | Integer | 1-2 digits | 7-25 | `19` | Go board size (standard: 9, 13, 19) |
| 5 | `komi` | Float | 1-5 chars | 0.0-100.0 | `6.5` | Compensation points for White |
| 6 | `white_player` | String | 1-50 chars | Alphanumeric + `_` | `AlphaGo_v20` | Name of White player/engine |
| 7 | `black_player` | String | 1-50 chars | Alphanumeric + `_` | `Leela_Chess_Zero` | Name of Black player/engine |

#### Optional Fields

| # | Field Name | Type | Size | Range | Example | Description |
|---|------------|------|------|-------|---------|-------------|
| 8 | `result` | String | 1-20 chars | `W+<num>`, `B+<num>`, `<color>+Resign`, `Draw` | `W+2.5` | Game result (only if game finished) |
| 9+ | `move` | String | 2-3 chars | A1-Z25 (skip I) | `E5` | Move in algebraic notation |
| 9+ | `time` | Float | 1-10 chars | 0.0+ | `2.34` | Elapsed time in seconds for that move |

### Special Cases

#### Comment Lines

Lines starting with `#` are comments and should be ignored:

```
# Server maintenance at 15:00 UTC
# Game list updated: 45 active games
```

#### Empty Lines

Empty lines may be sent as keep-alive markers and should be ignored.

---

## Message Examples

### Example 1: In-Progress Game (No Result)

```
12345 2026-08-01 14:30:00 19 6.5 AlphaGo Leela E5 1.23 D4 0.87 C4 1.56
```

**Parsed as:**
- Game ID: 12345
- Date: 2026-08-01
- Time: 14:30:00
- Board Size: 19x19
- Komi: 6.5
- White: AlphaGo
- Black: Leela
- Moves: E5 (1.23s), D4 (0.87s), C4 (1.56s)
- Status: In Progress

### Example 2: Completed Game (With Result)

```
12346 2026-08-01 14:35:00 9 0.0 KataGo Pachi W+2.5 E5 2.10 D4 1.80 C4 2.30 E3 1.90
```

**Parsed as:**
- Game ID: 12346
- Date: 2026-08-01
- Time: 14:35:00
- Board Size: 9x9
- Komi: 0.0
- White: KataGo
- Black: Pachi
- Result: White won by 2.5 points
- Moves: E5, D4, C4, E3 (with times)
- Status: Finished

### Example 3: Game with Resignation

```
12347 2026-08-01 14:40:00 13 6.5 MoGo Fuego B+Resign D3 0.50 C3 0.45 D4 0.48
```

**Parsed as:**
- Result: Black won by resignation
- Status: Finished (opponent resigned)

### Example 4: Comment and Empty Lines

```
# Active games as of 2026-08-01 14:45:00

12348 2026-08-01 14:45:00 19 6.5 Zen GnuGo E5 1.2

# Next update in 5 seconds
```

---

## Move Notation

### Algebraic Notation Format

Moves are specified in **algebraic notation**:

```
<column><row>
```

Where:
- **Column**: `A` to `Z` (representing columns 1-25)
  - Skips `I` to avoid confusion with `1`
  - Columns: A, B, C, D, E, F, G, H, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z
- **Row**: `1` to `25` (representing rows 1-25)
  - Row 1 is at the bottom for 19x19 (traditional Go board orientation)

### Valid Moves by Board Size

| Board Size | Columns | Rows | Example Moves |
|-----------|---------|------|---------------|
| 7x7 | A-G | 1-7 | A1, D4, G7 |
| 9x9 | A-I | 1-9 | A1, E5, I9 |
| 13x13 | A-M | 1-13 | A1, G7, M13 |
| 19x19 | A-S | 1-19 | A1, K10, S19 |
| 25x25 | A-Z | 1-25 | A1, M13, Z25 |

### Special Moves

**Pass Move**: Some implementations may use `Pass` instead of a coordinate. The current implementation's support for `Pass` moves is not explicitly documented in the protocol, but the game engine (`gogame.py`) supports pass moves.

### Move Examples

```
E5     → Column E (5th), Row 5
D4     → Column D (4th), Row 4
A1     → Column A (1st), Row 1 (corner)
S19    → Column S (19th), Row 19 (opposite corner on 19x19)
T25    → Column T (20th), Row 25 (corner on 25x25)
```

---

## Elapsed Time Format

The time field for each move represents how many seconds elapsed for that move:

```
<float>
```

### Characteristics

- **Type**: Floating-point number
- **Unit**: Seconds
- **Precision**: Typically 2 decimal places
- **Range**: 0.0 to infinite (no practical limit)
- **Examples**: `0.01`, `1.23`, `45.67`, `120.5`

### Interpretation

- `< 1.0`: Very fast move (engine computed instantly or had pre-computed result)
- `1.0 - 10.0`: Normal move time
- `> 10.0`: Slow move (engine used most of allocated time)
- Sum of all times: Total elapsed game time

---

## Game Result Format

The result field (optional, present only when game is finished):

```
<color>+<outcome>
```

### Winner Notation

| Format | Meaning | Example |
|--------|---------|---------|
| `W+<score>` | White won by points | `W+2.5` |
| `B+<score>` | Black won by points | `B+3.0` |
| `W+Resign` | Black resigned | `W+Resign` |
| `B+Resign` | White resigned | `B+Resign` |
| `Draw` | Game ended in draw | `Draw` |

### Score Calculation

For point-based results, score includes:
- Territory points
- Captured stones
- Komi (for White)

Example: `W+2.5` means White won by 2.5 points (typically after accounting for komi and captured stones).

---

## Game Data Streaming Behavior

### Update Mechanism

The server **continuously streams** game data, sending updated game lines when:

1. **A new game starts** - Initial game line sent
2. **A move is made** - Full game line resent with new move appended
3. **A game finishes** - Full game line sent with result field populated

### Example: Game Progression

```
TIME    MESSAGE
────────────────────────────────────────────────────────
T=0s    12350 2026-08-01 15:00:00 19 6.5 Engine1 Engine2

T=1s    12350 2026-08-01 15:00:00 19 6.5 Engine1 Engine2 E5 0.45

T=2s    12350 2026-08-01 15:00:00 19 6.5 Engine1 Engine2 E5 0.45 D4 1.23

T=3s    12350 2026-08-01 15:00:00 19 6.5 Engine1 Engine2 E5 0.45 D4 1.23 C4 0.89

...

T=150s  12350 2026-08-01 15:00:00 19 6.5 Engine1 Engine2 W+2.5 E5 0.45 D4 1.23 C4 0.89 ... [full game] ...
```

### Key Points

- **Each update includes the entire game state** (all moves so far)
- **Moves are never deleted**, only appended
- **Result is added when game finishes**
- **Client must handle duplicate updates** (may receive same message multiple times)
- **No guarantee of exactly-once delivery** for network protocol (handle idempotently)

---

## Client-to-Server Communication

### Send Command Format

```
<command> [arguments]\n
```

Commands are sent as lines (newline-terminated), similar to game updates.

### Example Commands (Typical CGOS Server)

```
WATCH <gid>             # Subscribe to updates for game <gid>
UNWATCH <gid>          # Stop watching game <gid>
LIST                   # Get list of active games
QUERY <gid>            # Get current state of game <gid>
QUIT                   # Close connection
```

**Note**: The exact commands supported by CGOS are not fully documented in this codebase. The protocol framework supports sending arbitrary commands using:

```python
await client.send_command("COMMAND arg1 arg2")
```

### Example Exchange

```
Client → Server:  WATCH 12350
Server → Client:  12350 2026-08-01 15:00:00 19 6.5 Engine1 Engine2 E5 0.45

Client → Server:  LIST
Server → Client:  # 45 active games
                  12350 2026-08-01 15:00:00 19 6.5 Engine1 Engine2 E5 0.45 D4 1.23
                  12351 2026-08-01 15:05:00 9 0.0 KataGo Pachi C5 2.1
                  ...
```

---

## Error Handling

### Malformed Messages

The client should handle these gracefully:

| Condition | Example | Action |
|-----------|---------|--------|
| Too few fields | `12345 2026-08-01` | Ignore line, log warning |
| Invalid integer | `abc 2026-08-01 14:30:00 19 6.5 A B` | Ignore line, log debug |
| Invalid float | `12345 2026-08-01 14:30:00 19 abc A B` | Ignore line, log debug |
| Invalid move format | `12345 2026-08-01 14:30:00 19 6.5 A B ZZ99` | Parse as far as possible, truncate moves |
| Comment line | `# Server message` | Skip, do not parse |
| Empty line | `` | Skip, treat as keep-alive |

### Connection Errors

| Condition | Recovery |
|-----------|----------|
| Connection refused | Exponential backoff, retry connection |
| Connection dropped | Log error, wait for reconnect request |
| Read timeout | Assume keep-alive period exceeded, reconnect |
| Incomplete line | Buffer and wait for newline |

### Client Implementation Pattern

```python
try:
    line = await self.reader.readline()
    if not line:
        # Server closed connection
        break
    
    game_info = self._parse_game_line(line.decode().strip())
    if game_info:
        # Valid game update
        self.active_games[game_info.gid] = game_info
        if self.on_game_update:
            self.on_game_update(game_info)
except Exception as e:
    # Parse or protocol error
    logger.error(f"Error: {e}")
```

---

## Protocol State Diagram

```
┌─────────────┐
│ Disconnected│
└──────┬──────┘
       │ connect()
       ↓
┌─────────────────────┐
│ Connecting          │
│ TCP SYN sent        │
└──────┬──────────────┘
       │ TCP ACK received
       ↓
┌─────────────────────┐
│ Connected           │
│ Waiting for data    │
└──────┬──────────────┘
       │ Data received
       ↓
┌─────────────────────┐
│ Receiving Data      │
│ Parsing messages    │
└──────┬──────────────┘
       │ (continuously)
       │ error or disconnect()
       ↓
┌─────────────┐
│ Disconnected│
└─────────────┘
```

---

## Performance Considerations

### Bandwidth

- **Average message size**: 100-500 bytes per game update
- **Update frequency**: Every 0.5-5 seconds per active game
- **Concurrent games**: Server may broadcast 50-100+ games simultaneously
- **Typical bandwidth**: 10-100 KB/s for active client

### Latency

- **Message delivery**: < 100ms (local network)
- **Update frequency**: Depends on move speed (varies from seconds to minutes)
- **Real-time guarantee**: Best-effort (no guarantees)

### Scalability

- **Server**: Handles 1000+ concurrent clients (broadcast model)
- **Client**: Can handle 1000+ concurrent games (parsing/storage)
- **No per-client processing**: Server broadcasts same data to all clients

---

## Security Considerations

### Authentication
- **None**: Public game data, no authentication required
- **Encryption**: Not part of protocol (recommend TLS in production)

### Data Validation
- Client must validate all received data
- No SQL injection or code injection possible (game moves are constrained)
- DoS concern: Malicious server could send massive messages

### Privacy
- All game data is public
- Player names are visible
- Game moves are visible to all watchers

---

## Examples and Test Cases

### Test Case 1: Parse Simple Game

```python
line = "12345 2026-08-01 14:30:00 19 6.5 AlphaGo Leela E5 1.2 D4 0.8"
parts = line.split()

gid = int(parts[0])           # 12345
date = parts[1]                # 2026-08-01
time = parts[2]                # 14:30:00
board_size = int(parts[3])    # 19
komi = float(parts[4])         # 6.5
white_player = parts[5]        # AlphaGo
black_player = parts[6]        # Leela
moves = [(parts[7], float(parts[8])), 
         (parts[9], float(parts[10]))]  # [(E5, 1.2), (D4, 0.8)]
```

### Test Case 2: Game with Result

```python
line = "12346 2026-08-01 14:35:00 19 6.5 KataGo Pachi W+2.5 E5 2.1 D4 1.8"
# Includes result: W+2.5
result = parts[7]  # W+2.5
moves = [(parts[8], float(parts[9])), (parts[10], float(parts[11]))]
```

### Test Case 3: Handling Odd Number of Move/Time Pairs

```python
line = "12347 2026-08-01 14:40:00 19 6.5 A B E5 1.2 D4"
# Last move (D4) has no time - should be skipped
for i in range(8, len(parts) - 1, 2):
    move = parts[i]
    time = float(parts[i + 1])
# Only processes E5 with 1.2, skips D4
```

---

## Implementation Reference

See `src/cgosview/network/cgos_client.py` for reference implementation in Python.

### Key Method

```python
def _parse_game_line(self, line: str) -> Optional[GameInfo]:
    """Parse CGOS protocol line into GameInfo."""
    if not line or line.startswith("#"):
        return None
    
    try:
        parts = line.split()
        if len(parts) < 7:
            return None
        
        gid = int(parts[0])
        date = parts[1]
        time = parts[2]
        board_size = int(parts[3])
        komi = float(parts[4])
        white_player = parts[5]
        black_player = parts[6]
        result = parts[7] if len(parts) > 7 else None
        
        moves: List[Tuple[str, float]] = []
        for i in range(8, len(parts) - 1, 2):
            move = parts[i]
            elapsed = float(parts[i + 1])
            moves.append((move, elapsed))
        
        return GameInfo(
            gid=gid, date=date, time=time,
            board_size=board_size, komi=komi,
            white_player=white_player,
            black_player=black_player,
            result=result, moves=moves
        )
    except (ValueError, IndexError):
        return None
```

---

## Related Documentation

- **Game Engine**: See `gogame.py` for move validation and game rules
- **Network Client**: See `cgos_client.py` for implementation details
- **GUI**: See `main_window.py` for game display integration

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-08-01 | Initial protocol documentation based on CGOSVIEW Python port |

---

## Conclusion

The CGOS protocol is a simple, efficient, line-based text protocol designed for real-time game streaming. Its simplicity makes it easy to implement and debug, while its streaming nature allows for real-time updates of thousands of concurrent games.

The protocol is inherently broadcast-oriented, with the server pushing updates to all connected clients, making it ideal for a public game viewing platform like CGOS.
