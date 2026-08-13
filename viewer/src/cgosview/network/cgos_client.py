"""
Async client for CGOS (Computer Go Online Server) communication.

Handles non-blocking connection to CGOS server and game updates with
robust error handling, reconnection logic, and protocol compliance.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    ERROR = 3


@dataclass
class GameInfo:
    """Game metadata from CGOS server."""
    
    gid: int
    """Game ID"""
    
    date: str
    """Game date (YYYY-MM-DD)"""
    
    time: str
    """Game start time (HH:MM:SS)"""
    
    board_size: int
    """Board size (7-25)"""
    
    komi: float
    """Komi (handicap points for white)"""
    
    white_player: str
    """White player name"""
    
    black_player: str
    """Black player name"""
    
    result: Optional[str] = None
    """Game result (e.g., "W+2.5", "B+Resign") - None if in progress"""
    
    moves: List[Tuple[str, float]] = field(default_factory=list)
    """List of (move, elapsed_time) tuples"""
    
    def is_finished(self) -> bool:
        """Check if game has finished."""
        return self.result is not None
    
    def __hash__(self) -> int:
        """Make hashable by gid."""
        return hash(self.gid)
    
    def __eq__(self, other: object) -> bool:
        """Compare by gid."""
        if not isinstance(other, GameInfo):
            return False
        return self.gid == other.gid


class CGOSClient:
    """
    Async client for CGOS server communication.
    
    Establishes TCP connection to CGOS server and receives real-time
    game updates with automatic reconnection and heartbeat monitoring.
    
    Features:
    - Non-blocking async I/O
    - Automatic reconnection with exponential backoff
    - Protocol handshake (v1 viewer protocol)
    - Heartbeat/ping mechanism for connection health
    - Event callbacks for game updates
    - Proper error handling and logging
    
    Usage:
        client = CGOSClient("cgos-hg.de", 6809)
        client.on_game_added = handle_game_added
        client.on_game_updated = handle_game_updated
        await client.connect()
        await client.receive_games()
    """
    
    def __init__(
        self,
        host: str = "cgos-hg.de",
        port: int = 6809,
        connection_timeout: float = 10.0,
        heartbeat_interval: float = 30.0,
        max_retries: int = 5,
        reconnect_base_delay: float = 1.0,
        max_games: int = 50
    ):
        """
        Initialize CGOS client.
        
        Args:
            host: CGOS server hostname
            port: CGOS server port
            connection_timeout: Connection timeout in seconds
            heartbeat_interval: Heartbeat interval in seconds
            max_retries: Maximum reconnection attempts
            reconnect_base_delay: Base delay for exponential backoff
            max_games: Maximum number of games to track in the game list
        """
        self.host = host
        self.port = port
        self.connection_timeout = connection_timeout
        self.heartbeat_interval = heartbeat_interval
        self.max_retries = max_retries
        self.reconnect_base_delay = reconnect_base_delay
        self.max_games = max_games
        
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.active_games: Dict[int, GameInfo] = {}
        self.connection_state = ConnectionState.DISCONNECTED
        self.error_message: Optional[str] = None
        
        # Callbacks
        self.on_game_added: Optional[Callable[[GameInfo], None]] = None
        self.on_game_updated: Optional[Callable[[GameInfo], None]] = None
        self.on_game_finished: Optional[Callable[[GameInfo], None]] = None
        self.on_connection_state_changed: Optional[Callable[[ConnectionState, Optional[str]], None]] = None
        
        logger.info(f"Initialized CGOS client for {host}:{port}")
    
    def get_state(self) -> ConnectionState:
        """Get current connection state."""
        return self.connection_state
    
    def set_state(self, state: ConnectionState, error: Optional[str] = None) -> None:
        """
        Set connection state and trigger callback.
        
        Args:
            state: New connection state
            error: Optional error message
        """
        if self.connection_state != state:
            self.connection_state = state
            self.error_message = error
            logger.info(f"Connection state changed: {state.name}" + 
                       (f" - {error}" if error else ""))
            
            if self.on_connection_state_changed:
                self.on_connection_state_changed(state, error)
    
    async def connect(self) -> bool:
        """
        Establish connection to CGOS server.
        
        Returns:
            True if connection successful, False otherwise
        """
        self.set_state(ConnectionState.CONNECTING)
        
        try:
            logger.info(f"Attempting connection to {self.host}:{self.port}")
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.connection_timeout
            )
            self.set_state(ConnectionState.CONNECTED)
            logger.info(f"Connected to {self.host}:{self.port}")
            return True
        except asyncio.TimeoutError:
            error = f"Connection timeout after {self.connection_timeout}s"
            self.set_state(ConnectionState.ERROR, error)
            logger.error(error)
            return False
        except Exception as e:
            error = f"Connection failed: {e}"
            self.set_state(ConnectionState.ERROR, error)
            logger.error(error)
            return False
    
    async def disconnect(self) -> None:
        """Close connection to server."""
        try:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            self.reader = None
            self.writer = None
            self.set_state(ConnectionState.DISCONNECTED)
            logger.info("Disconnected from server")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def connect_with_retry(self) -> bool:
        """
        Attempt connection with exponential backoff retry.
        
        Returns:
            True if eventually connected, False if all retries exhausted
        """
        for attempt in range(self.max_retries):
            if await self.connect():
                return True
            
            if attempt < self.max_retries - 1:
                delay = self.reconnect_base_delay * (2 ** attempt)
                logger.info(f"Reconnection attempt {attempt + 1}/{self.max_retries}, "
                          f"retrying in {delay}s")
                await asyncio.sleep(delay)
        
        logger.error(f"Failed to connect after {self.max_retries} attempts")
        return False
    
    async def send_command(self, command: str) -> bool:
        """
        Send command to CGOS server.
        
        Args:
            command: Command string to send
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.writer:
            logger.error("Not connected to server")
            return False
        
        try:
            self.writer.write((command + "\n").encode())
            await self.writer.drain()
            logger.debug(f"Sent command: {command}")
            return True
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False
    
    async def observe_game(self, gid: int) -> bool:
        """
        Send observe command for a specific game.
        
        This should be called when a user opens/clicks on a game to view it.
        The server will respond with a SETUP message containing the game's moves.
        
        Args:
            gid: Game ID to observe
        
        Returns:
            True if observe command sent successfully, False otherwise
        """
        logger.info(f"Sending observe command for game {gid}")
        return await self.send_command(f"observe {gid}")
    

    def _parse_match_message(self, parts: List[str]) -> Optional[GameInfo]:
        """
        Parse CGOS MATCH message.
        
        Format: match gid date time size komi white(rating) black(rating) [result]
        
        Args:
            parts: Split message parts (starting from "match")
        
        Returns:
            GameInfo object or None if parse error
        """
        try:
            # Match message has at least: match gid date time size komi white black
            if len(parts) < 8:
                logger.debug(f"Match message too short: {len(parts)} parts")
                return None
            
            gid = int(parts[1])
            date = parts[2]
            time = parts[3]
            board_size = int(parts[4])
            komi = float(parts[5])
            white_player = self._extract_player_name(parts[6])
            black_player = self._extract_player_name(parts[7])
            
            # Check for result (only if game is finished)
            result = None
            if len(parts) > 8 and parts[8] != "-":
                potential_result = parts[8]
                if potential_result.startswith("W+") or \
                   potential_result.startswith("B+") or \
                   potential_result == "Draw" or \
                   "Resign" in potential_result:
                    result = potential_result
            
            return GameInfo(
                gid=gid,
                date=date,
                time=time,
                board_size=board_size,
                komi=komi,
                white_player=white_player,
                black_player=black_player,
                result=result,
                moves=[]
            )
        except (ValueError, IndexError) as e:
            logger.debug(f"Could not parse match message: {e}")
            return None
    
    def _parse_setup_message(self, parts: List[str]) -> Optional[Tuple[int, List[Tuple[str, float]], dict]]:
        """
        Parse CGOS SETUP message.
        
        Two formats:
        1. Active game: setup gid - - size komi white(rating) black(rating) level [move time...]
        2. Archived game: setup gid date time size komi white(rating) black(rating) level [move time...] result
        
        Args:
            parts: Split message parts (starting from "setup")
        
        Returns:
            Tuple of (gid, moves_list, game_data_dict) or None if parse error
            where game_data_dict contains: date, time, board_size, komi, white_player, black_player, result
        """
        try:
            if len(parts) < 9:
                logger.debug(f"Setup message too short: {len(parts)} parts")
                return None
            
            gid = int(parts[1])
            
            # Check if this is an active game (- -) or archived game (actual date/time)
            is_active = parts[2] == "-" and parts[3] == "-"
            
            if is_active:
                # Format: setup gid - - size komi white black level [moves...]
                # parts[0]=setup, parts[1]=gid, parts[2]=-, parts[3]=-, parts[4]=size,
                # parts[5]=komi, parts[6]=white, parts[7]=black, parts[8]=level, parts[9+]=moves
                
                date = "-"
                time = "-"
                board_size = int(parts[4])
                komi = float(parts[5])
                white_player = self._extract_player_name(parts[6])
                black_player = self._extract_player_name(parts[7])
                result = None
                move_start_idx = 9
            else:
                # Format: setup gid date time size komi white black level [moves...] [result]
                # parts[0]=setup, parts[1]=gid, parts[2]=date, parts[3]=time, parts[4]=size,
                # parts[5]=komi, parts[6]=white, parts[7]=black, parts[8]=level, parts[9+]=moves
                
                date = parts[2]
                time = parts[3]
                board_size = int(parts[4])
                komi = float(parts[5])
                white_player = self._extract_player_name(parts[6])
                black_player = self._extract_player_name(parts[7])
                
                # Parse moves and result (result is the last element if it's a result string)
                move_start_idx = 9
                result = None
                
                # Check if last part is a result (archived games have results)
                if len(parts) > move_start_idx:
                    last_part = parts[-1]
                    if last_part.startswith("W+") or last_part.startswith("B+") or \
                       last_part == "Draw" or "Resign" in last_part or last_part == "?":
                        result = last_part
            
            # Parse moves (pairs of move and time)
            moves: List[Tuple[str, float]] = []
            
            # Determine the end index for moves (exclude result if present)
            move_end_idx = len(parts)
            if result is not None and not is_active:
                move_end_idx = len(parts) - 1
            
            for i in range(move_start_idx, move_end_idx - 1, 2):
                try:
                    move = parts[i]
                    time_value = float(parts[i + 1])
                    moves.append((move, time_value))
                except (ValueError, IndexError):
                    break
            
            game_data = {
                "date": date,
                "time": time,
                "board_size": board_size,
                "komi": komi,
                "white_player": white_player,
                "black_player": black_player,
                "result": result
            }
            
            return (gid, moves, game_data)
        except (ValueError, IndexError) as e:
            logger.debug(f"Could not parse setup message: {e}")
            return None
    
    def _parse_update_message(self, parts: List[str]) -> Optional[Tuple[int, str, float]]:
        """
        Parse CGOS UPDATE message.
        
        Format: update gid move time_remaining_ms
        
        Args:
            parts: Split message parts (starting from "update")
        
        Returns:
            Tuple of (gid, move, time_value) or None if parse error
            where time_value is the time field value (typically remaining time in ms,
            converted to seconds for consistency with SETUP messages)
        """
        try:
            if len(parts) < 4:
                logger.debug(f"Update message too short: {len(parts)} parts")
                return None
            
            gid = int(parts[1])
            move = parts[2]
            # Time value - store as-is (convert from ms to s if it's a large number)
            time_value = float(parts[3])
            # If time_value is > 1000, assume it's in milliseconds, convert to seconds
            if time_value > 1000:
                time_value = time_value / 1000.0
            
            return (gid, move, time_value)
        except (ValueError, IndexError) as e:
            logger.debug(f"Could not parse update message: {e}")
            return None
    
    def _parse_gameover_message(self, parts: List[str]) -> Optional[Tuple[int, str]]:
        """
        Parse CGOS GAMEOVER message.
        
        Format: gameover gid result [white_time_ms black_time_ms]
        
        Args:
            parts: Split message parts (starting from "gameover")
        
        Returns:
            Tuple of (gid, result) or None if parse error
        """
        try:
            if len(parts) < 3:
                logger.debug(f"Gameover message too short: {len(parts)} parts")
                return None
            
            gid = int(parts[1])
            result = parts[2]
            
            return (gid, result)
        except (ValueError, IndexError) as e:
            logger.debug(f"Could not parse gameover message: {e}")
            return None
    
    @staticmethod
    def _extract_player_name(player_str: str) -> str:
        """
        Extract player name from player field.
        
        Format: "PlayerName(1900)" or "PlayerName"
        Returns: "PlayerName"
        """
        if '(' in player_str:
            return player_str.split('(')[0]
        return player_str
    
    def _parse_message(self, line: str) -> Optional[Tuple[str, object]]:
        """
        Parse a CGOS protocol message.
        
        Returns:
            Tuple of (message_type, parsed_data) where message_type is one of:
            - "match": GameInfo object
            - "setup": (gid, moves_list, game_data_dict)
            - "update": (gid, move, time)
            - "gameover": (gid, result)
            - None: If message could not be parsed
        """
        if not line or line.startswith("#"):
            return None
        
        parts = line.split()
        if not parts:
            return None
        
        msg_type = parts[0].lower()
        
        if msg_type == "match":
            result = self._parse_match_message(parts)
            return ("match", result) if result else None
        
        elif msg_type == "setup":
            result = self._parse_setup_message(parts)
            return ("setup", result) if result else None
        
        elif msg_type == "update":
            result = self._parse_update_message(parts)
            return ("update", result) if result else None
        
        elif msg_type == "gameover":
            result = self._parse_gameover_message(parts)
            return ("gameover", result) if result else None
        
        else:
            logger.debug(f"Unknown message type: {msg_type}")
            return None
    
    async def receive_games(self) -> None:
        """
        Main loop to receive game updates from server.
        
        This method:
        1. Receives and parses protocol request from server
        2. Sends protocol handshake (v1 viewer protocol)
        3. Continuously reads game messages (match, setup, update, gameover)
        4. Maintains game state from event-based protocol
        5. Triggers callbacks for game changes
        6. Handles errors gracefully
        
        Protocol flow:
        - Receive: "protocol genmove_analyze"
        - Send: v1 cgosview/1.0.0
        - Receive: MATCH messages listing games
        - Send: OBSERVE commands for games
        - Receive: SETUP message with full game state
        - Receive: UPDATE messages for each move
        - Receive: GAMEOVER when game finishes
        
        This method blocks and runs continuously.
        Call in a separate task with: asyncio.create_task(client.receive_games())
        """
        if not self.reader or self.connection_state != ConnectionState.CONNECTED:
            logger.error("Not connected to server")
            return
        
        try:
            # Step 1: Receive protocol request from server
            logger.info("Waiting for protocol request from server")
            try:
                protocol_line = await asyncio.wait_for(
                    self.reader.readline(),
                    timeout=self.connection_timeout
                )
                if not protocol_line:
                    error = "Server closed connection before protocol exchange"
                    logger.error(error)
                    self.set_state(ConnectionState.ERROR, error)
                    return
                
                protocol_msg = protocol_line.decode().strip()
                logger.info(f"Received protocol request: {protocol_msg}")
                
                # Verify it's a protocol message (should be "protocol genmove_analyze")
                if not protocol_msg.startswith("protocol"):
                    logger.warning(f"Expected 'protocol' message, got: {protocol_msg}")
            
            except asyncio.TimeoutError:
                error = f"Timeout waiting for protocol request ({self.connection_timeout}s)"
                logger.error(error)
                self.set_state(ConnectionState.ERROR, error)
                return
            
            # Step 2: Send protocol identification in response
            logger.info("Sending viewer protocol identification")
            if not await self.send_command("v1 cgosview/1.0.0"):
                logger.error("Failed to send protocol identification")
                self.set_state(ConnectionState.ERROR, "Failed to send protocol identification")
                return
            
            # Main receive loop
            logger.info("Starting game message receive loop")
            
            while self.connection_state == ConnectionState.CONNECTED:
                try:
                    # Read line with timeout to allow heartbeat checks
                    line = await asyncio.wait_for(
                        self.reader.readline(),
                        timeout=max(self.heartbeat_interval * 2, 60.0)
                    )
                    
                    if not line:
                        logger.info("Server closed connection")
                        self.set_state(ConnectionState.ERROR, "Server closed connection")
                        break
                    
                    # Parse message
                    try:
                        msg_data = self._parse_message(line.decode().strip())
                        
                        if not msg_data:
                            continue
                        
                        msg_type, data = msg_data
                        
                        if msg_type == "match":
                            # New or updated game announcement
                            game_info = data
                            if game_info:
                                is_new = game_info.gid not in self.active_games
                                
                                # Enforce max games limit
                                if is_new and len(self.active_games) >= self.max_games:
                                    oldest_gid = min(self.active_games.keys())
                                    del self.active_games[oldest_gid]
                                    logger.debug(f"Removed oldest game {oldest_gid}")
                                
                                # Store game
                                self.active_games[game_info.gid] = game_info
                                
                                # Trigger callback
                                if is_new:
                                    logger.info(f"New game {game_info.gid}: "
                                              f"{game_info.white_player} vs {game_info.black_player}")
                                    if self.on_game_added:
                                        self.on_game_added(game_info)
                        
                        elif msg_type == "setup":
                            # Game setup with initial moves (in response to observe command)
                            gid, moves, game_data = data
                            if gid in self.active_games:
                                game_info = self.active_games[gid]
                                game_info.moves = moves
                                
                                # Update game info with data from SETUP message
                                # For archived games, this includes date, time, and result
                                if game_data.get("date") != "-":
                                    game_info.date = game_data["date"]
                                if game_data.get("time") != "-":
                                    game_info.time = game_data["time"]
                                if game_data.get("result"):
                                    game_info.result = game_data["result"]
                                
                                logger.info(f"Game {gid} setup: {len(moves)} moves")
                                if self.on_game_updated:
                                    self.on_game_updated(game_info)
                        
                        elif msg_type == "update":
                            # New move in game
                            gid, move, time_remaining = data
                            if gid in self.active_games:
                                game_info = self.active_games[gid]
                                # Append new move
                                game_info.moves.append((move, time_remaining))
                                logger.debug(f"Game {gid} move: {move} (time: {time_remaining}s)")
                                if self.on_game_updated:
                                    self.on_game_updated(game_info)
                        
                        elif msg_type == "gameover":
                            # Game finished
                            gid, result = data
                            if gid in self.active_games:
                                game_info = self.active_games[gid]
                                game_info.result = result
                                logger.info(f"Game {gid} finished: {result}")
                                if self.on_game_finished:
                                    self.on_game_finished(game_info)
                    
                    except Exception as e:
                        logger.error(f"Error parsing message: {e}")
                
                except asyncio.TimeoutError:
                    logger.debug("Receive timeout (normal heartbeat check)")
                except Exception as e:
                    logger.error(f"Error receiving games: {e}")
                    self.set_state(ConnectionState.ERROR, str(e))
                    break
        
        except Exception as e:
            error = f"Fatal error in receive loop: {e}"
            self.set_state(ConnectionState.ERROR, error)
            logger.error(error)
        finally:
            await self.disconnect()
    
    def get_games(self) -> List[GameInfo]:
        """
        Get list of active games.
        
        Returns:
            List of GameInfo objects sorted by game ID
        """
        return sorted(self.active_games.values(), key=lambda g: g.gid, reverse=True)
