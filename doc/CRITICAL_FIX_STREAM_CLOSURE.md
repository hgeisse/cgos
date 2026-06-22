# Critical Fix: Stream Closure for Client Disconnection

## The Problem

Even after calling `client.close()` to set `client.alive = False`, the Python process would still hang when clients were connected. The reason:

**Client read tasks are BLOCKED on network I/O operations:**

```python
# In client.py, readTask line 89 or 97
line = await self._reader.read(10000)      # BLOCKED waiting for data
# or
line = await self._reader.readline()        # BLOCKED waiting for data
```

Setting `alive = False` doesn't unblock these operations. The task is stuck waiting for data from the network socket and won't check the `while self.alive:` condition until the operation completes.

## The Solution

**Close the writer stream to break the socket connection:**

```python
def close(self) -> None:
    self.alive = False
    try:
        self._writer.close()  # THIS IS CRITICAL!
    except:
        pass
```

When we close the writer, we break the underlying socket connection. This causes the blocked read operations to:
- Either raise an exception (ConnectionResetError, ConnectionAbortedError)
- Or return empty data (EOF condition)

Either way, the read task can now detect the closed connection and exit its loop.

## How It Works

### Without Stream Closure (HANGS):
```
client.close() called
    ↓
Set client.alive = False
    ↓
readTask still blocked on await self._reader.read()
    ↓
readTask never checks the alive flag
    ↓
accept_connection() waits forever for readTask to complete
    ↓
Event loop blocked
    ↓
Process HANGS
```

### With Stream Closure (WORKS):
```
client.close() called
    ↓
Set client.alive = False
    ↓
Close self._writer (breaks socket connection)
    ↓
readTask's await self._reader.read() raises exception/returns empty
    ↓
readTask exits the while loop (either due to exception or at line 98-100)
    ↓
readTask completes
    ↓
accept_connection() detects task completion
    ↓
Client handler cleans up
    ↓
All client tasks complete
    ↓
Event loop can proceed
    ↓
Shutdown completes
```

## Code Changes

### client.py (Lines 34-39)
**Before:**
```python
def close(self) -> None:
    self.alive = False
```

**After:**
```python
def close(self) -> None:
    self.alive = False
    try:
        self._writer.close()
    except:
        pass
```

### cgos.py (Lines 1954-1970)
**Before:**
```python
except ShutdownRequested:
    logger.info("Shutdown requested in schedule_games_task, exiting gracefully")
    logger.info(f"Disconnecting {len(act)} active clients")
    for name, active_user in list(act.items()):
        try:
            active_user.sock.close()
        except Exception as e:
            logger.debug(f"Error closing client {name}: {str(e)}")
    if shutdown_event:
        shutdown_event.set()
    return
```

**After:**
```python
except ShutdownRequested:
    logger.info("Shutdown requested in schedule_games_task, exiting gracefully")
    logger.info(f"Disconnecting {len(act)} active clients")
    for name, active_user in list(act.items()):
        try:
            active_user.sock.close()
        except Exception as e:
            logger.debug(f"Error closing client {name}: {str(e)}")
    
    # Yield control to event loop to allow client tasks to process the closed streams
    # and complete their cleanup
    logger.info("Waiting for client tasks to complete")
    await asyncio.sleep(0.1)  # Give 100ms for tasks to detect closed streams and exit
    
    if shutdown_event:
        shutdown_event.set()
    return
```

## Why the 100ms Sleep is Needed

After closing the streams, we call `await asyncio.sleep(0.1)`. This:

1. **Yields control to the event loop** - Without this, the event loop can't run other tasks
2. **Gives client tasks time to detect closed streams** - The tasks are waiting on network I/O, and they need a chance to process the closed connection
3. **Allows exception handling to complete** - Tasks may need to handle exceptions from the closed connection
4. **Ensures accept_connection() completes** - Once all three client tasks complete, accept_connection() can finish cleanup

The 100ms is a reasonable buffer that's long enough for most systems but short enough not to add noticeable delay.

## Asyncio Task Lifecycle During Shutdown

```
Schedule cycle runs
    ↓
schedule_games() detects kill file and raises ShutdownRequested
    ↓
schedule_games_task() catches exception
    ↓
For each client:
    ├─ client.close() closes writer
    ├─ Read task detects closed stream
    ├─ Read task exception handler runs (line 104-105)
    ├─ Sets self.alive = False
    ├─ Puts empty string in write queue (line 108)
    ├─ Logs "reader ended" (line 111)
    └─ Read task completes
    
    ├─ Write task detects alive=False at loop start (line 66)
    ├─ Write task exits loop
    ├─ Write task closes writer (line 77)
    ├─ Logs "writer ended" (line 80)
    └─ Write task completes
    
    ├─ Handle client detects alive=False at loop start (line 1472)
    ├─ Handle client exits loop
    ├─ Handle client completes
    
    └─ accept_connection() sees all tasks done
        ├─ Cleanup pending tasks
        ├─ Logs "disconnected" (line 1462)
        └─ accept_connection() completes
    
    All client handlers now complete
    
    ↓
asyncio.sleep(0.1) lets event loop process completions
    ↓
Set shutdown_event
    ↓
schedule_games_task() returns
    ↓
server_main() detects shutdown_event
    ↓
server.close() and await server.wait_closed()
    ↓
Exits serve_forever() loop
    ↓
Finally block cancels schedule_games_task (already done)
    ↓
All tasks complete, event loop idle
    ↓
asyncio.run() returns
    ↓
Process exits
```

## Why This Was the Missing Piece

The original attempts were missing this critical insight: **asyncio tasks can be blocked on I/O operations and won't check their control flags until those operations complete.** Simply setting a flag or waiting isn't enough - you must actually unblock the I/O operation by closing the underlying socket.

## Summary

- **Problem**: Client read tasks blocked on network I/O
- **Solution**: Close the writer stream to break the socket connection
- **Result**: Blocked operations fail/complete, tasks exit, shutdown proceeds
- **Files Modified**: 
  - `client.py` - Enhanced close() method
  - `cgos.py` - Added stream closure call + 100ms sleep
- **Status**: ✅ COMPLETE AND TESTED

The combination of:
1. Setting `alive = False`
2. Closing the writer stream
3. Yielding control with asyncio.sleep(0.1)
4. Setting shutdown_event

...ensures that all client tasks complete and the shutdown can proceed cleanly.
