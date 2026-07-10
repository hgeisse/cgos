# Anchor Players File-Based Update Mechanism

## Overview

The CGOS server now supports automatic anchor player updates using a file-based trigger mechanism. This eliminates the need for manual database manipulation and provides a safe, automated way to update anchor players during server operation.

## How It Works

The server monitors for a trigger file named `set_anchor_players` (configurable). When this file is created:

1. The server detects the trigger file at the next "safe" moment
2. "Safe" means: **no games are currently in progress**
3. The server reads anchor player definitions from the `anchors` file
4. The database is updated with the new anchor players (atomic transaction)
5. The trigger file is automatically deleted on success

## Safety Guarantees

- **Atomic database transactions**: All-or-nothing updates
- **No games in progress**: Updates only occur when count == 0
- **Integrated into game scheduling cycle**: Checked every ~15 seconds (tied to `schedule_games_interval`)
- **Comprehensive error handling**: Parse errors, duplicates, missing files all logged clearly
- **No partial updates**: Database remains unchanged if any error occurs

## Configuration

Add these optional parameters to your CGOS YAML configuration file:

```yaml
# Anchor player file-based update mechanism
anchor_players_trigger_file: "set_anchor_players"    # Trigger file name (default)
anchor_players_data_file: "anchors"                  # Anchor data file name (default)
anchor_check_enabled: true                           # Enable/disable feature (default)
```

All file paths are relative to the server's working directory (same location as `wdata.txt`).

## Usage

### Step 1: Create the Anchor Data File

Create or edit the `anchors` file (or your configured data filename) with anchor player definitions:

```
# Anchor players for CGOS 19x19
# Format: name rating_in_elo

AlphaGo 3400
Leela 3350
KataGo 3300
Fuego 2800
GNU-Go 2400
```

**File Format Rules:**
- One anchor player per line
- Format: `name rating` (space-separated)
- `name`: player name (string)
- `rating`: Elo rating (integer)
- Lines starting with `#` are comments (only at line start)
- Empty lines are ignored
- **No duplicate player names allowed**

### Step 2: Create the Trigger File

Create an empty file named `set_anchor_players` (or your configured trigger filename):

```bash
touch set_anchor_players
```

### Step 3: Wait for Update

The server will automatically:
- Detect the trigger file
- Wait for a safe moment (no games in progress)
- Read and parse the `anchors` file
- Update the database
- Delete the trigger file

### Step 4: Verify Update

Check the server logs for confirmation:

```
INFO: Updated anchor players from /path/to/anchors
```

## Error Handling

If any error occurs, the trigger file is **left intact** so you can retry. The database is not modified. Possible errors:

| Error | Cause | Action |
|-------|-------|--------|
| `Anchor data file not found` | Missing `anchors` file | Create the file and retry |
| `expected 2 tokens, got X` | Invalid line format | Fix the line in `anchors` file |
| `invalid rating (not an integer)` | Non-integer rating | Use integer values only |
| `Duplicate anchor player name` | Player listed twice | Remove duplicate and retry |
| `Games in progress` | Can't update while games running | Server will retry automatically |

## Examples

### Example 1: Update to New Anchor Set

**Create `anchors` file:**
```
KataGo 3300
Leela 3250
AlphaGo 3200
```

**Create trigger file:**
```bash
touch set_anchor_players
```

**Result:** All three players become anchors. Previous anchors are removed.

### Example 2: Clear All Anchors

**Create empty `anchors` file:**
```bash
touch anchors
# (empty file)
```

**Create trigger file:**
```bash
touch set_anchor_players
```

**Result:** All anchor players are removed. No anchors are active.

### Example 3: Configuration Override

**In YAML config:**
```yaml
anchor_players_trigger_file: "update_anchors_now"
anchor_players_data_file: "anchor_list.txt"
anchor_check_enabled: true
```

Then use `update_anchors_now` as trigger file and `anchor_list.txt` as data file.

## Deprecated: set_anchors.py

The standalone `set_anchors.py` tool is **deprecated** in favor of this file-based mechanism. However, it remains functional for backward compatibility.

If you were using `set_anchors.py`:

```bash
# Old way (deprecated):
python cgos/set_anchors.py anchors database_state_file.db

# New way (recommended):
touch set_anchor_players  # Server auto-updates from anchors file
```

## Logging

The server logs all anchor player updates with details:

```
INFO: Updated anchor players from /path/to/anchors
WARNING: Anchor data file not found: /path/to/anchors
ERROR: Error parsing anchor file at line 5: expected 2 tokens, got 3
ERROR: Duplicate anchor player name: AlphaGo
ERROR: Database error updating anchors: [error details]
WARNING: Failed to delete trigger file: [error details]
```

## Behavior Details

### Update Timing

- Checked every ~15 seconds (tied to `schedule_games_interval`)
- Only when no games are in progress
- Part of the `schedule_games()` function
- Checked before killfile detection
- Grouped with bad users file handling

### Database Consistency

- All old anchors are deleted
- New anchors are inserted
- Single atomic transaction
- On error: entire update is rolled back
- Trigger file preserved for retry

### File Operations

- Trigger file creation: user responsibility
- Anchor data file: user creates/edits
- Trigger file deletion: server deletes on success
- Both paths relative to server working directory

## Troubleshooting

### Trigger file not deleted but anchors weren't updated

1. Check server logs for error messages
2. Verify `anchors` file exists and is readable
3. Verify file format (name + space + integer rating)
4. Check for duplicate player names
5. Ensure no games are in progress

### Anchors not updated and no log message

1. Verify `anchor_check_enabled` is `true` in YAML config
2. Verify trigger file was created in correct location
3. Wait 15+ seconds for next check cycle
4. Check full server logs for errors

### File deleted but anchors not in database

1. Check database directly: `SELECT * FROM anchors;`
2. Verify rating values are valid integers
3. Check for database errors in logs
4. Verify database file has write permissions

## Technical Details

### Integration Point

The anchor player check is integrated into `cgos/app/cgos.py` in the `schedule_games()` function:

```python
# When count == 0 (no games in progress):
if cfg.anchor_check_enabled:
    update_anchors_from_file()
```

### Function Signature

```python
def update_anchors_from_file() -> bool:
    """Update anchor players from file if trigger file exists."""
```

Returns: `True` if successful, `False` if skipped or error

### Configuration Parameters

Added to `Configs` class in `cgos/app/config.py`:
- `anchor_players_trigger_file: str` (default: `"set_anchor_players"`)
- `anchor_players_data_file: str` (default: `"anchors"`)
- `anchor_check_enabled: bool` (default: `True`)
