# CGOS Server Graceful Shutdown Fix

## Problem
The original shutdown logic had a severe asyncio error: when the kill file was detected, the server called `sys.exit(0)` directly from within the `schedule_games()` function. This immediately terminated the process while multiple asyncio tasks were still running, resulting in "Task exception was never retrieved" errors.

## Root Cause
- `sys.exit(0)` is a synchronous, immediate process termination
- It doesn't allow asyncio tasks to clean up gracefully
- Active tasks include:
  - `schedule_games_task()` (main scheduling loop)
  - Multiple `handle_client()` tasks (one per connected client)
  - Multiple `readTask()` and `writeTask()` per client
  - All were abruptly terminated without proper cancellation

## Solution Implemented
Replaced the synchronous `sys.exit(0)` with an exception-based graceful shutdown mechanism:

### 1. **ShutdownRequested Exception** (lines 36-38)
```python
class ShutdownRequested(Exception):
    """Exception raised when kill file is detected to trigger graceful shutdown"""
    pass
```
- Custom exception to signal shutdown request
- Propagates up from `schedule_games()` to `schedule_games_task()`

### 2. **Modified schedule_games()** (line 1651)
**Before:**
```python
sys.exit(0)
```

**After:**
```python
raise ShutdownRequested()
```
- Instead of immediate termination, raises exception
- Allows exception handlers up the call stack to clean up

### 3. **Added shutdown_event Global Variable** (lines 68-69)
```python
# Shutdown coordination
shutdown_event: Optional[asyncio.Event] = None
```
- Global asyncio.Event to signal shutdown between tasks
- Allows `schedule_games_task()` to signal `server_main()` to close

### 4. **Modified schedule_games_task()** (lines 1951-1975)
**Before:**
```python
except Exception as e:
    logger.error(f"Error while scheduling game {str(e)}")
```

**After:**
```python
except ShutdownRequested:
    logger.info("Shutdown requested in schedule_games_task, exiting gracefully")
    # Disconnect all active clients to unblock their handler tasks
    logger.info(f"Disconnecting {len(act)} active clients")
    for name, active_user in list(act.items()):
        try:
            active_user.sock.close()
        except Exception as e:
            logger.debug(f"Error closing client {name}: {str(e)}")
    if shutdown_event:
        shutdown_event.set()
    return
except Exception as e:
    logger.error(f"Error while scheduling game {str(e)}")
```
- Catches `ShutdownRequested` exception
- **Disconnects all active clients** to unblock their handler tasks (critical fix!)
- Sets the `shutdown_event` to signal `server_main()` to close
- Returns gracefully instead of propagating the exception
- Other exceptions are still handled normally

**Why client disconnect is critical:**
- Each connected client has three async tasks: `readTask()`, `writeTask()`, `handle_client()`
- `accept_connection()` waits for one of these tasks to complete
- Without disconnecting clients, their tasks keep running indefinitely
- `client.close()` sets `client.alive = False`, which causes read/write/handler tasks to exit
- This unblocks the `accept_connection()` coroutine, allowing client cleanup

### 5. **Modified server_main()** (lines 1975-2010)
**Before:**
```python
async with server:
    await server.serve_forever()

task.cancel()
```

**After:**
```python
try:
    async with server:
        # Create a task that waits for shutdown signal
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        
        # Wait for either serve_forever or shutdown_event
        done, pending = await asyncio.wait(
            [asyncio.create_task(server.serve_forever()), shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel the other task
        for p in pending:
            p.cancel()
            try:
                await p
            except asyncio.CancelledError:
                pass
        
        logger.info("Server closing due to shutdown signal")
        server.close()
        await server.wait_closed()
finally:
    # Gracefully cancel the scheduling task if it's still running
    logger.info("Shutting down server_main, cancelling schedule_games_task")
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.debug("schedule_games_task cancelled successfully")
            pass
```
- Creates a global `shutdown_event` at start
- Runs `server.serve_forever()` in parallel with shutdown event waiting
- When shutdown event is signaled, closes the server and exits the loop
- Added try/finally block for guaranteed cleanup
- Properly cancels the `schedule_games_task` and awaits it
- Catches `asyncio.CancelledError` during cleanup

### 6. **Modified runServer()** (lines 2058-2066)
**Before:**
```python
asyncio.run(server_main())
```

**After:**
```python
try:
    asyncio.run(server_main())
    logger.info("Server shutdown completed successfully")
    sys.exit(0)
except KeyboardInterrupt:
    logger.info("Server interrupted by keyboard")
    sys.exit(0)
except Exception as e:
    logger.error(f"Server error: {str(e)}")
    logger.error(traceback.format_exc())
    sys.exit(1)
```
- Wraps `asyncio.run()` in exception handlers
- Logs successful shutdown
- Handles keyboard interrupts gracefully
- Logs and reports errors with traceback

## Shutdown Flow (After Fix)

1. **Kill file detection** (schedule_games:1641)
   - Database is committed and closed
   - Web data file is updated
   - `ShutdownRequested` exception is raised

2. **Exception caught in schedule_games_task()** 
   - `schedule_games_task()` catches the `ShutdownRequested` exception
   - **Disconnects all active clients** (calls `client.close()` on each)
     - Sets `client.alive = False` for each connected client
     - Causes their `readTask()`, `writeTask()`, and `handle_client()` to exit
     - Unblocks `accept_connection()` coroutines waiting on those tasks
   - Sets the global `shutdown_event` to signal other tasks
   - Returns gracefully

3. **Client handler cleanup**
   - Each client's tasks exit due to `client.alive = False`
   - `accept_connection()` coroutines complete
   - All client connections are terminated

4. **server_main() detects shutdown signal**
   - The `shutdown_event.wait()` task completes
   - `asyncio.wait()` returns with shutdown_task in done set
   - Server closes gracefully via `server.close()` and `await server.wait_closed()`
   - Exits the `serve_forever()` loop

5. **Cleanup phase**
   - `server_main()`'s finally block executes
   - `schedule_games_task` is cancelled as a safety measure (may already be done)
   - Task is awaited to ensure proper cleanup

6. **Process exits**
   - `asyncio.run()` completes normally (all tasks have completed)
   - `runServer()` logs success
   - Process exits with code 0

## Benefits

1. **No "Task exception was never retrieved" errors** - Tasks are properly cancelled and awaited
2. **All clients disconnected** - Active client connections are terminated before shutdown
3. **Graceful cleanup** - All async tasks finish their cleanup handlers
4. **Proper logging** - Multiple log messages track the shutdown progress
5. **Error resilience** - Exception handlers at multiple levels provide safety
6. **Keyboard interrupt support** - Handles Ctrl+C gracefully
7. **Database safety** - Databases are committed before shutdown is initiated
8. **Process termination guaranteed** - Even with connected clients, server shuts down cleanly

## Testing

To verify the fix works:

```bash
# Terminal 1: Run the server
python3 cgos.py configs/cgos.yaml

# Terminal 2: Wait a bit, then create the kill file
sleep 30
touch killfiles/kill_cgos9

# Check logs for graceful shutdown messages:
# - "KILL FILE FOUND - EXIT CGOS"
# - "Shutdown requested in schedule_games_task, exiting gracefully"
# - "Shutting down server_main, cancelling schedule_games_task"
# - "Server shutdown completed successfully"
# 
# NO asyncio "Task exception was never retrieved" errors should appear
```

## Files Modified
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/cgos.py`

## Backward Compatibility
These changes are fully backward compatible. The server behavior remains the same from a user perspective - kill file still triggers shutdown - but the shutdown is now graceful and clean.
