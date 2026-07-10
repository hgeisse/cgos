# Quick Start: Anchor Players File Update

## TL;DR

**To update anchor players while the server is running:**

```bash
# 1. Create or edit the "anchors" file in the working directory
cat > anchors << 'EOF'
AlphaGo 3400
Leela 3350
KataGo 3300
EOF

# 2. Create the trigger file (signals server to update)
touch set_anchor_players

# 3. Wait for server to process (15 seconds or less)
# The trigger file will be deleted automatically
```

That's it! The server will automatically:
- Detect the trigger file
- Wait for a safe moment (no games in progress)
- Read and validate the anchor file
- Update the database
- Delete the trigger file

## File Locations

Both files must be in the server's **working directory** (same location as `wdata.txt`):

- **Anchor data file:** `anchors` (or configured name)
- **Trigger file:** `set_anchor_players` (or configured name)

## Anchor File Format

```
# Comments start with # (line start only)
PlayerName 1234

# One player per line: name rating (space-separated)
AlphaGo 3400
Leela 3350

# Empty lines are ignored
KataGo 3300

# Ratings must be integers
Fuego 2800
```

**Rules:**
- One player per line
- Format: `name rating` (space-separated)
- Rating must be an integer (Elo points)
- Comments start with `#` at line start
- Empty lines ignored
- **No duplicate names allowed**
- Empty file is valid (results in zero anchor players)

## Error Handling

If something goes wrong, **the trigger file is preserved** so you can fix and retry.

**Common errors and fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `expected 2 tokens, got X` | Too many/few columns | Fix the line (name + rating only) |
| `invalid rating (not an integer)` | Non-numeric rating | Use only integer values |
| `Duplicate anchor player name` | Player listed twice | Remove duplicate line |
| Trigger file not deleted | Database error | Check server logs for details |

## Verification

### Check Server Logs

```
INFO: Updated anchor players from /path/to/anchors
```

### Check Database

```bash
sqlite3 database_state_file.db "SELECT * FROM anchors;"
```

## Examples

### Example 1: Simple Update

**Create anchors file:**
```
Leela 3200
Fuego 2800
```

**Trigger update:**
```bash
touch set_anchor_players
```

**Result:** These 2 players become anchors. Any previous anchors are removed.

---

### Example 2: Clear All Anchors

**Create empty anchors file:**
```bash
touch anchors
```

**Trigger update:**
```bash
touch set_anchor_players
```

**Result:** All anchor players are removed.

---

### Example 3: From Script

```bash
#!/bin/bash
# Update anchors from CSV file

# Parse CSV and create anchors file
awk -F',' '{print $1 " " $2}' player_ratings.csv > anchors

# Trigger update
touch set_anchor_players

# Wait and verify
sleep 2
if [ ! -f set_anchor_players ]; then
    echo "✓ Update successful"
else
    echo "✗ Update failed - check server logs"
fi
```

## Configuration

Optional: Customize file names in your YAML config:

```yaml
anchor_players_trigger_file: "update_anchors_now"
anchor_players_data_file: "anchor_list.txt"
anchor_check_enabled: true
```

Default configuration (no YAML entry needed):
- Trigger file: `set_anchor_players`
- Data file: `anchors`
- Feature enabled: `true`

## Troubleshooting

### Trigger file not deleted but no error log

1. Wait 15+ seconds (tied to game scheduling cycle)
2. Verify no games are running
3. Check that anchors file exists in working directory
4. Check file permissions (must be readable)

### Trigger file deleted but anchors not updated

1. Check server logs for errors
2. Verify anchors file format is correct
3. Check for duplicate player names
4. Verify database has write access

### Feature seems disabled

1. Check YAML config for `anchor_check_enabled: false`
2. Check server logs for "anchor" messages
3. Verify trigger file name matches config

## When Updates Happen

Updates are checked:
- **Frequency:** Every ~15 seconds (when scheduling games)
- **Condition:** Only when no games are in progress
- **Context:** Same safe window as killfile handling
- **Guarantee:** No games will be interrupted

## Backward Compatibility

The old `set_anchors.py` tool is deprecated but still works:

```bash
# Old way (deprecated):
python cgos/set_anchors.py anchors database_state_file.db

# New way (recommended):
touch set_anchor_players
```

---

**For complete documentation, see:** `ANCHOR_PLAYERS_UPDATE.md`
