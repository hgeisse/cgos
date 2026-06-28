# CGOS Database Schema - Complete Reference Guide

## Table of Contents
1. [Overview](#overview)
2. [Database Files](#database-files)
3. [State Database (state.db)](#state-database-statedb)
4. [Archive Database (archive.db)](#archive-database-archivedb)
5. [Web Data File (wdata.txt)](#web-data-file-wdatatxt)
6. [Data Relationships](#data-relationships)
7. [Query Examples](#query-examples)
8. [Indexing Strategy](#indexing-strategy)
9. [Data Retention](#data-retention)
10. [Source Code Reference](#source-code-reference)

---

## Overview

The CGOS system uses three mechanisms for persistent data storage:

| Storage | Type | Purpose | Scope |
|---|---|---|---|
| **state.db** | SQLite3 database | Active game state, player ratings, running counters | Current session |
| **archive.db** | SQLite3 database | Compressed game records for long-term archival | Historical |
| **wdata.txt** | Text file | Real-time game updates for web display | Current round + recent history |

### Data Flow

```
Game Result
    ↓
state.db (gameid, games tables marked as final="n")
    ↓ [batchRate() called every ~15 seconds]
    ↓
password table updated (rating, K, games, last_game)
games table updated (final="y")
    ↓
seeRecord() creates text representation
    ↓
archive.db (games table, compressed)
    ↓
write_web_data_file() creates wdata.txt
    ↓
Web builder reads wdata.txt for HTML generation
```

---

## Database Files

### Configuration

Database file paths are specified in YAML configuration:

**File**: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/configs/generic/cgos19.yaml`

```yaml
# Active game state and ratings
database_state_file: "<server-data>/19x19/state.db"

# Compressed game archive
game_archive_database: "<server-data>/19x19/archive.db"

# Web data for HTML generation
web_data_file: "<server-data>/19x19/wdata.txt"
```

### File Initialization

Both databases are created on first run (cgos.py:84-113):

```python
def initDatabase() -> None:
    # Create archive database if needed
    if cfg.game_archive_database is not None and not os.path.exists(...):
        conn = sqlite3.connect(cfg.game_archive_database)
        conn.execute("create table games(gid int, dta, analysis)")
        conn.execute("create index white on games(gid)")
        conn.commit()
        conn.close()
    
    # Create state database if needed
    if not os.path.exists(cfg.database_state_file):
        conn = sqlite3.connect(cfg.database_state_file)
        # ... create tables ...
        conn.commit()
        conn.close()
```

### Database Connection

Connection with extended timeout for long transactions (cgos.py:116-145):

```python
def openDatabase() -> None:
    global db, dbrec
    
    # 40-second timeout for transactions
    db = sqlite3.connect(cfg.database_state_file, timeout=40000)
    
    if cfg.game_archive_database is not None:
        dbrec = sqlite3.connect(cfg.game_archive_database, timeout=40000)
```

The extended timeout (40000 milliseconds = 40 seconds) prevents timeouts during complex operations like `batchRate()` which processes many games simultaneously.

---

## State Database (state.db)

The state database contains the current game state, player information, and running counters.

### Table: gameid

**Purpose**: Store the next available game ID

**Creation** (cgos.py:99):
```sql
CREATE TABLE gameid(gid int)
```

**Schema**:

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `gid` | INTEGER | Not Null | Current game ID counter |

**Usage**:
```python
# Get next game ID
gid = db.execute("SELECT gid FROM gameid WHERE ROWID=1").fetchone()[0]

# Increment for next game
db.execute("UPDATE gameid set gid=gid+1 WHERE ROWID=1")
```

**Data**:
- Single row containing an integer
- Incremented by 1 for each new game
- Example: `1`, `2`, `3`, ... `99999`

**Lifecycle**:
- Initialized to 1 on database creation
- Never deleted or modified except increment
- Persists across server restarts
- **Note**: Game IDs are sequential and never reused

---

### Table: password

**Purpose**: Store player credentials, ratings, and game statistics

**Creation** (cgos.py:100-102):
```sql
CREATE TABLE password(
    name TEXT PRIMARY KEY,
    pass TEXT,
    games INT,
    rating FLOAT,
    K FLOAT,
    last_game TIMESTAMP,
    PRIMARY KEY(name)
)
```

**Schema**:

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `name` | TEXT | PRIMARY KEY | Username (3-18 chars, alphanumeric/dot/hyphen) |
| `pass` | TEXT | Not Null | Password (plain or hashed, depending on `hashPassword` config) |
| `games` | INTEGER | Not Null | Total games played by this player |
| `rating` | FLOAT | Not Null | Current Elo rating (e.g., 1850.5) |
| `K` | FLOAT | Not Null | Current K-factor (decay parameter) |
| `last_game` | TIMESTAMP | Not Null | Timestamp of most recent game |

**Typical Data**:
```
name: "GnuGo"
pass: "secret123" or "$2b$12$..." (if hashed)
games: 547
rating: 1850.75
K: 5.0
last_game: "2024-06-20 14:30:25"
```

**Column Details**:

**name**:
- Unique identifier for player
- Case-sensitive
- 3-18 characters
- Must start with alphabetic character
- Alphanumeric, periods, hyphens only
- Examples: "GnuGo", "Leela-Zero", "AlphaGo.v1"

**pass**:
- Plain text or bcrypt hash depending on `cfg.hashPassword`
- Plain text: stored as-is (max 16 characters)
- Hashed: bcrypt format starting with `$2b$`
- Required for authentication

**games**:
- Counter incremented each time player plays a game
- Used for determining provisional vs established status
- Also determines K-factor reduction

**rating**:
- Floating-point Elo rating
- Updated by `batchRate()` after each game
- Typical range: 500-2500
- Formula: `newRating = currentRating + K * (result - expected)`
- Anchored players always reset to anchor value

**K**:
- K-factor (rating change per game)
- New players: maxK (typically 200)
- Established players: minK (typically 3)
- Reduced after each game: `newK = K * (1.0 - reduction * opponentStrength)`
- Lower K = more stable rating, less volatile

**last_game**:
- Timestamp in format "YYYY-MM-DD HH:MM:SS"
- Updated whenever player finishes a game
- Used to expire inactive players from web display
- Example: "2000-01-01 00:00" for never-played
- Used in web data file generation (cgos.py:1684-1688):
  ```python
  atme = ctme - datetime.timedelta(seconds=86400 * 190)  # 190 days
  # Only include players who played in last 190 days
  db.execute("SELECT ... FROM password WHERE last_game >= ?")
  ```

**Operations**:

**Insert (new player)**:
```python
db.execute(
    """INSERT INTO password VALUES(?, ?, 0, ?, ?, "2000-01-01 00:00")""",
    (username, password_hash, defaultRatingAverage, cfg.maxK)
)
```
- `games` starts at 0
- `rating` is set to current average rating
- `K` is set to maximum (for volatile rating)

**Update (rating change)**:
```python
db.execute(
    "UPDATE password SET rating=?, K=?, last_game=?, games=games+1 WHERE name==?",
    (new_rating, new_k, timestamp, username)
)
```
- Called by `batchRate()` after each game
- Atomic transaction with other player's update

**Update (password change)**:
```python
db.execute(
    "UPDATE password SET pass=? WHERE name=?",
    (new_password_hash, username)
)
```

**Select (authentication)**:
```python
db.execute(
    "SELECT pass, rating, K FROM password WHERE name = ?",
    (username,)
)
```

---

### Table: games (state.db)

**Purpose**: Store game results and current state

**Creation** (cgos.py:103-107):
```sql
CREATE TABLE games(
    gid INT,
    w TEXT,
    wr TEXT,
    b TEXT,
    br TEXT,
    dte TIMESTAMP,
    wtu INT,
    btu INT,
    res TEXT,
    final TEXT,
    PRIMARY KEY(gid)
)

CREATE INDEX white ON games(w)
CREATE INDEX black ON games(b)
```

**Schema**:

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `gid` | INTEGER | PRIMARY KEY | Game ID (unique) |
| `w` | TEXT | Not Null | White player name |
| `wr` | TEXT | Not Null | White rating at game start (display string) |
| `b` | TEXT | Not Null | Black player name |
| `br` | TEXT | Not Null | Black rating at game start (display string) |
| `dte` | TIMESTAMP | Not Null | Game date/time (format: "YYYY-MM-DD HH:MM") |
| `wtu` | INTEGER | Not Null | White time used in milliseconds |
| `btu` | INTEGER | Not Null | Black time used in milliseconds |
| `res` | TEXT | Not Null | Game result (e.g., "B+2.5", "W+Resign") |
| `final` | TEXT | Not Null | Rating status ("n"=unrated, "y"=rated) |

**Typical Data**:
```
gid: 12345
w: "GnuGo"
wr: "1850"
b: "Leela"
br: "1900?"
dte: "2024-06-20 14:30"
wtu: 1200000
btu: 1189500
res: "B+2.5"
final: "y"
```

**Column Details**:

**gid**:
- Game ID (primary key)
- Unique identifier for each game
- Matches `gameid` table counter
- Incremental (1, 2, 3, ...)
- Never reused

**w** (white player):
- Username of white player
- Matches `password.name`
- Indexed for efficient queries

**wr** (white rating)**:
- Rating display string at game start
- Format: "1850" (established) or "1900?" (provisional)
- Includes "?" suffix if K > 16 at game time
- Snapshot of rating at game start (for historical record)
- Different from current rating in `password` table

**b** (black player)**:
- Username of black player
- Matches `password.name`
- Indexed for efficient queries

**br** (black rating)**:
- Rating display string at game start
- Same format as `wr`
- Snapshot at game time

**dte** (date/time)**:
- Game creation timestamp
- Format: "YYYY-MM-DD HH:MM"
- Example: "2024-06-20 14:30"
- Used for sorting and filtering recent games

**wtu** (white time used)**:
- Time consumed by white player
- Milliseconds (full second = 1000 ms)
- Calculated as: `level - remaining_time`
- Example: 1200000 ms = 20 minutes
- Used in game statistics and reports

**btu** (black time used)**:
- Time consumed by black player
- Same unit and calculation as `wtu`
- Example: 1189500 ms = ~19.8 minutes

**res** (result)**:
- Game result string
- Possible values:
  - `"B+2.5"` - Black wins by 2.5 points
  - `"W+3.0"` - White wins by 3.0 points
  - `"B+Resign"` - White resigns
  - `"W+Resign"` - Black resigns
  - `"B+Time"` - White forfeits on time
  - `"W+Time"` - Black forfeits on time
  - `"B+Illegal"` - White made illegal move
  - `"W+Illegal"` - Black made illegal move
  - `"Draw"` - Game drawn (rare)

**final** (rating status)**:
- Two possible values:
  - `"n"` - Not finalized (awaiting rating update)
  - `"y"` - Finalized (ratings have been applied)
- Workflow:
  1. Game completes → `final = "n"`
  2. `batchRate()` runs → calculates new ratings, updates `password` table
  3. Update: `SET final = "y"`
  4. Game never re-rated again

**Indexes**:
- `white ON games(w)` - Fast lookup of all games by white player
- `black ON games(b)` - Fast lookup of all games by black player
- Primary key `gid` automatically indexed

**Operations**:

**Insert (game completion)**:
```python
db.execute(
    """INSERT INTO games VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, "n" )""",
    (gid, white_name, white_rating_display, black_name, black_rating_display,
     timestamp, white_time_ms, black_time_ms, result_string)
)
```
- Called by `gameover()` when game ends
- `final` is always "n" initially

**Update (rating finalization)**:
```python
db.execute(
    """UPDATE games SET final="y" WHERE gid=?""",
    (gid,)
)
```
- Called by `batchRate()` after rating update

**Select (unrated games)**:
```python
db.execute(
    'SELECT gid, w, b, res, dte FROM games WHERE final == "n"'
)
```
- Called by `batchRate()` to find games to rate

**Select (match history)**:
```python
db.execute(
    "SELECT count(*) FROM games WHERE w==? AND b==?",
    (white_name, black_name)
)
```
- Called by `match_games()` to balance colors
- Counts how many times white played against black

**Select (web data - recent games)**:
```python
db.execute(
    "SELECT gid, w, wr, b, br, dte, wtu, btu, res FROM games WHERE dte >= ?",
    (cutoff_timestamp,)  # Last 4 hours
)
```
- Called by `write_web_data_file()` to show recent games

---

### Table: anchors

**Purpose**: Store ratings for reference engines (calibration points)

**Creation** (cgos.py:108):
```sql
CREATE TABLE anchors(
    name TEXT PRIMARY KEY,
    rating FLOAT
)
```

**Schema**:

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `name` | TEXT | PRIMARY KEY | Anchor player name |
| `rating` | FLOAT | Not Null | Fixed rating for this anchor |

**Typical Data**:
```
name: "GnuGo_anchor"
rating: 1700.0

name: "Leela_anchor"
rating: 1850.0
```

**Purpose of Anchors**:
- Reference engines with fixed ratings
- Provide calibration points for the rating scale
- Their ratings never change despite game results
- Used to validate rating calculations
- Prevent rating inflation/deflation over time

**Column Details**:

**name**:
- Anchor identifier (should match `password.name` entry)
- Create the anchor player in `password` table first
- Can be added to this table without being in active play

**rating**:
- Fixed Elo rating
- When anchor plays a game, result doesn't affect their rating
- Their rating is always reset to this value in `batchRate()`
- Example: 1700.0 (not 1700? with ? suffix)

**Operations**:

**Insert (create anchor)**:
```python
db.execute(
    "INSERT INTO anchors (name, rating) VALUES (?, ?)",
    ("GnuGo", 1700.0)
)
```

**Select (load anchors)**:
```python
anchors = {}
for nme, rat in db.execute("SELECT name, rating FROM anchors"):
    anchors[nme] = rat
```
- Called by `batchRate()` to constrain ratings
- If player is in anchors dict, their new rating is reset

**Effect in Rating Process** (cgos.py:398-404):
```python
# make sure anchors retain their ratings
if w in anchors:
    nwr = anchors[w]  # Override calculated rating
    nwK = cfg.minK     # Lock K-factor to minimum
if b in anchors:
    nbr = anchors[b]
    nbK = cfg.minK
```

---

### Table: clients

**Purpose**: Store client connection statistics (future use)

**Creation** (cgos.py:109):
```sql
CREATE TABLE clients(name, count)
```

**Schema**:

| Column | Type | Purpose |
|---|---|---|
| `name` | TEXT | Client identifier |
| `count` | INTEGER | Connection count |

**Status**: Appears to be defined but not actively used in current codebase.

---

## Archive Database (archive.db)

The archive database stores compressed game records for long-term storage.

### Table: games (archive.db)

**Purpose**: Store complete game data in compressed format

**Creation** (cgos.py:135):
```sql
CREATE TABLE IF NOT EXISTS games(gid, see, see2)
```

**Schema**:

| Column | Type | Purpose |
|---|---|---|
| `gid` | INTEGER | Game ID (matches state.db) |
| `see` | TEXT | Serialized game data (moves, ratings, metadata) |
| `see2` | TEXT | Analysis data (move analysis JSON) |

**Data Population**:

Games are added to archive.db in `gameover()` function (cgos.py:590-594):

```python
def gameover(gid: int, sc: str, err: str) -> None:
    # ...
    see, see2 = seeRecord(games[gid], sc, dte, tme)
    
    if dbrec:
        dbrec.execute("INSERT INTO games VALUES(?, ?, ?)", (gid, see, see2))
        dbrec.commit()
```

**Column Details**:

**gid**:
- Game ID (matches `state.db.games.gid`)
- Unique identifier for each game
- Links archived game to state database

**see** (serialized game data):
- Complete game information in text format
- Created by `seeRecord()` function (cgos.py:296-307):
  ```python
  def seeRecord(game: Game, res: str, dte: str, tme: str) -> Tuple[str, str]:
      s = ""
      s += f"{tme} {cfg.boardsize} {cfg.komi} "
      s += f"{game.w}({game.white_rate}) {game.b}({game.black_rate}) "
      s += f"{cfg.level} {joinMoves(game.moves)} {res}"
      a = joinAnalysis(game.moves)
      return s, a
  ```

**Example `see` value**:
```
2024-06-20 14:30:25 19 7.0 GnuGo(1850) Leela(1900?) 1200000 D4 1200000 Q4 1199500 E4 1199000 Q3 1198500 B+2.5
```

**Components**:
- Timestamp: "2024-06-20 14:30:25"
- Board size: 19
- Komi: 7.0
- White player and rating: "GnuGo(1850)"
- Black player and rating: "Leela(1900?)"
- Time level: 1200000 (milliseconds)
- Move sequence with times: "D4 1200000 Q4 1199500 ..."
- Result: "B+2.5"

**see2** (analysis data):
- Analysis information from moves
- Extracted from move JSON if present
- Contains engine analysis (winrate, visits, PV, etc.)
- Can be empty if no analysis provided
- Format: newline-separated JSON objects
- Correponds to `moves[i][2]` (optional third field in move tuple)

**Example `see2` value**:
```
{"visits": 1000, "winrate": 0.65, "pv": "D4 Q4"}
{"visits": 950, "winrate": 0.58, "pv": "Q4 E4"}
{"visits": 920, "winrate": 0.62, "pv": "E4 Q3"}
```

**Operations**:

**Insert (game completion)**:
```python
see, see2 = seeRecord(games[gid], result, date, time)
dbrec.execute("INSERT INTO games VALUES(?, ?, ?)", (gid, see, see2))
dbrec.commit()
```

**Select (game retrieval - for viewers)**:
```python
rec = dbrec.execute(
    "SELECT dta FROM games WHERE gid = ?",
    (gid,)
).fetchone()
```
- Called by `viewer_respond()` to retrieve archived games
- Allows viewers to watch past games

**Compression**:
- Archive database can use SQLite compression extensions
- Configuration option `compressSgf: true` enables compression
- Reduces storage for long-term archival

---

## Web Data File (wdata.txt)

**Purpose**: Real-time game updates and player standings for web display

**Location**: Configured in YAML, typically:
```yaml
web_data_file: "<server-data>/19x19/wdata.txt"
```

**Update Frequency**: Every time `schedule_games()` is called (~15 seconds)

**Generation**: `write_web_data_file()` function (cgos.py:1665-1726)

### File Format

Text file with line-based records. Each line starts with a record type indicator.

**Record Types**:

#### 1. Timestamp Record

**Format**: `<timestamp>`

**Location**: First line

**Example**:
```
2024-06-20 14:30:45
```

**Purpose**: When the file was generated

---

#### 2. User Record (u)

**Format**: `u <name> <games> <rating> <last_game>`

**Example**:
```
u GnuGo 547 1850 2024-06-20 14:25:33
u Leela 892 1900? 2024-06-20 14:27:15
u NewBot 12 1800? 2024-06-20 14:28:00
```

**Conditions**: Players with games in last 190 days

**Data Source** (cgos.py:1684-1688):
```python
atme = ctme - datetime.timedelta(seconds=86400 * 190)  # 190 days
lutme = atme.strftime("%Y-%m-%d %H:%M:%S")
for nme, gms, rat, k, lg in db.execute(
    "SELECT name, games, rating, K, last_game FROM password WHERE last_game >= ?",
    (lutme,),
):
    wd.write(f"u {nme} {gms} {strRate(rat, k)} {lg}\n")
```

**Fields**:
- `name`: Player username
- `games`: Total games played
- `rating`: Current rating (with "?" for provisional)
- `last_game`: Timestamp of most recent game

**Usage**: Web builder generates standings/rankings

---

#### 3. Game Record (g)

**Format**: `g <gid> <white> <wr> <black> <br> <dte> <wtu> <btu> <res>`

**Example**:
```
g 12344 GnuGo 1850 Leela 1900? 2024-06-20 14:15 1200000 1189500 B+2.5
g 12345 Leela 1900? GnuGo 1850 2024-06-20 14:20 1198500 1195000 W+3.5
```

**Conditions**: Games completed in last 4 hours

**Data Source** (cgos.py:1704-1708):
```python
atme = ctme - datetime.timedelta(seconds=3600 * 4)  # 4 hours
lutme = atme.strftime("%Y-%m-%d %H:%M:%S")
for (gid, w, wr, b, br, dte, wtu, btu, res) in db.execute(
    "SELECT gid, w, wr, b, br, dte, wtu, btu, res FROM games WHERE dte >= ?",
    (lutme,),
):
    wd.write(f"g {gid} {w} {wr} {b} {br} {dte} {wtu} {btu} {res}\n")
```

**Fields**:
- `gid`: Game ID
- `white`: White player name
- `wr`: White rating at game start
- `black`: Black player name
- `br`: Black rating at game start
- `dte`: Game date/time
- `wtu`: White time used (ms)
- `btu`: Black time used (ms)
- `res`: Result

**Usage**: Recent games list on web page

---

#### 4. Status Record (s)

**Format**: `s <dte> <gid> <white> <black> <last_move_start_time> <wtl> <btl> <wr> <br> <wconnected> <bconnected> <lastmove_ms>`

**Example**:
```
s 2024-06-20 14:30:45 12346 GnuGo Leela 1718905445123 600000 620000 1850 1900? 1 1 234567
s 2024-06-20 14:30:45 12347 AlphaGo Pachi 1718905401000 450000 480000 2000 1750? 1 0 44123
```

**Conditions**: All currently active games

**Data Source** (cgos.py:1713-1723):
```python
for gid, rec in games.items():
    wconnected = 1 if rec.w in act else 0
    bconnected = 1 if rec.b in act else 0
    lastmove = ct - rec.last_move_start_time
    
    wd.write(
        f"s {tmeSch} {gid} {rec.w} {rec.b} {rec.last_move_start_time}"
        + f" {rec.white_remaining_time} {rec.black_remaining_time} "
        + f"{rec.white_rate} {rec.black_rate}"
        + f" {wconnected} {bconnected} {lastmove}\n"
    )
```

**Fields**:
- `dte`: File generation timestamp
- `gid`: Game ID
- `white`: White player
- `black`: Black player
- `last_move_start_time`: Millisecond timestamp of last move
- `wtl`: White time left (milliseconds)
- `btl`: Black time left (milliseconds)
- `wr`: White rating display
- `br`: Black rating display
- `wconnected`: 1=connected, 0=disconnected
- `bconnected`: 1=connected, 0=disconnected
- `lastmove_ms`: Milliseconds since last move

**Usage**: 
- Game viewer (real-time game state)
- Live board display
- Connection status monitoring

### File Operations

**Creation**:
```python
tmpf = os.path.join(workdir, "dta.cgos.tmp")  # Temporary file
with open(tmpf, "w") as wd:
    # ... write records ...
os.replace(tmpf, cfg.web_data_file)           # Atomic rename
shutil.copy(cfg.web_data_file, cfg.htmlDir)   # Copy to web directory
```

**Atomic Update**:
- Write to temporary file first
- Atomic rename to final filename
- Prevents partial reads by web builder

**Distribution**:
- Copied to HTML directory for web access
- Web builder reads and parses this file
- Generates HTML standings, crosstables, etc.

---

## Data Relationships

### Player Registration Workflow

```
User connects with username/password
    ↓
Query password table for username
    ↓
If exists: fetch pass, rating, K
If not exists: INSERT new row
    password.name = username
    password.pass = hashed_password
    password.games = 0
    password.rating = defaultRatingAverage
    password.K = maxK
    password.last_game = "2000-01-01 00:00"
```

### Game Lifecycle

```
1. INITIALIZATION (init_game)
   - Allocate gid from gameid table
   - Increment gameid.gid for next game
   - Create entry in active games dict (not DB)
   - Snapshot ratings into Game object

2. GAMEPLAY (during genmove/play)
   - Moves added to Game.moves list
   - Time values updated in Game object
   - No database writes during play

3. COMPLETION (gameover)
   - INSERT into state.db.games table with final="n"
   - INSERT into archive.db.games with see, see2
   - Game object kept for wdata.txt generation

4. RATING (batchRate)
   - SELECT from state.db.games WHERE final="n"
   - For each game:
     * Fetch current ratings from password table
     * Calculate new ratings using Elo formula
     * UPDATE password table
     * UPDATE games SET final="y"
   - Atomic transaction for each game

5. ARCHIVAL (write_web_data_file)
   - Include finalized game in wdata.txt "g" records
   - Archive data already in archive.db
```

### Data Consistency

**Password Table**:
- Always represents current player state
- Updated atomically after game completion
- K-factor only decreases (stabilization)

**Games Table**:
- Immutable after final="y"
- Stores snapshot of ratings at game time
- Can be audited against password table

**Archive Database**:
- Compressed copy of game data
- Read-only after insertion
- Used for viewer playback and historical analysis

---

## Query Examples

### Find all games by a specific player

**SQL**:
```sql
SELECT gid, w, wr, b, br, dte, res
FROM games
WHERE w = 'GnuGo' OR b = 'GnuGo'
ORDER BY dte DESC
LIMIT 50
```

**Why it works**:
- Index on both `w` and `b` columns
- Efficient even with millions of rows

---

### Find head-to-head record

**SQL**:
```sql
SELECT
    w, b, res,
    SUM(CASE WHEN res LIKE 'W%' THEN 1 ELSE 0 END) as w_wins,
    SUM(CASE WHEN res LIKE 'B%' THEN 1 ELSE 0 END) as b_wins,
    COUNT(*) as total_games
FROM games
WHERE (w = 'GnuGo' AND b = 'Leela') OR (w = 'Leela' AND b = 'GnuGo')
GROUP BY w, b
ORDER BY dte DESC
```

---

### Find unrated games

**SQL** (used by batchRate):
```sql
SELECT gid, w, b, res, dte
FROM games
WHERE final = 'n'
```

---

### Get current standings

**SQL**:
```sql
SELECT
    name, games, rating, K,
    CASE WHEN K > 16.0 THEN '?' ELSE '' END as provisional
FROM password
WHERE games > 0
ORDER BY rating DESC
LIMIT 100
```

---

### Find disconnected players in active games

**SQL** (implicit in schedule_games):
```python
for gid in list(games.keys()):
    if gid not in act:  # Check if player still connected
        # Handle disconnect
```

---

### Recent player activity

**SQL** (used for wdata.txt):
```sql
SELECT name, games, rating, K, last_game
FROM password
WHERE last_game >= datetime('now', '-190 days')
ORDER BY last_game DESC
```

---

## Indexing Strategy

### Primary Keys

**Automatic Indexes**:
- `gameid.ROWID` - Single row table
- `password.name` - Unique player identifier
- `games.gid` - Game ID
- `anchors.name` - Anchor identifier

### Manual Indexes

**Created in initDatabase** (cgos.py:106-107):
```sql
CREATE INDEX white ON games(w)
CREATE INDEX black ON games(b)
```

**Purpose**:
- Speed up queries like: `SELECT * FROM games WHERE w = 'GnuGo'`
- Speed up match history queries
- Efficient player game lookup

**Query Plans**:
```sql
-- Uses index, fast O(log n):
SELECT ... FROM games WHERE w = 'GnuGo'

-- Uses index, fast O(log n):
SELECT count(*) FROM games WHERE w = 'A' AND b = 'B'

-- Full table scan if no other predicates:
SELECT * FROM games ORDER BY dte DESC
```

### No Index Needed

**Already covered by primary key**:
- `games.gid` - Queries using game ID
- `password.name` - Player lookups

**Rarely queried**:
- `games.dte` - Sorted but not filtered much
- Could add if performance becomes issue

---

## Data Retention

### Active Session Data (state.db)

**Retained indefinitely**:
- All game records (not deleted, only marked final="y")
- All player records (not deleted, ratings persist)
- Gameid counter (only incremented)

**Cleanup**: Manual maintenance required
- Delete old games if needed
- Vacuum database to reclaim space

### Archive Data (archive.db)

**Retention Policy**: No automatic deletion
- All games kept in archive
- Can be compressed if `compressSgf: true`
- Use archive for long-term storage

### Web Data (wdata.txt)

**Retention in File**:
- Players: Last 190 days of activity
- Completed games: Last 4 hours
- Active games: Current only

**Why Limited**:
- File generated fresh every 15 seconds
- Only includes recent data for web display
- Complete history in state.db and archive.db

### Example Retention Timeline

```
Time T
├─ wdata.txt generated with:
│  ├─ Players active last 190 days
│  ├─ Games in last 4 hours
│  └─ Active games (current round)
│
Time T+15s
├─ wdata.txt regenerated
│  ├─ Same players still active
│  ├─ New games in window, old ones removed
│  ├─ New active games, old ones completed
│
Time T+4 hours
├─ Games from T-4 hours removed from wdata.txt
├─ But still in state.db and archive.db
│
Time T+190 days
├─ Inactive players removed from wdata.txt
├─ But still in state.db with last_game timestamp
```

---

## Source Code Reference

### Database Files

**File**: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/app/cgos.py`

| Function | Line | Purpose |
|---|---|---|
| `initDatabase()` | 84 | Create tables on first run |
| `openDatabase()` | 116 | Open connections to databases |
| `batchRate()` | 319 | Update ratings after games |
| `gameover()` | 558 | Record game completion |
| `seeRecord()` | 296 | Serialize game data |
| `getAnchors()` | 310 | Load anchor definitions |
| `write_web_data_file()` | 1665 | Generate wdata.txt |

### Configuration

**File**: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/app/config.py`

Database paths defined as:
```python
database_state_file: str       # state.db path
game_archive_database: str     # archive.db path
web_data_file: str            # wdata.txt path
```

### Data Classes

**File**: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/gogame/game.py`

```python
class Game:
    w: str                  # White player
    b: str                  # Black player
    last_move_start_time: int
    white_remaining_time: int
    black_remaining_time: int
    white_rate: str         # Rating display
    black_rate: str
    moves: List[Tuple[str, int, Optional[str]]]  # Move, time, analysis
    ctime: datetime.datetime  # Game creation time
```

---

## Summary

The CGOS database system uses a three-layer approach:

### Layer 1: State Database (state.db)
- **Purpose**: Current game state and player ratings
- **Key Tables**: `gameid`, `password`, `games`, `anchors`
- **Guarantees**: Atomic transactions, durable storage
- **Updated**: Continuously during gameplay and rating

### Layer 2: Archive Database (archive.db)
- **Purpose**: Long-term game record storage
- **Key Table**: `games` (with move sequences and analysis)
- **Guarantees**: Immutable historical record
- **Updated**: Once per game completion

### Layer 3: Web Data File (wdata.txt)
- **Purpose**: Real-time updates for web display
- **Records**: Players, recent games, active games
- **Guarantees**: Atomic file updates every 15 seconds
- **Scope**: Recent data only (190 days, 4 hours, current)

This design provides:
- **Consistency**: Atomic rating updates
- **Durability**: Persistent archives
- **Performance**: Indexed lookups, batch processing
- **Scalability**: Efficient queries, deferred rating updates
- **Auditability**: Complete game history

---

**File created**: CGOS Database Schema Documentation
**Coverage**: Complete column-by-column reference with examples
**Scope**: All three storage mechanisms (state.db, archive.db, wdata.txt)
