"""
Async client for CGOS (Computer Go Online Server) communication.

Handles non-blocking connection to CGOS server and game updates.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GameInfo:
    """Game metadata from CGOS server."""
    
    gid: int
    """Game ID"""
    
    date: str
    """Game date"""
    
    time: str
    """Game time"""
    
    board_size: int
    """Board size (7-25)"""
    
    komi: float
    """Komi (handicap points for white)"""
    
    white_player: str
    """White player name"""
    
    black_player: str
    """Black player name"""
    
    result: Optional[str] = None
    """Game result (e.g., "W+2.5", "B+Resign")"""
    
    moves: List[Tuple[str, float]] = field(default_factory=list)
    """List of (move, elapsed_time) tuples"""


class CGOSClient:
    """
    Async client for CGOS server communication.
    
    Establishes TCP connection to CGOS server and receives real-time
    game updates from players.
    
    Usage:
        client = CGOSClient()
        await client.connect()
        # Set up callbacks
        client.on_game_update = handle_game_update
        # Start receiving games
        await client.receive_games()
    """
    
    def __init__(self, host: str = "cgos.boardspace.net", port: int = 6867):
        """
        Initialize CGOS client.
        
        Args:
            host: CGOS server hostname
            port: CGOS server port
        """
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.active_games: Dict[int, GameInfo] = {}
        self.on_game_update: Optional[Callable[[GameInfo], None]] = None
        self.connected = False
        
        logger.info(f"Initialized CGOS client for {host}:{port}")
    
    async def connect(self) -> bool:
        """
        Establish connection to CGOS server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            self.connected = True
            logger.info(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False
    
    async def disconnect(self) -> None:
        """Close connection to server."""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
                self.connected = False
                logger.info("Disconnected from server")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
    
    async def receive_games(self) -> None:
        """
        Main loop to receive game updates from server.
        
        This method blocks and continuously reads game data from server.
        Call in a separate task with: asyncio.create_task(client.receive_games())
        """
        if not self.connected:
            logger.error("Not connected to server")
            return
        
        try:
            while self.reader and self.connected:
                # Read line from server
                line = await self.reader.readline()
                if not line:
                    logger.info("Server closed connection")
                    break
                
                # Parse game update
                try:
                    game_info = self._parse_game_line(line.decode().strip())
                    if game_info:
                        self.active_games[game_info.gid] = game_info
                        if self.on_game_update:
                            self.on_game_update(game_info)
                except Exception as e:
                    logger.error(f"Error parsing game line: {e}")
        
        except Exception as e:
            logger.error(f"Error receiving games: {e}")
        finally:
            await self.disconnect()
    
    def _parse_game_line(self, line: str) -> Optional[GameInfo]:
        """
        Parse CGOS protocol line into GameInfo.
        
        Protocol format (example):
            gid date time boardsize komi white black result moves...
        
        Args:
            line: Raw line from CGOS server
        
        Returns:
            GameInfo object or None if parse error
        """
        if not line or line.startswith("#"):
            return None
        
        try:
            parts = line.split()
            if len(parts) < 7:
                return None
            
            gid = int(parts[0])
            date = parts[1]
            time = parts[2]
            board_size = int(parts[3])
            komi = float(parts[4])
            white_player = parts[5]
            black_player = parts[6]
            result = parts[7] if len(parts) > 7 else None
            
            # Parse moves (pairs of move and elapsed time)
            moves: List[Tuple[str, float]] = []
            for i in range(8, len(parts) - 1, 2):
                try:
                    move = parts[i]
                    elapsed = float(parts[i + 1])
                    moves.append((move, elapsed))
                except (ValueError, IndexError):
                    break
            
            return GameInfo(
                gid=gid,
                date=date,
                time=time,
                board_size=board_size,
                komi=komi,
                white_player=white_player,
                black_player=black_player,
                result=result,
                moves=moves
            )
        
        except (ValueError, IndexError) as e:
            logger.debug(f"Could not parse line: {line} ({e})")
            return None
    
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
