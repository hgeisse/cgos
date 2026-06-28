# CGOS Game Rating System - Complete Implementation Guide

## Table of Contents
1. [Overview](#overview)
2. [Rating System Components](#rating-system-components)
3. [Rating Calculation Process](#rating-calculation-process)
4. [K-Factor Management](#k-factor-management)
5. [New Player Initialization](#new-player-initialization)
6. [Batch Rating Process](#batch-rating-process)
7. [Rating Display](#rating-display)
8. [Configuration Parameters](#configuration-parameters)
9. [Example Scenarios](#example-scenarios)
10. [Source Code Reference](#source-code-reference)

---

## Overview

CGOS uses the **Elo rating system**, adapted from chess for competitive Go engine rating. The system is designed to:

- **Measure Strength**: Provide a numerical rating reflecting an engine's playing strength
- **Predict Outcomes**: Calculate the probability of winning based on rating difference
- **Track Progress**: Show improvement over time through rating changes
- **Stabilize Ratings**: Use dynamic K-factors to reduce rating volatility for established players
- **Anchor Calibration**: Maintain fixed ratings for reference engines (anchors)

**Key Principles:**
- A player rated 1800 is expected to beat a player rated 1700 approximately 64% of the time
- New players have volatile ratings; established players have stable ratings
- Anchor players maintain fixed ratings to provide rating calibration reference points

---

## Rating System Components

### Core Rating Components

Each player maintains three rating-related values in the database:

| Field | Type | Purpose |
|-------|------|---------|
| `rating` | float | Current Elo rating (e.g., 1800.5) |
| `K` | float | K-factor controlling rating change magnitude |
| `games` | int | Total number of games played (counter) |
| `last_game` | timestamp | Timestamp of most recent game |

### Rating State in Active Connections

While connected, the server stores additional state in the `ActiveUser` object:

```python
class ActiveUser:
    rating: float    # Current rating
    k: float        # Current K-factor
    msg_state: str  # "waiting", "genmove", "gameover", etc.
    # ... other fields
```

---

## Rating Calculation Process

### Phase 1: Game Result Determination

When a game ends, the server calls `gameover(gid, result, error_msg)` which:

1. **Records game in database** with a `final` flag set to `"n"` (not finalized for rating)
2. **Stores result string** in standard format:
   - `"B+2.5"` - Black wins by 2.5 points
   - `"W+Resign"` - White wins by resignation
   - `"B+Time"` - Black wins by timeout
   - `"Draw"` - Game drawn (rare)

Example database insertion (cgos.py:596-599):
```python
db.execute(
    """INSERT INTO games VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, "n" )""",
    (gid, game.w, game.white_rate, game.b, game.black_rate, tme, wtu, btu, sc),
)
db.commit()
```

### Phase 2: Batch Rating (Deferred Processing)

The server periodically calls `batchRate()` (cgos.py:319-431) to process all unfinalized games. This happens:
- When `schedule_games()` completes a round (cgos.py:1621)
- Processes all games with `final == "n"`
- Calculates new ratings and updates database atomically

**Batch Rating Flow:**

```
FOR each game WITH final == "n":
  1. Fetch current ratings and K-factors
  2. Normalize K-factors to minK if too low
  3. Calculate effective K-factors based on opponent strength
  4. Determine result score (1.0, 0.5, or 0.0)
  5. Calculate new ratings using Elo formula
  6. Calculate K-factor reduction
  7. Apply anchor constraints (if player is anchor)
  8. Update database (atomic transaction)
  9. Update active player cache
  10. Mark game as final == "y"
```

---

## Rating Calculation Details

### Step 1: Normalize K-Factors

Before calculation, ensure K-factor is at least the minimum (cgos.py:350-353):

```python
if wk < cfg.minK:
    wk = cfg.minK
if bk < cfg.minK:
    bk = cfg.minK
```

This prevents K-factors from falling below the configured minimum.

### Step 2: Calculate K-Factor Strength Ratio

The system calculates how "strong" each player's K-factor is relative to the configured range (cgos.py:355-362):

```
K range = maxK - minK
White K strength = 1.0 - (wk - minK) / kRange
Black K strength = 1.0 - (bk - minK) / kRange

Effective White K = wk * (Black K strength)
Effective Black K = bk * (White K strength)
```

**Purpose:** When a strong player (high established rating, low K) plays a new player (high K), the strong player's effective K is reduced to prevent large rating swings from a single game.

**Example:**
```
Configuration:
  minK = 3.0
  maxK = 200.0
  kRange = 197.0

White (established): K = 10.0
Black (new):        K = 200.0

wks = 1.0 - (10 - 3) / 197 = 1.0 - 0.0355 = 0.9645
bks = 1.0 - (200 - 3) / 197 = 1.0 - 1.0 = 0.0

weK = 10.0 * 0.0 = 0.0        (white's effective K is 0)
beK = 200.0 * 0.9645 = 192.9  (black's effective K is 192.9)

Result: White's rating barely changes; Black's rating changes significantly
```

### Step 3: Determine Game Result Score

Convert result string to numerical result score (cgos.py:364-370):

```python
if res[0] == "W":        # White wins (B+..., W+..., etc.)
    wres = 1.0
    bres = 0.0
elif res[0] == "B":      # Black wins
    wres = 0.0
    bres = 1.0
else:                    # Draw or other
    wres = 0.5
    bres = 0.5
```

| Result String | White Score | Black Score |
|---|---|---|
| `B+2.5`, `B+Resign`, `B+Time` | 0.0 | 1.0 |
| `W+2.5`, `W+Resign`, `W+Time` | 1.0 | 0.0 |
| `Draw` | 0.5 | 0.5 |

### Step 4: Calculate Expected Win Rate

Use the Elo expectation formula (rating.py:6-9):

```python
def expectation(me: float, you: float) -> float:
    x = (you - me) / 400.0
    d: float = 1.0 + pow(10.0, x)
    return 1.0 / d
```

**Formula:**
```
E(A vs B) = 1 / (1 + 10^((B - A) / 400))
```

**Interpretation:**
- If A and B have same rating: E(A) = 0.5 (50% chance A wins)
- If A is 100 points higher: E(A) ≈ 0.64 (64% chance A wins)
- If A is 200 points higher: E(A) ≈ 0.76 (76% chance A wins)
- If A is 400 points higher: E(A) ≈ 0.91 (91% chance A wins)

This is called in `newrating()` (rating.py:12-15):

```python
def newrating(cur_rating: float, opp_rating: float, res: float, K: float) -> float:
    ex = expectation(cur_rating, opp_rating)
    nr = cur_rating + K * (res - ex)
    return nr
```

**Called for both players** (cgos.py:372-373):
```python
nwr = newrating(wr, br, wres, weK)  # White's new rating
nbr = newrating(br, wr, bres, beK)  # Black's new rating
```

### Step 5: Calculate New Ratings

Applied separately for each player using `newrating()` function:

```
New Rating = Current Rating + K * (Result - Expected)
```

**Where:**
- `Current Rating` = Player's rating before game
- `K` = Effective K-factor (calculated in Step 2)
- `Result` = Actual result (1.0, 0.5, or 0.0)
- `Expected` = Expected win probability from Elo formula

**Examples:**

**Scenario 1: Upset Victory**
```
White (1800): Expected 0.64 vs Black (1700)
White WINS: new = 1800 + 16 * (1.0 - 0.64) = 1800 + 5.76 = 1805.76
Black LOSES: new = 1700 + 16 * (0.0 - 0.36) = 1700 - 5.76 = 1694.24
```

**Scenario 2: Expected Victory**
```
White (1800): Expected 0.64 vs Black (1700)
Black WINS (upset!): new = 1700 + 16 * (1.0 - 0.36) = 1700 + 10.24 = 1710.24
White LOSES: new = 1800 + 16 * (0.0 - 0.64) = 1800 - 10.24 = 1789.76
```

**Scenario 3: New vs Established Player**
```
Established (1800, K=10): Expected 0.95 vs New (1400, K=200)
Established WINS: new = 1800 + 10 * (1.0 - 0.95) = 1800 + 0.5 = 1800.5
New LOSES: new = 1400 + 200 * (0.0 - 0.05) = 1400 - 10 = 1390

New WINS (upset!): 
  new = 1400 + 200 * (1.0 - 0.05) = 1400 + 190 = 1590
  established = 1800 + 10 * (0.0 - 0.95) = 1800 - 9.5 = 1790.5
```

---

## K-Factor Management

### K-Factor Purpose

The K-factor controls how much a player's rating changes per game:
- **High K** (50-200): Large rating changes per game (volatile)
- **Low K** (3-30): Small rating changes per game (stable)

### K-Factor Lifecycle

#### Initial K-Factor (New Players)

When a new player authenticates, they receive the maximum K-factor (cgos.py:868-869):

```python
db.execute(
    """INSERT INTO password VALUES(?, ?, 0, ?, ?, "2000-01-01 00:00")""",
    (
        who,           # username
        pw_store,      # password
        defaultRatingAverage,  # initial rating
        cfg.maxK,      # initial K-factor (max)
    ),
)
```

**Typical Initial Values:**
- `rating` = `defaultRatingAverage` (or 1800)
- `K` = `maxK` (200)
- `games` = 0

#### K-Factor Reduction Per Game

After each game, the K-factor is reduced based on opponent strength (cgos.py:375-388):

```python
# Reduction factor based on current K
if wk <= 32.0:
    rf = 0.02  # Lower reduction for established players
else:
    rf = 0.04  # Higher reduction for new players

nwK = wk * (1.0 - rf * bks)  # Apply reduction based on opponent
nbK = bk * (1.0 - rf * wks)  # Apply reduction based on opponent

# Enforce minimum K
if nbK < cfg.minK:
    nbK = cfg.minK
if nwK < cfg.minK:
    nwK = cfg.minK
```

**K-Reduction Formula:**
```
New K = Current K * (1.0 - ReductionFactor * OpponentKStrength)

where:
  ReductionFactor = 0.02 if K <= 32, else 0.04
  OpponentKStrength = 1.0 - (Opponent_K - minK) / (maxK - minK)
```

**Purpose of Opponent Strength in Reduction:**
- Playing against established players (low K) reduces your K less
- Playing against new players (high K) reduces your K more
- This encourages players to play each other

**Example K-Reduction:**
```
Configuration: minK=3, maxK=200
White: K=100 (newer player), plays Black: K=50 (established)

bks = 1.0 - (50 - 3) / 197 = 0.761
rf = 0.04 (since 100 > 32)
nwK = 100 * (1.0 - 0.04 * 0.761) = 100 * (1.0 - 0.0304) = 96.96

Black: K=50
wks = 1.0 - (100 - 3) / 197 = 0.507
rf = 0.02 (since 50 <= 32 is false, so 0.04)
Actually: rf = 0.04 (since 50 > 32)
nbK = 50 * (1.0 - 0.04 * 0.507) = 50 * (1.0 - 0.0203) = 48.98
```

### K-Factor Floor

The minimum K-factor prevents ratings from becoming completely frozen (cgos.py:350-353, 392-395):

```python
minK = 3.0   # typical configuration
maxK = 200.0 # typical configuration

# Enforce floor
if K < minK:
    K = minK
```

Even after hundreds of games, established players maintain a small K of 3.0, ensuring their rating can still change slowly.

---

## New Player Initialization

### Default Rating Calculation

When the server starts, it calculates `defaultRatingAverage` from existing players (cgos.py:1838-1843):

```python
global defaultRatingAverage

# Fetch all player ratings
lst = []
r_sum = 0.0
for name, rat, k in db.execute("SELECT name, rating, K FROM password"):
    if rat > 0:  # valid rating
        lst.append((name, rat))
        r_sum += rat

# Calculate average (excluding bottom SKIP players)
ll = len(lst)
if ll > 0:
    defaultRatingAverage = r_sum / ll
else:
    defaultRatingAverage = cfg.defaultRating
```

**Purpose:** New players start at the average rating of all existing players, not a fixed value. This prevents rating inflation or deflation over time.

### Registration Process

When a new player authenticates with a password that doesn't exist (cgos.py:858-872):

1. Check if user is admin (if so, close connection)
2. Hash password if configured
3. Insert into database with:
   - `rating` = `defaultRatingAverage`
   - `K` = `maxK` (200)
   - `games` = 0
   - `last_game` = "2000-01-01 00:00"

```python
logger.info(f"[{who}] new user")
if cfg.hashPassword:
    pw_store = passctx.hash(pw)
else:
    pw_store = pw
db.execute(
    """INSERT INTO password VALUES(?, ?, 0, ?, ?, "2000-01-01 00:00")""",
    (who, pw_store, defaultRatingAverage, cfg.maxK),
)
db.commit()
```

---

## Batch Rating Process

### Trigger Conditions

`batchRate()` is called automatically (cgos.py:1621):

```python
def schedule_games() -> None:
    # ... check for timeouts, schedule new games ...
    batchRate()  # After scheduling completes
```

This runs approximately every 15 seconds (cgos.py:63):

```python
schedule_games_interval = 15.0
```

### Processing Flow

The function processes all unfinalized games in a batch transaction (cgos.py:319-431):

```python
def batchRate() -> None:
    global act, ratingOf, db
    
    anchors = getAnchors()  # Load anchor players
    tme = now_string()      # Current timestamp
    
    # SELECT all games not yet rated
    batch = db.execute('SELECT gid, w, b, res, dte FROM games WHERE final == "n"')
    
    for gid, w, b, res, dte in batch:
        # ... rating calculations ...
        
        # ATOMIC UPDATE
        with db:  # Transaction
            db.execute(
                "UPDATE password SET rating=?, K=?, last_game=?, games=games+1 WHERE name==?",
                (nwr, nwK, tme, w),
            )
            db.execute(
                "UPDATE password SET rating=?, K=?, last_game=?, games=games+1 WHERE name==?",
                (nbr, nbK, tme, b),
            )
            db.execute("""UPDATE games SET final="y" WHERE gid=?""", (gid,))
    
    db.commit()  # Final commit
```

### Atomic Transaction

The rating update is atomic (cgos.py:419-428):

```python
with db:  # Opens transaction
    db.execute(...)  # Update white
    db.execute(...)  # Update black
    db.execute(...)  # Mark game final
# Transaction committed automatically
```

This ensures:
- Both players' ratings are updated together
- No partial updates if error occurs
- Database consistency maintained

### Anchor Constraint Application

If a player is an "anchor" (reference player), their rating is locked (cgos.py:398-404):

```python
anchors = getAnchors()  # Dict of {name: fixed_rating}

# ... after calculating new ratings ...

if w in anchors:
    nwr = anchors[w]  # Force white's rating to anchor value
    nwK = cfg.minK    # Lock K-factor to minimum
if b in anchors:
    nbr = anchors[b]  # Force black's rating to anchor value
    nbK = cfg.minK    # Lock K-factor to minimum
```

**Example:**
```
Anchor "GnuGo" has rating 1600.0 (fixed)
GnuGo plays and LOSES to NewBot
  Calculated new rating: 1595.2
  Applied rating: 1600.0 (anchor overrides)
  New K: 3.0 (minimum, frozen)
```

Anchors serve as calibration points, their ratings never change.

### Active Connection Cache Update

While updating database, also update active players (cgos.py:406-417):

```python
# Update act record too
if w in act:
    act[w].rating = nwr
    act[w].k = nwK
if b in act:
    act[b].rating = nbr
    act[b].k = nbK

# Update global rating display cache
wsrate = strRate(nwr, nwK)
bsrate = strRate(nbr, nbK)
ratingOf[w] = wsrate
ratingOf[b] = bsrate
```

This ensures:
- Connected players see updated ratings immediately
- Web display uses fresh ratings
- Next game uses updated K-factors

---

## Rating Display

### Rating String Format

The `strRate()` function formats ratings for display (rating.py:18-24):

```python
def strRate(elo: float, k: float) -> str:
    r = "%0.0f" % elo           # Round to nearest integer
    
    if elo < 0.0:
        r = "0"                 # Minimum 0
    
    if k > 16.0:                # Provisional (K > 16)
        r += "?"                # Add "?" suffix
    
    return r
```

**Examples:**

| Elo | K | Display | Meaning |
|---|---|---|---|
| 1850.3 | 5.0 | `1850` | Established player |
| 1750.7 | 200.0 | `1751?` | New player (provisional) |
| 1799.5 | 25.0 | `1800` | Still gaining experience |
| -50.0 | 200.0 | `0?` | Not possible (clamped) |

**Display Interpretation:**
- **No "?"**: Established player, rating is stable (K ≤ 16)
- **With "?"**: Provisional player, rating may change significantly (K > 16)

The "?" provides users with immediate visual feedback on rating reliability.

---

## Configuration Parameters

### Server Configuration (YAML)

In `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/configs/generic/cgos19.yaml`:

```yaml
# Default starting rating for new players
defaultRating: 1800.0

# K-factor bounds
minK: 3.0              # Minimum K (established players)
maxK: 200.0            # Maximum K (new players)

# Matching configuration
anchor_match_rate: 0.1 # Probability of anchor vs anchor match
```

### Rating Configuration Impact

| Parameter | Impact | Example |
|---|---|---|
| `defaultRating` | Starting point for all new players | 1800 vs 1600 affects rating distribution |
| `minK` | Final K for very established players | 3.0 prevents complete rating freeze |
| `maxK` | Initial K for completely new players | 200.0 allows quick rating stabilization |

### Derived Calculations

From configuration:
```
K Range = maxK - minK = 200 - 3 = 197
```

This range is used in K-strength calculation (cgos.py:358-359):
```
strength = 1.0 - (K - minK) / kRange
```

---

## Example Scenarios

### Scenario 1: New Player vs Established Player

**Setup:**
- NewBot (1800 rating, K=200)
- GnuGo (1800 rating, K=10)
- minK=3, maxK=200

**Pre-game:**
```
Configuration: minK=3, maxK=200, kRange=197

NewBot: K=200, strength = 1.0 - (200-3)/197 = 0.0
GnuGo:  K=10,  strength = 1.0 - (10-3)/197 = 0.9645

Expected (1800 vs 1800) = 0.5
NewBot's effective K = 200 * 0.9645 = 192.9
GnuGo's effective K = 10 * 0.0 = 0.0
```

**Game Result: NewBot wins (upset!)**
```
NewBot's new rating = 1800 + 192.9 * (1.0 - 0.5) = 1800 + 96.45 = 1896.45
GnuGo's new rating = 1800 + 0.0 * (0.0 - 0.5) = 1800 + 0 = 1800

NewBot's new K = 200 * (1.0 - 0.04 * 0.9645) = 200 * 0.9614 = 192.28
GnuGo's new K = 10 * (1.0 - 0.02 * 0.0) = 10 * 1.0 = 10
```

**Result:**
- NewBot gains 96 rating points (large jump from upset)
- GnuGo loses 0 rating points (established player protected)
- NewBot's K drops by ~7.7 points
- GnuGo's K unchanged (opponent has high K)

### Scenario 2: Matched Players with History

**Setup:**
- WhiteBot (1750 rating, K=30)
- BlackBot (1800 rating, K=40)
- minK=3, maxK=200

**Pre-game Analysis:**
```
Effective K calculation:
wks = 1.0 - (30-3)/197 = 0.863
bks = 1.0 - (40-3)/197 = 0.813

weK = 30 * 0.813 = 24.39
beK = 40 * 0.863 = 34.52

Expected win rate for White:
E(White vs Black) = 1/(1 + 10^((1800-1750)/400))
                  = 1/(1 + 10^0.125)
                  = 1/(1 + 1.333)
                  = 0.429 (42.9% chance)
```

**Game Result: White wins (expected upset)**
```
White new rating = 1750 + 24.39 * (1.0 - 0.429)
                 = 1750 + 24.39 * 0.571
                 = 1750 + 13.92
                 = 1763.92

Black new rating = 1800 + 34.52 * (0.0 - 0.571)
                 = 1800 - 19.72
                 = 1780.28

White new K = 30 * (1 - 0.04 * 0.813) = 30 * 0.9675 = 29.02
Black new K = 40 * (1 - 0.04 * 0.863) = 40 * 0.9655 = 38.62
```

**Result:**
- White gains 13.9 points (good upset win)
- Black loses 19.7 points (upset loss hurts more than expected win)
- Both K-factors decrease slightly

### Scenario 3: Anchor Player Match

**Setup:**
- AnchorGnuGo (1700 rating, K=3, anchored)
- TestBot (1750 rating, K=50)

**Pre-game:**
```
Expected (1750 vs 1700) = 0.540 for TestBot
```

**Game Result: TestBot wins**
```
Calculated:
TestBot new = 1750 + K_eff * (1.0 - 0.540)
AnchorGnuGo new = 1700 + K_eff * (0.0 - 0.460)
```

**With Anchor Override:**
```
TestBot rating: 1750 + ... (calculated, stored)
AnchorGnuGo rating: 1700 (forced back to anchor value!)
AnchorGnuGo K: 3.0 (forced to minK)
```

**Result:**
- Anchor's rating is reset to 1700 (not changed despite game result)
- Anchor's K is locked to 3.0 (frozen)
- Anchor maintains calibration role

### Scenario 4: Default Rating Calculation

**Server startup with existing players:**
```
Existing players:
  GnuGo:     rating=1800, K=3
  Leela:     rating=1900, K=5
  AlphaGo:   rating=2000, K=8
  Pachi:     rating=1700, K=10

defaultRatingAverage = (1800 + 1900 + 2000 + 1700) / 4 = 1850

When NewBot registers:
  NewBot.rating = 1850 (not 1800 as in config)
  NewBot.K = 200
```

---

## Source Code Reference

### Core Rating Functions

**File: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/app/rating.py`**

```python
def expectation(me: float, you: float) -> float:
    """Calculate expected win probability using Elo formula"""
    x = (you - me) / 400.0
    d: float = 1.0 + pow(10.0, x)
    return 1.0 / d

def newrating(cur_rating: float, opp_rating: float, res: float, K: float) -> float:
    """Calculate new rating after game"""
    ex = expectation(cur_rating, opp_rating)
    nr = cur_rating + K * (res - ex)
    return nr

def strRate(elo: float, k: float) -> str:
    """Format rating for display"""
    r = "%0.0f" % elo
    if elo < 0.0:
        r = "0"
    if k > 16.0:
        r += "?"
    return r
```

### Key Server Functions

**File: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/app/cgos.py`**

| Function | Line | Purpose |
|---|---|---|
| `gameover()` | 558 | Record game result in database |
| `batchRate()` | 319 | Process all unfinalized games and update ratings |
| `getAnchors()` | 310 | Load anchor ratings from database |
| `_handle_player_password()` | 800+ | Initialize new player with ratings |
| `schedule_games()` | 1525+ | Periodic task that calls batchRate() |

### Database Schema

**File: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/app/cgos.py` (lines 100-108)**

**Table: `password`**
```sql
CREATE TABLE password(
    name TEXT PRIMARY KEY,
    pass TEXT,              -- Password hash or plain
    games INT,              -- Total games played
    rating FLOAT,           -- Current Elo rating
    K FLOAT,                -- Current K-factor
    last_game TIMESTAMP     -- Most recent game timestamp
)
```

**Table: `games`**
```sql
CREATE TABLE games(
    gid INT PRIMARY KEY,
    w TEXT,                 -- White player
    wr TEXT,                -- White rating (display string)
    b TEXT,                 -- Black player
    br TEXT,                -- Black rating (display string)
    dte TIMESTAMP,          -- Game date/time
    wtu INT,                -- White time used (ms)
    btu INT,                -- Black time used (ms)
    res TEXT,               -- Result (e.g., "B+2.5")
    final BOOL              -- "n" = unrated, "y" = rated
)
```

**Table: `anchors`**
```sql
CREATE TABLE anchors(
    name TEXT PRIMARY KEY,
    rating FLOAT            -- Fixed rating for this anchor
)
```

### Configuration Classes

**File: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/app/config.py`**

```python
class Configs:
    defaultRating: float     # Initial rating for new players
    minK: float             # Minimum K-factor
    maxK: float             # Maximum K-factor
    # ... other configuration parameters
```

---

## Summary

The CGOS rating system is a comprehensive Elo-based implementation featuring:

1. **Classic Elo Formula**: Expected win probability + rating adjustment
2. **Adaptive K-factors**: Dynamic reduction based on player maturity and opponent strength
3. **Anchor Calibration**: Reference points for rating accuracy
4. **Deferred Batch Processing**: Atomic rating updates every ~15 seconds
5. **Provisional Indicators**: "?" suffix shows rating stability
6. **History Tracking**: Complete game records for rating audits

The system balances:
- **Fairness**: Stronger players protected from rating swings against weaker players
- **Stability**: Established players' ratings change slowly
- **Responsiveness**: New players' ratings stabilize quickly
- **Calibration**: Anchor players maintain fixed reference points

This implementation has proven effective for rating competitive Go engines across multiple servers and instances.
