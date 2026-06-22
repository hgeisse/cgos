# Testing the Graceful Shutdown Fix

## Quick Test

### Terminal 1: Run the server
```bash
cd /home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server
python3 -m cgos.app.cgos configs/cgos.yaml
```

Wait for the server to start. You should see:
```
INFO - cgos_server - "CGOS Server" up and running at ... GMT
INFO - cgos_server - Serving on 0.0.0.0:6119
```

### Terminal 2: Trigger shutdown after 30 seconds
```bash
sleep 30
touch killfiles/kill_cgos9
```

### Expected Output in Terminal 1

The server logs should show this sequence:
1. Regular operation (Games in progress messages)
2. After ~15 seconds when next schedule cycle runs:
   ```
   INFO - cgos_server - KILL FILE FOUND - EXIT CGOS
   INFO - cgos_server - Shutdown requested in schedule_games_task, exiting gracefully
   INFO - cgos_server - Server closing due to shutdown signal
   INFO - cgos_server - Shutting down server_main, cancelling schedule_games_task
   INFO - cgos_server - schedule_games_task cancelled successfully
   INFO - cgos_server - Server shutdown completed successfully
   ```
3. Process exits with code 0

### What Should NOT Appear

- `asyncio - Error - Task exception was never retrieved`
- `Traceback` (unless there's an actual error)
- Hanging process (process should exit within seconds)

## Detailed Verification

### Check 1: Process Terminates
```bash
# In Terminal 1, after kill file is created
# Process should exit within 15-20 seconds
# Verify with:
echo $?  # Should print 0 (success exit code)
```

### Check 2: Proper Log Sequence
Run with file logging enabled and check:
```bash
tail -f logs/cgos.log | grep -E "KILL FILE|Shutdown|Server closing|completed"
```

Expected sequence in logs:
```
KILL FILE FOUND - EXIT CGOS
Shutdown requested in schedule_games_task, exiting gracefully
Server closing due to shutdown signal
Shutting down server_main, cancelling schedule_games_task
schedule_games_task cancelled successfully
Server shutdown completed successfully
```

### Check 3: No Asyncio Errors
```bash
grep -E "Task exception|CancelledError" logs/cgos.log
# Should return nothing (or only the debug message about successful cancellation)
```

### Check 4: Network Port Released
```bash
# Immediately after shutdown, try to restart server in same port
python3 -m cgos.app.cgos configs/cgos.yaml
# Should bind successfully (port not in TIME_WAIT)
```

## Multi-Instance Test

If running multiple server instances with different kill files:

```bash
# Terminal 1
python3 -m cgos.app.cgos configs/cgos_1.yaml  # uses killfiles/kill_cgos1

# Terminal 2  
python3 -m cgos.app.cgos configs/cgos_2.yaml  # uses killfiles/kill_cgos2

# Terminal 3 - Shutdown only instance 1
touch killfiles/kill_cgos1

# Verify:
# - Server 1 shuts down cleanly
# - Server 2 continues running
```

## Edge Cases to Test

### Test 1: Kill file during active games
```bash
# Run server
# Connect with client and start a game
# While game is running, touch kill file
# Expected: Game continues, new games not scheduled,
#           server shuts down after current scheduling cycle
```

### Test 2: Rapid shutdown
```bash
# Run server
# Immediately (within 45 seconds) touch kill file
# Expected: Server detects kill file on first scheduling opportunity
#           and shuts down gracefully
```

### Test 3: Kill file already exists on startup
```bash
# Create kill file
touch killfiles/kill_cgos9
# Run server
python3 -m cgos.app.cgos configs/cgos.yaml
# Expected: Server removes existing kill file on startup,
#           starts normally
```

## Performance Metrics

### Shutdown Time
- **Kill file detection**: Up to 15 seconds (next scheduling cycle)
- **Server closure**: Should be instant (~1 second)
- **Total shutdown time**: 1-16 seconds from kill file creation

### Memory/Resource Cleanup
```bash
# Before shutdown
ps aux | grep cgos

# During shutdown (watch resources)
watch -n 1 'ps aux | grep cgos'

# After shutdown
ps aux | grep cgos
# Should show no server process
```

## Success Criteria

✓ Process exits within 20 seconds of kill file creation
✓ Exit code is 0 (success)
✓ No "Task exception was never retrieved" errors
✓ Log shows complete shutdown sequence
✓ Network port is released immediately
✓ No zombie processes left behind
✓ All databases properly closed (no file locks)

## Troubleshooting

### Problem: Process doesn't exit
- Check if kill file path is correct (matches cfg.killFileSrv)
- Verify server is running (check logs)
- Check if there are long-running operations blocking schedule_games()
- Look for infinite loops in external code being called

### Problem: "Task exception was never retrieved"
- This should NOT appear with the new code
- If it does, check that schedule_games_task is catching ShutdownRequested
- Verify shutdown_event is being set

### Problem: Databases locked after shutdown
- This shouldn't happen - databases are committed and closed
- Verify db.close() is being called before ShutdownRequested is raised
- Check for other connections to the database files

## Related Files
- Main code: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/cgos.py`
- Configuration: Check `killFileSrv` parameter in YAML config
- Kill files: `killfiles/kill_cgos*` (per-instance shutdown files)
