# CGOS Client Pairing/Matching System - Complete Implementation Guide

## Table of Contents
1. [Overview](#overview)
2. [Game Scheduling Cycle](#game-scheduling-cycle)
3. [The Matching Algorithm](#the-matching-algorithm)
4. [Elo Range Calculation](#elo-range-calculation)
5. [Pairing Strategy](#pairing-strategy)
6. [Match History Constraints](#match-history-constraints)
7. [Anchor Player Handling](#anchor-player-handling)
8. [Game Initialization](#game-initialization)
9. [Configuration Parameters](#configuration-parameters)
10. [Example Matching Scenarios](#example-matching-scenarios)
11. [Source Code Reference](#source-code-reference)

---

## Overview

The CGOS matching system is responsible for:

1. **Identifying Available Players** - Finding all players in "waiting" state
2. **Computing Fair Matchups** - Pairing players with appropriate rating differences
3. **Preventing Repetitive Matches** - Avoiding same-player rematches
4. **Managing Anchor Players** - Ensuring reference players don't always face each other
5. **Balancing Color Assignment** - Giving players equal opportunities as white/black
6. **Game Initialization** - Setting up games with correct parameters

**Key Principle**: Match players with similar ratings, but vary the specific opponents and colors to ensure diverse game experiences and fair rating distribution.

---

## Game Scheduling Cycle

### Periodic Scheduling (Every ~15 seconds)

The server runs `schedule_games()` continuously via the event loop (cgos.py:1938-1977):

```python
async def schedule_games_task() -> None:
    await asyncio.sleep(45.0)  # Initial 45-second delay
    
    while True:
        try:
            schedule_games()
            # ... error handling ...
        except Exception:
            pass
        
        await asyncio.sleep(schedule_games_interval)  # 15 seconds
```

The `schedule_games_interval` is set to 15.0 seconds (cgos.py:63):
```python
schedule_games_interval = 15.0
```

### Scheduling Decision Tree

When `schedule_games()` is called (cgos.py:1534-1662):

```
1. CHECK ACTIVE GAMES
   ├─ Iterate through all games in progress
   ├─ Detect timeouts (player ran out of time)
   ├─ Mark timed-out games as "gameover"
   └─ Update web display with progress
   
2. COUNT ACTIVE GAMES
   ├─ If games still in progress:
   │  └─ Update web data and continue
   └─ If NO games in progress:
      ├─ Call batchRate() to finalize game ratings
      ├─ Check kill file (if found, shutdown)
      ├─ If matchMode == AUTO:
      │  └─ Call match_games() to schedule new round
      └─ Update web data
```

**Key Decision**: If any games are still playing (`count > 0`), do NOT match new games. Wait for all games to finish.

```python
if count > 0:
    # Games still in progress
    write_web_data_file(ctme)
else:
    # No games in progress - ready for new round
    logger.info("Batch rating")
    batchRate()
    # ... handle bad users ...
    if cfg.matchMode == MatchMode.AUTO:
        match_games(ctme)
    write_web_data_file(ctme)
```

**This ensures:**
- Round-based playing (all games in a round start and finish together)
- Ratings are finalized before matching the next round
- Symmetric load (all players get new opponents at same time)

---

## The Matching Algorithm

### Phase 1: Collect Waiting Players

First, identify all players ready to play (cgos.py:1824-1830):

```python
lst: List[Tuple[str, float]] = []
r_sum = 0.0

for name, v in act.items():
    if v.msg_state == "waiting":
        r = v.rating
        lst.append((name, r))
        r_sum += r

lst.sort(key=lambda e: -e[1])  # Sort by rating, highest first
```

**Result**: `lst` = list of (name, rating) tuples sorted by rating (descending)

**Example**:
```
Available players:
  GnuGo:     1850.0
  Leela:     1900.0
  AlphaGo:   2000.0
  Pachi:     1700.0

After sorting:
  [(AlphaGo, 2000), (Leela, 1900), (GnuGo, 1850), (Pachi, 1700)]
```

### Phase 2: Calculate Dynamic Elo Range

The system calculates the maximum rating difference that should be allowed (cgos.py:1817-1865):

```python
RANGE = 500.0  # Minimum initial range

# Step 1: Find maximum rating gap (SKIP = 4)
lst.sort(key=lambda e: -e[1])
ll = len(lst)
e = ll - SKIP

for i in range(e):
    cr = lst[i][1]      # Current player rating
    nr = lst[i + SKIP][1]  # Player 4 positions down
    
    diff = cr - nr
    
    if diff > max_interval:
        max_interval = diff

# Step 2: Apply multiplier and update RANGE
max_interval = max_interval * 1.50
if max_interval > RANGE:
    RANGE = max_interval
```

**Purpose**: Prevent very weak players from never getting matched. By checking the gap between every player and the player 4 positions down, we ensure the range is large enough to include most players.

**SKIP Constant**: 4 (cgos.py:41)
```python
SKIP = 4
```

**Example Calculation**:
```
Players (sorted by rating):
  0: AlphaGo   2000
  1: Leela     1900
  2: GnuGo     1850
  3: Pachi     1700
  4: NewBot    1600
  5: Weak      1300

SKIP = 4, ll = 6, e = 6 - 4 = 2

Check positions:
  i=0: cr=AlphaGo(2000), nr=lst[4]=NewBot(1600)
       diff = 2000 - 1600 = 400
  i=1: cr=Leela(1900), nr=lst[5]=Weak(1300)
       diff = 1900 - 1300 = 600 (max)

max_interval = 600
max_interval *= 1.50 = 900

RANGE = 900 (large enough to include all players)
```

**Edge Case - Very Few Players**:
```python
if e <= 0:
    max_interval = 2000.0  # Default range for <5 players
```

### Phase 3: Randomize and Re-sort

Add randomness to rating-based sorting to vary opponents (cgos.py:1868-1878):

```python
lst = []

for name, v in act.items():
    if v.msg_state == "waiting":
        r = v.rating + RANGE * random.random()
        lst.append((name, r))

lst.sort(key=lambda e: -e[1])  # Sort by permuted rating
```

**Key Insight**: Each player's rating is "perturbed" by a random value up to RANGE. This causes the sorted order to vary from their true rating order.

**Effect**: 
- Same-strength players stay near each other
- Within that group, random pairings occur
- Very weak players might be matched occasionally
- No player gets stuck facing the same opponent every round

**Example**:
```
Original:
  AlphaGo:  2000.0
  Leela:    1900.0
  GnuGo:    1850.0
  Pachi:    1700.0

RANGE = 900

After adding random perturbation (example):
  AlphaGo:  2000 + 900*0.35 = 2315
  Leela:    1900 + 900*0.92 = 2728  (top after perturbation!)
  GnuGo:    1850 + 900*0.01 = 1859
  Pachi:    1700 + 900*0.88 = 2492

New sorted order:
  1. Leela    2728
  2. Pachi    2492
  3. AlphaGo  2315
  4. GnuGo    1859

Result: Leela and Pachi play each other (rating 1900 vs 1700)
        AlphaGo and GnuGo play each other (rating 2000 vs 1850)
```

### Phase 4: Pair Adjacent Players

Create pairs from the re-sorted list (cgos.py:1886-1916):

```python
lst_pairs = iter(lst)
for aa, bb in zip(lst_pairs, lst_pairs):
    if bb is None:
        continue
    
    # Extract player names
    wp = aa[0]  # First player in pair
    bp = bb[0]  # Second player in pair
    
    # Apply constraints...
    # Then create game
    init_game(ctme, wp, bp)
```

**Pairing Method**: Take pairs of adjacent players from the sorted list

```
Sorted list after perturbation:
  [0] Player A
  [1] Player B  <-- Pair with A
  [2] Player C
  [3] Player D  <-- Pair with C
  [4] Player E
  [5] Player F  <-- Pair with E
  [6] Player G  <-- Unpaired (odd number)
```

**If odd number of players**: Last player doesn't get matched this round.

**Advantages**:
- Locally optimized (adjacent players in permuted list have similar adjusted ratings)
- Simple and deterministic
- Naturally avoids very unbalanced matches

---

## Elo Range Calculation

### Detailed Range Calculation Process

The RANGE controls how much randomness is introduced (cgos.py:1817-1863):

```
Step 1: Initial RANGE
  RANGE = 500.0  (hardcoded minimum)

Step 2: Collect waiting players
  lst = [(name, rating), ...] sorted by rating descending
  
Step 3: Calculate max gap (accounts for SKIP players)
  For each position i from 0 to (ll - SKIP):
    gap[i] = lst[i].rating - lst[i + SKIP].rating
  max_gap = max(gap[i])

Step 4: Apply safety margin
  max_gap *= 1.50

Step 5: Update RANGE
  if max_gap > RANGE:
    RANGE = max_gap
```

### Why Skip 4 Players?

The SKIP constant of 4 ensures:
- The range is large enough to bridge gaps in the player population
- If there's a cluster of 4 strong players, then a gap, we still match across it
- Very few players ever get left unmatched

**Real-world example** (assuming 10 players):
```
Positions:     Rating
0 (strongest)  2200
1              2150
2              2100
3              2050
4              1800  <-- Large gap!
5              1750
6              1700
7              1650
8              1600
9 (weakest)    1200

SKIP = 4 analysis:
  Position 0: gap to pos 4 = 2200 - 1800 = 400
  Position 1: gap to pos 5 = 2150 - 1750 = 400
  Position 2: gap to pos 6 = 2100 - 1700 = 400
  Position 3: gap to pos 7 = 2050 - 1650 = 400
  Position 4: gap to pos 8 = 1800 - 1600 = 200
  Position 5: gap to pos 9 = 1750 - 1200 = 550  <-- Max

max_interval = 550 * 1.50 = 825

Result: RANGE = 825 is large enough that random perturbation can
connect the cluster (2200-2050) with the rest (1800-1200)
```

### Range-Based Randomization

Once RANGE is determined, each player's perceived rating becomes:

```
adjusted_rating = actual_rating + RANGE * random(0.0, 1.0)
```

This creates a probability distribution where:
- Very small RANGE: strict rating-based matching only
- Very large RANGE: almost random matching
- RANGE = gap_size: bridges the weakest players back into matches

---

## Pairing Strategy

### High-Level Pairing Algorithm

```
INPUTS:
  - List of waiting players with actual ratings
  - Calculated RANGE for this round
  
PROCESS:
  1. Sort players by actual rating (descending)
  2. Perturb each rating: rating + RANGE * random()
  3. Re-sort by perturbed rating (descending)
  4. Take adjacent pairs from sorted list
  5. Apply constraints (anchor check, match history, color swap)
  6. Initialize game with pair
  
OUTPUTS:
  - Games created with matched players
```

### Why This Works

**Locally Optimal Matching**:
- Adjacent players in perturbation-sorted list have similar adjusted strength
- Matches are relatively balanced
- Not searching for globally optimal matching (NP-hard problem)

**Variety**:
- Random perturbation ensures different matches each round
- No player gets stuck in a rut with the same opponents
- Over many rounds, each player faces diverse opposition

**Scalability**:
- O(n log n) complexity due to sorting
- Can handle 1000s of concurrent players
- Single linear pass to create pairs

### Color Assignment (White vs Black)

Once a pair is created, the system decides who plays white (cgos.py:1912-1913):

```python
# Count previous games between these players
wco = db.execute(
    "SELECT count(*) FROM games WHERE w==? AND b==?", (wp, bp)
).fetchone()[0]
bco = db.execute(
    "SELECT count(*) FROM games WHERE w==? AND b==?", (bp, wp)
).fetchone()[0]

# Swap white and black if black has not been played as many times
if bco < wco:
    bp, wp = wp, bp
```

**Strategy**: 
- Count how many times WP has played as white against BP
- Count how many times BP has played as white against WP
- Assign white to the player who has played white less often

**Example**:
```
Players: Alice (strong) vs Bob (weak)
History: Alice white vs Bob black: 5 games
         Bob white vs Alice black: 2 games

Decision: Swap so Bob plays white (plays white less often)
          This gives Bob better chances as white (first move advantage)
```

**This balances**:
- Color advantage (white has small first-move advantage in Go)
- Player experience (both get to play white frequently)
- Rating changes (if white plays weak, weak player gets more rating swings)

---

## Match History Constraints

### Preventing Same-Player Rematches

The system avoids matching the same pair too frequently by selecting from adjacent players in the randomized list:

```python
# After perturbation and sorting:
lst = [(Player1, adj_rating1), (Player2, adj_rating2), ...]

# Take pairs of adjacent entries
# This naturally creates diversity because:
# - The permutation changes every round
# - Even if two players are similar strength,
#   their positions in the new sorted order vary
```

**Example Scenario**:
```
Round 1 after perturbation-sort:
  [0] AlphaGo (2100)
  [1] Leela   (2080)
  [2] GnuGo   (2000)
  [3] Pachi   (1950)

Matches: AlphaGo vs Leela, GnuGo vs Pachi

Round 2 after new perturbation-sort:
  [0] Pachi   (2100)  <- different due to random perturbation
  [1] GnuGo   (2080)
  [2] AlphaGo (2000)
  [3] Leela   (1950)

Matches: Pachi vs GnuGo, AlphaGo vs Leela

Different matchups even with same players!
```

### Explicit Match History Check

For critical decisions (like anchor matching), explicit database queries are used:

```python
wco = db.execute(
    "SELECT count(*) FROM games WHERE w==? AND b==?", (wp, bp)
).fetchone()[0]
```

This allows:
- Counting total games between any pair
- Implementing future constraints if needed
- Auditing match fairness

---

## Anchor Player Handling

### What is an Anchor?

Anchor players are reference engines with fixed ratings. They help calibrate the rating scale.

**Characteristics**:
- Rating is locked (doesn't change)
- K-factor is locked to minimum
- Provide consistent calibration point
- Used to benchmark other engines

### Anchor Matching Rules

Anchor vs Anchor matches are controlled by `anchor_match_rate` (cgos.py:1897-1902):

```python
# delete anchor vs anchor
if aa in anchors and bb in anchors:
    r = random.random()
    if r > cfg.anchor_match_rate:
        logger.info(f"delete this match. {wp}, {bp}, r={r}")
        continue
```

**Decision Logic**:
1. Check if both players in the pair are anchors
2. Generate random number 0.0-1.0
3. If random > anchor_match_rate: skip this match (don't create game)
4. Otherwise: create the game

**Configuration** (default in cgos19.yaml):
```yaml
anchor_match_rate: 0.10  # 10% of anchor vs anchor matches are allowed
```

**Example**:
```
Configuration: anchor_match_rate = 0.10

Pair: GnuGo (anchor) vs Leela (anchor)
Random draw: 0.35
Decision: 0.35 > 0.10? YES → skip this match (don't create game)

Pair: GnuGo (anchor) vs Pachi (regular)
Random draw: 0.88
Decision: 0.88 > 0.10? YES → skip (but this is never checked 
because only one is anchor)

Actually, the check only applies when BOTH are anchors:
Pair: GnuGo (anchor) vs AlphaGo (anchor)
Random draw: 0.05
Decision: 0.05 > 0.10? NO → allow this match (10% success rate)
```

**Why This Matters**:
- Anchor vs Anchor doesn't calibrate anything (both are fixed)
- Regular vs Anchor is useful (rates the regular player)
- Too many Anchor vs Anchor wastes pairings
- 10% allow rate gives occasional anchor-anchor matches for consistency

---

## Game Initialization

### init_game() Function Signature

Once a pair is selected, `init_game()` is called to create the game (cgos.py:1729-1787):

```python
def init_game(
    ctme: datetime.datetime,
    wp: str,                          # White player
    bp: str,                          # Black player
    white_remaining_time: Optional[int] = None,
    black_remaining_time: Optional[int] = None,
    moves: Optional[List[Tuple[str, int, Optional[str]]]] = None,
) -> int:
```

### Game Initialization Steps

**Step 1: Allocate Game ID**
```python
gid = db.execute("SELECT gid FROM gameid WHERE ROWID=1").fetchone()[0]
db.execute("UPDATE gameid set gid=gid+1 WHERE ROWID=1")
```

**Step 2: Create Go Board**
```python
rule = Rule(cfg.koRule)
gme[gid] = GoGame(cfg.boardsize, rule)
```

**Step 3: Replay Catch-up Moves** (if resuming game)
```python
for mv, _, _ in moves:
    err = gme[gid].make(mv)
    if err < 0:
        logger.error(f"Bad game move {gid} {ERR_MSG[err*-1]}")
        return 0
```

**Step 4: Get Current Ratings**
```python
wr = ratingOf[wp]  # White rating display string
br = ratingOf[bp]  # Black rating display string
```

**Step 5: Create Game Object**
```python
game = Game(
    wp,                         # White player name
    bp,                         # Black player name
    0,                          # last_move_start_time
    white_remaining_time or cfg.level,  # Initial white time
    black_remaining_time or cfg.level,  # Initial black time
    wr,                         # White rating string (e.g., "1850?")
    br,                         # Black rating string (e.g., "1900")
    moves or [],                # Move list
    ctme                        # Game creation time
)
games[gid] = game
```

**Step 6: Update Player State**
```python
act[wp].gid = gid
act[wp].msg_state = "ok"    # Waiting for setup confirmation
act[bp].gid = gid
act[bp].msg_state = "ok"
```

**Step 7: Send Setup Message to Players**
```python
msg_out = f"setup {gid} {cfg.boardsize} {cfg.komi} {cfg.level} {wp}({wr}) {bp}({br})"
if len(game.moves) > 0:
    msg_out += f" {joinMoves(game.moves)}"  # Catch-up moves
    
nsend(wp, msg_out)
nsend(bp, msg_out)

logger.info(msg_out)
```

**Example Setup Message**:
```
setup 123 19 7.5 1200000 GnuGo(1850) Leela(1900?)
```

**Step 8: Notify Viewers**
```python
vmsg = f"match {gid} - - {cfg.boardsize} {cfg.komi} {wp}({wr}) {bp}({br}) -"
viewers.sendAll(vmsg)
```

**Step 9: Return Game ID**
```python
return gid
```

### Game Start Delay

After all games in a round are initialized, there's a 3-second delay before starting (cgos.py:1919-1922):

```python
# add a 3 second delay to let all programs complete setup.
time.sleep(3000 / 1000)  # 3 seconds
```

**Purpose**: Give all clients time to process setup messages and initialize their engines.

### Game Clock Start

After the delay, games are started with `start_game()` (cgos.py:1927-1935):

```python
for gid, rec in games.items():
    logger.info(
        f"match-> {rec.w}({ rating(rec.w) })   {rec.b}({ rating(rec.b) })"
    )
    start_game(rec)
```

`start_game()` determines whose turn it is and sends the first `genmove` request (cgos.py:1790-1807):

```python
def start_game(game: Game) -> None:
    ct = now_milliseconds()
    game.last_move_start_time = ct
    
    ply = len(game.moves)
    if ply & 1:  # Odd number of moves (black's turn)
        ctm = game.w  # White just moved
        c = "w"
        tl = game.white_remaining_time - (ct - game.last_move_start_time)
    else:  # Even number of moves (white's turn)
        ctm = game.b  # Black just moved
        c = "b"
        tl = game.black_remaining_time - (ct - game.last_move_start_time)
    
    nsend(ctm, f"genmove {c} {tl}")
    act[ctm].msg_state = "genmove"
```

---

## Configuration Parameters

### Matching-Related Configuration

**File**: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/configs/generic/cgos19.yaml`

```yaml
# anchor_match_rate: Probability of allowing anchor vs anchor matches
# type: float, optional (default: 0.10)
# range: 0.0-1.0 (0% to 100%)
anchor_match_rate: 0.10

# matchMode: Determines who matches players
# type: str, optional (default: "AUTO")
# possible values: "AUTO", "ADMIN"
#   AUTO: Server automatically matches waiting players
#   ADMIN: Administrator manually matches players (future feature)
matchMode: "AUTO"
```

### Game Configuration

```yaml
# level: Time limit per player, in seconds
# type: int, required
level: 1200  # 20 minutes

# timeGift: Fischer timing increment, in seconds
# type: float, required
timeGift: 0.25  # 250ms per move

# boardsize: Size of Go board for all games
# type: int, required
boardsize: 19

# komi: Compensation for black
# type: float, required
komi: 7.0
```

### Schedule Timing

Hard-coded in cgos.py:
```python
schedule_games_interval = 15.0  # Check every 15 seconds
SKIP = 4                        # Gap for range calculation
```

---

## Example Matching Scenarios

### Scenario 1: Simple Even Match

**Setup**:
```
Players waiting:
  GnuGo:    1800.0
  Leela:    1750.0
  Pachi:    1700.0
  AlphaGo:  1650.0

Configuration:
  anchor_match_rate: 0.10
  matchMode: AUTO
  SKIP: 4
  Level: 1200 seconds
```

**Step 1: Collect Waiting Players**
```
lst = [(GnuGo, 1800), (Leela, 1750), (Pachi, 1700), (AlphaGo, 1650)]
r_sum = 7000
ll = 4
```

**Step 2: Calculate RANGE**
```
e = 4 - 4 = 0
Since e <= 0:
  max_interval = 2000.0
  
max_interval *= 1.50 = 3000.0
RANGE = 3000.0 (or keep at 500 if 500 > 3000, which is false)
So RANGE = 3000.0
```

Actually, let me recalculate more carefully:
```
Initial RANGE = 500.0
e = ll - SKIP = 4 - 4 = 0

The loop:
  for i in range(e):  # range(0) = empty range
  
No iterations, so max_interval stays 0.0

Since e <= 0:
  max_interval = 2000.0
  
max_interval *= 1.50 = 3000.0

if 3000.0 > 500.0:
  RANGE = 3000.0
```

**Step 3: Randomize**
```
GnuGo:    1800 + 3000 * 0.35 = 2850
Leela:    1750 + 3000 * 0.82 = 3210
Pachi:    1700 + 3000 * 0.12 = 1960
AlphaGo:  1650 + 3000 * 0.67 = 3660

Sorted by perturbed rating:
  AlphaGo:  3660
  Leela:    3210
  GnuGo:    2850
  Pachi:    1960
```

**Step 4: Create Pairs**
```
Pairs: (AlphaGo, Leela), (GnuGo, Pachi)
```

**Step 5: Check Match History**
```
AlphaGo vs Leela:
  wco = count(w=AlphaGo, b=Leela) = 0
  bco = count(w=Leela, b=AlphaGo) = 0
  Equal, so no swap needed

GnuGo vs Pachi:
  wco = count(w=GnuGo, b=Pachi) = 0
  bco = count(w=Pachi, b=GnuGo) = 0
  Equal, so no swap needed
```

**Step 6: Check Anchors**
```
Neither pair has both players as anchors, so no anchor check needed
```

**Step 7: Create Games**
```
Game 1: AlphaGo (white) vs Leela (black)
Game 2: GnuGo (white) vs Pachi (black)
```

**Result**:
```
Games scheduled:
  GID 1: AlphaGo(1800?) vs Leela(1750?)  [1800 vs 1750]
  GID 2: GnuGo(1800?) vs Pachi(1700?)    [1800 vs 1700]

Despite similar actual ratings, the random perturbation caused:
- AlphaGo (actual 1650) to play Leela (actual 1750)
- GnuGo (actual 1800) to play Pachi (actual 1650)
```

### Scenario 2: Anchor Matching Prevention

**Setup**:
```
Players waiting:
  GnuGo_anchor:    1700.0 (is anchor)
  Leela_anchor:    1800.0 (is anchor)
  Pachi_regular:   1750.0

anchors = {"GnuGo_anchor": 1700, "Leela_anchor": 1800}
anchor_match_rate = 0.10
```

**Step 1-3: Collect and Randomize**
```
After perturbation sort (hypothetical):
  Leela_anchor:     2100
  Pachi_regular:    1900
  GnuGo_anchor:     1600
```

**Step 4: Create Pairs**
```
Pairs: (Leela_anchor, Pachi_regular), (GnuGo_anchor, [unpaired])
```

**Result**:
```
Game 1: Leela_anchor vs Pachi_regular (allowed, only one anchor)
GnuGo_anchor remains unpaired this round
```

**Alternative Scenario** (different random perturbation):
```
After perturbation sort (different example):
  GnuGo_anchor:     2200
  Leela_anchor:     2100
  Pachi_regular:    1900

Pairs: (GnuGo_anchor, Leela_anchor), (Pachi_regular, [unpaired])

Check anchor rule:
  Both GnuGo_anchor and Leela_anchor are in anchors
  Random draw: 0.15
  Is 0.15 > 0.10? YES
  Decision: SKIP this match
  
Result: No game created, Pachi also doesn't play this round
```

If random draw had been 0.05 instead:
```
Is 0.05 > 0.10? NO
Decision: CREATE game (10% of attempts succeed)

Game: GnuGo_anchor (white) vs Leela_anchor (black)
```

### Scenario 3: Match History Balancing

**Setup**:
```
Players waiting:
  Strong:  2000.0
  Medium:  1900.0

Previous games:
  Strong vs Medium:       5 times (Strong was white 5 times)
  Medium vs Strong:       3 times (Medium was white 3 times)
```

**Step 1-3: Matching Process**
```
After perturbation and pairing:
  Pair: (Strong, Medium)
```

**Step 4: Check Match History**
```
wco = count(w=Strong, b=Medium) = 5
bco = count(w=Medium, b=Strong) = 3

Is bco < wco?  (3 < 5)? YES
Decision: Swap white and black

wp, bp = bp, wp  (Medium becomes white, Strong becomes black)
```

**Step 5: Create Game**
```
Game: Medium (white) vs Strong (black)

Effect: Medium gets to play white more often,
        balancing the color advantage over time
```

### Scenario 4: Large Player Pool with Diverse Ratings

**Setup**:
```
Players waiting (10 total):
  1: GnuGo      2000
  2: Leela      1950
  3: AlphaGo    1900
  4: Pachi      1850
  5: NewBot1    1800
  6: NewBot2    1700
  7: NewBot3    1600
  8: Weak1      1300
  9: Weak2      1250
  10: VeryWeak  1200

Configuration:
  SKIP = 4
  anchor_match_rate = 0.10
```

**Step 1: Collect**
```
lst sorted by actual rating (descending):
  GnuGo(2000), Leela(1950), AlphaGo(1900), Pachi(1850),
  NewBot1(1800), NewBot2(1700), NewBot3(1600), Weak1(1300),
  Weak2(1250), VeryWeak(1200)
```

**Step 2: Calculate RANGE**
```
ll = 10, e = 10 - 4 = 6

Gaps examined:
  i=0: pos0(2000) - pos4(1800) = 200
  i=1: pos1(1950) - pos5(1700) = 250
  i=2: pos2(1900) - pos6(1600) = 300
  i=3: pos3(1850) - pos7(1300) = 550
  i=4: pos4(1800) - pos8(1250) = 550 (max!)
  i=5: pos5(1700) - pos9(1200) = 500

max_interval = 550 * 1.50 = 825
RANGE = 825
```

**Step 3: Randomize**
```
GnuGo:      2000 + 825*0.10 = 2082.5
Leela:      1950 + 825*0.85 = 2650.0
AlphaGo:    1900 + 825*0.30 = 2147.5
Pachi:      1850 + 825*0.95 = 2633.75
NewBot1:    1800 + 825*0.20 = 1965.0
NewBot2:    1700 + 825*0.70 = 2277.5
NewBot3:    1600 + 825*0.02 = 1616.5
Weak1:      1300 + 825*0.80 = 1960.0
Weak2:      1250 + 825*0.50 = 1662.5
VeryWeak:   1200 + 825*0.45 = 1571.25

Sorted by perturbed rating:
  Leela:      2650.0
  Pachi:      2633.75
  NewBot2:    2277.5
  AlphaGo:    2147.5
  GnuGo:      2082.5
  NewBot1:    1965.0
  Weak1:      1960.0
  Weak2:      1662.5
  NewBot3:    1616.5
  VeryWeak:   1571.25
```

**Step 4: Create Pairs**
```
Pairs:
  (Leela, Pachi)
  (NewBot2, AlphaGo)
  (GnuGo, NewBot1)
  (Weak1, Weak2)
  (NewBot3, VeryWeak) -- actually wait, only 10 players
  
Let me recount:
  0: Leela
  1: Pachi      (pair with Leela)
  2: NewBot2
  3: AlphaGo    (pair with NewBot2)
  4: GnuGo
  5: NewBot1    (pair with GnuGo)
  6: Weak1
  7: Weak2      (pair with Weak1)
  8: NewBot3
  9: VeryWeak   (pair with NewBot3)

All 10 players get matched!

Result:
  Leela(1950) vs Pachi(1850)
  NewBot2(1700) vs AlphaGo(1900)
  GnuGo(2000) vs NewBot1(1800)
  Weak1(1300) vs Weak2(1250)
  NewBot3(1600) vs VeryWeak(1200)

Despite having weak players, they all get games thanks to large RANGE!
```

---

## Source Code Reference

### Core Matching Functions

**File**: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/app/cgos.py`

| Function | Line | Purpose |
|---|---|---|
| `schedule_games()` | 1534 | Main scheduling loop (called every ~15s) |
| `match_games()` | 1810 | Calculate RANGE and create pairs |
| `init_game()` | 1729 | Initialize a game with two players |
| `start_game()` | 1790 | Start clock and send first genmove |
| `getAnchors()` | 310 | Load anchor definitions from database |

### Async Scheduler

```python
async def schedule_games_task() -> None:  # Line 1938
    """Runs schedule_games() every 15 seconds"""
```

### Key Constants

**cgos.py:**
```python
SKIP = 4                        # Line 41
schedule_games_interval = 15.0  # Line 63
```

### Configuration Class

**File**: `/home/hellwig/Go-Server/cgos-hg/try-ai/135246/server/cgos/app/config.py`

```python
class Configs:
    anchor_match_rate: float      # Line 51
    matchMode: MatchMode          # Line 55
    level: int                    # Line 32 (game time in ms)
    boardsize: int                # Line 29
    komi: float                   # Line 30
```

### Database Queries

**Anchor Loading**:
```python
for nme, rat in db.execute("SELECT name, rating FROM anchors"):
    anchors[nme] = rat
```

**Match History**:
```python
wco = db.execute(
    "SELECT count(*) FROM games WHERE w==? AND b==?", (wp, bp)
).fetchone()[0]
```

---

## Summary

The CGOS matching system implements a **sophisticated yet efficient** pairing algorithm:

### Key Design Decisions

1. **Round-Based Scheduling**: All games start and finish together
2. **Rating-Aware Matching**: Players face opponents of similar strength
3. **Randomized Perturbation**: Prevents deterministic pairings, adds variety
4. **Dynamic Range Calculation**: Adapts to player population
5. **Match History Balancing**: Fair color distribution
6. **Anchor Control**: Prevents wasteful anchor-vs-anchor games

### Algorithm Strengths

- **Fair**: Similar-strength players face each other
- **Varied**: Random perturbation ensures diversity
- **Inclusive**: Large RANGE includes weak players
- **Efficient**: O(n log n) complexity scales well
- **Configurable**: RANGE and anchor parameters adjust behavior

### Mathematical Foundation

- **SKIP-based range calculation**: Bridges population gaps
- **Perturbation randomization**: Converts rating order to stochastic matching
- **Adjacent pair selection**: Locally optimal from randomized order
- **Match history query**: Ensures color fairness

This design has proven effective for competitive Go engine rating across diverse player populations and rating distributions.
