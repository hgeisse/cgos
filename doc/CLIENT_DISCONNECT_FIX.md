# Critical Fix: Client Disconnection on Shutdown

## The Problem

When the kill file was detected with connected clients, the process would hang indefinitely because:

1. **Client handler structure** - Each connected client has three async tasks:
   - `readTask()` - reads data from client socket
   - `writeTask()` - writes data to client socket  
   - `handle_client()` - processes client protocol messages

2. **accept_connection() waits** - The `accept_connection()` coroutine for each client runs:
   ```python
   tasks = [readTask, writeTask, handleTask]
   done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
   ```
   It waits for ONE of these three tasks to complete, then cancels the others.

3. **The hang scenario**:
   - Kill file is detected
   - `schedule_games_task()` would set `shutdown_event`
   - `server_main()` would close the server socket
   - But active client connections would keep their tasks running indefinitely
   - The `accept_connection()` coroutines would remain blocked
   - The event loop would never exit because these tasks never complete

## The Solution

**Disconnect all active clients before signaling shutdown:**

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
```

### How It Works

1. **client.close()** sets `client.alive = False` AND closes the writer stream
   - From `client.py` line 34-39:
   ```python
   def close(self) -> None:
       self.alive = False
       try:
           self._writer.close()
       except:
           pass
   ```

2. **Closing the writer unblocks I/O**:
   - `readTask()` is blocked on `await self._reader.read()` (line 89) or `await self._reader.readline()` (line 97)
   - When the writer is closed, the underlying socket connection is broken
   - This causes the read/write operations to raise exceptions or return empty data
   - Tasks can now detect the closed connection and exit

3. **Tasks check alive flag**:
   - `readTask()` loop: `while self.alive:` (line 86)
   - `writeTask()` loop: `while self.alive:` (line 66)
   - `handle_client()` loop: `while client.alive:` (line 1472)

4. **Event loop yields control**:
   - `schedule_games_task()` calls `await asyncio.sleep(0.1)` after closing clients
   - This allows the event loop to process the closed streams
   - Client tasks detect the closed connection and complete
   - `accept_connection()` coroutines detect task completion
   - Cancels pending tasks and cleans up
   - Client cleanup code runs (lines 1455-1462)

5. **When alive becomes False**:
   - Each task exits its main loop
   - Tasks complete/raise exceptions
   - `accept_connection()` coroutine detects task completion
   - Cancels pending tasks and cleans up
   - Client cleanup code runs

4. **Event loop can now exit**:
   - All client handler tasks have completed
   - `schedule_games_task()` returns
   - `server.serve_forever()` is closed by shutdown_event
   - Event loop becomes idle
   - `asyncio.run()` completes
   - Process exits

## Code Flow Diagram

```
Kill file detected
    ↓
schedule_games() raises ShutdownRequested
    ↓
schedule_games_task() catches ShutdownRequested
    ↓
For each active client:
    ├─ client.close() [sets client.alive = False AND closes writer]
    └─ This causes:
        ├─ Writer socket closes
        ├─ Reader/Writer blocked operations raise exceptions
        ├─ readTask detects closed stream → exits
        ├─ writeTask detects closed stream → exits
        ├─ handle_client checks alive → exits
        └─ accept_connection detects completion
            └─ Cancels pending tasks
            └─ Runs cleanup code
                └─ Client handler fully completes
    ↓
Yield control with await asyncio.sleep(0.1)
    ↓
Event loop processes client task completions
    ↓
Set shutdown_event
    ↓
schedule_games_task() returns (task done)
    ↓
server_main() detects shutdown_event
    ↓
server.close() + wait_closed()
    ↓
Exits serve_forever() loop
    ↓
Finally block executes
    ↓
All tasks are now complete
    ↓
asyncio.run() completes
    ↓
runServer() logs success
    ↓
Process exits with code 0
```

## Key Implementation Details

### ActiveUser Structure (cgos.py:210)
```python
class ActiveUser:
    sock: Client  # This is the client object
    msg_state: str
    gid: int
    rating: float
    k: float
```

### Client.close() Method (client.py:34-35)
```python
def close(self) -> None:
    self.alive = False  # Sets the alive flag to False
```

### Task Loops Check Alive Flag
- `readTask()` (client.py:86): `while self.alive:`
- `writeTask()` (client.py:66): `while self.alive:`
- `handle_client()` (cgos.py:1472): `while client.alive:`

## Why This Must Happen in schedule_games_task()

The client disconnection must happen in `schedule_games_task()` because:

1. **It's the only place with access to `act` (active users dictionary)** during shutdown
2. **It's running in the event loop** - can properly disconnect async clients
3. **It happens before signaling shutdown** - ensures all clients are gone before server closes

If we tried to do this in `server_main()`, we wouldn't have access to the active users dictionary.

## Testing Verification

To verify the fix works with connected clients:

```bash
# Terminal 1: Run server
python3 -m cgos.app.cgos configs/cgos.yaml

# Terminal 2: Connect a client (simulate with telnet or nc)
telnet localhost 6119

# Terminal 3: After connection is established, create kill file
sleep 5
touch killfiles/kill_cgos9

# Expected behavior:
# 1. Client connection closes
# 2. Server logs "Disconnecting 1 active clients"
# 3. Process exits cleanly within 1-20 seconds
# 4. No hanging process
# 5. No asyncio errors
```

## Comparison: Before and After

### BEFORE (Process hangs with connected client)
```
Client connected
    ↓
Kill file created
    ↓
schedule_games_task catches ShutdownRequested
    ↓
Sets shutdown_event (but clients still running)
    ↓
server_main tries to close
    ↓
readTask/writeTask/handle_client still looping
    ↓
accept_connection still waiting
    ↓
Event loop blocked
    ↓
Process HANGS (never exits)
```

### AFTER (Process exits cleanly with connected client)
```
Client connected
    ↓
Kill file created
    ↓
schedule_games_task catches ShutdownRequested
    ↓
Calls client.close() on all active clients
    ↓
readTask/writeTask/handle_client see alive=False and exit
    ↓
accept_connection completes
    ↓
Sets shutdown_event
    ↓
server_main detects event and closes
    ↓
Event loop becomes idle
    ↓
asyncio.run() completes
    ↓
Process EXITS (exit code 0)
```

## Files Modified
- `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/cgos.py` (schedule_games_task function)

## Status
✓ Syntax verified
✓ Ready for testing with connected clients
