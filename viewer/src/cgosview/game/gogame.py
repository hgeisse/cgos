"""
Go game rules engine - Python translation of gogame.tcl

Implements complete Go game rules:
- Board state management (with borders)
- Move validation and execution
- Capture detection (flood-fill algorithm)
- KO rule enforcement
- Suicide detection
- Game history/undo functionality

Author: Translated from original Tcl version
License: MIT
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


class Stone(IntEnum):
    """Board intersection states."""
    EMPTY = 0
    BLACK = 1
    WHITE = 2
    BORDER = 3


class MoveError(IntEnum):
    """Move validation error codes (compatible with Tcl version)."""
    FORMAT_ERROR = -4
    OCCUPIED = -3
    KO_VIOLATION = -2
    SUICIDE = -1
    VALID = 0  # or positive for capture count


@dataclass
class GameState:
    """Immutable snapshot of game state."""
    board: List[int]
    move_number: int
    move: str
    captures: int = 0


class GoGame:
    """
    Complete Go game implementation with full rule enforcement.
    
    Supports:
    - Board sizes 7-25 (standard Go sizes)
    - Alternating black/white play
    - Capture detection and removal
    - KO rule (board state cannot repeat)
    - Suicide rule (cannot place stone with no liberties unless capturing)
    - Move history and undo functionality
    
    Example:
        >>> game = GoGame(19)
        >>> result = game.make_move("E5")
        >>> if result >= 0:
        ...     print(f"Valid move, captured {result} stones")
    """

    def __init__(self, size: int) -> None:
        """
        Initialize game board.
        
        Args:
            size: Board size (7-25 in standard Go)
        
        Raises:
            ValueError: If size not in valid range
        """
        if not 7 <= size <= 25:
            raise ValueError(f"Board size must be 7-25, got {size}")
        
        self.size = size
        self.n1 = size + 1  # Size + 1 for borders (index width)
        self.nn = size * size
        self.nnn = (size + 1) * (size + 2)
        
        # Game state
        self.current_move_number = 0
        self.board: List[int] = self._init_board()
        
        # History tracking (maps move number to board state)
        self.history: Dict[int, List[int]] = {0: self.board.copy()}
        self.moves: Dict[int, str] = {}
        
        # Board navigation directions (left, right, down, up)
        self.directions = [-1, 1, self.n1, -self.n1]
        
        logger.info(f"Initialized Go game with size {size}x{size}")
    
    def _init_board(self) -> List[int]:
        """
        Create new bordered board.
        
        Board is stored as flat list with border row/column of BORDER stones.
        Layout: (size+2) rows x (size+1) columns
        
        Returns:
            List of Stone values representing the board
        """
        board: List[int] = []
        for y in range(self.size + 2):
            for x in range(self.n1):
                # Border cells have BORDER stone, interior is EMPTY
                if y < 1 or y > self.size or x == 0:
                    board.append(Stone.BORDER)
                else:
                    board.append(Stone.EMPTY)
        return board
    
    def move_to_index(self, move: str) -> int:
        """
        Convert algebraic notation to board index.
        
        Go notation: Column (A-Z, skipping I) + Row (1-25, bottom to top)
        Examples: "A1" (bottom-left), "T19" (top-right)
        
        Args:
            move: Move in format "A1", "B3", etc. or "PASS"
        
        Returns:
            Board index (0-indexed into flattened board list) or error code:
            - Returns 0 for PASS
            - Returns -4 for format error
        """
        move_upper = move.upper().strip()
        
        # Handle pass
        if move_upper.startswith("PA"):
            return 0
        
        # Validate format: letter followed by digits
        if len(move_upper) < 2 or not move_upper[0].isalpha():
            return MoveError.FORMAT_ERROR
        
        try:
            x_char = move_upper[0]
            y_coord = int(move_upper[1:])
        except (ValueError, IndexError):
            return MoveError.FORMAT_ERROR
        
        # Convert Y coordinate (reverse for Go convention: 1 at bottom)
        y = self.n1 - y_coord
        
        if y > self.size or y < 1:
            return MoveError.FORMAT_ERROR
        
        # Convert X coordinate (handle 'I' skip in Go notation)
        x_ord = ord(x_char)
        if x_ord == ord('I'):
            return MoveError.FORMAT_ERROR
        if x_ord > ord('H'):
            x_ord -= 1  # Adjust for missing 'I' character
        
        x = x_ord - ord('A') + 1
        
        if not 1 <= x <= self.size:
            return MoveError.FORMAT_ERROR
        
        return y * self.n1 + x
    
    def _capture_group(self, target: int) -> List[int]:
        """
        Find captured stones in group (flood-fill algorithm).
        
        Starting from target position, finds all connected stones of same color.
        Returns empty list if group has at least one liberty (empty adjacent space).
        
        Args:
            target: Index of stone to check
        
        Returns:
            List of stone positions that would be captured, or empty list if group alive
        """
        if not (0 <= target < len(self.board)):
            return []
        
        target_stone = self.board[target]
        if target_stone in (Stone.EMPTY, Stone.BORDER):
            return []
        
        visited: Set[int] = {target}
        captured: List[int] = [target]
        stack: List[int] = [target]
        
        while stack:
            pos = stack.pop()
            
            # Check all 4 adjacent positions
            for direction in self.directions:
                neighbor = pos + direction
                
                if neighbor in visited:
                    continue
                
                visited.add(neighbor)
                neighbor_stone = self.board[neighbor]
                
                # Found liberty - group is alive, return empty
                if neighbor_stone == Stone.EMPTY:
                    return []
                
                # Same color - add to group for further checking
                if neighbor_stone == target_stone:
                    captured.append(neighbor)
                    stack.append(neighbor)
        
        # No liberties found - group is captured
        return captured
    
    def make_move(self, move: str) -> int:
        """
        Execute a move with full validation.
        
        Validates the move according to all Go rules:
        1. Move format is valid
        2. Target square is empty
        3. Move doesn't result in suicide (unless capturing)
        4. Move doesn't violate KO rule (board state can't repeat)
        
        Args:
            move: Move in algebraic notation or "PASS"
        
        Returns:
            -4: Format error (invalid notation)
            -3: Square occupied (already has a stone)
            -2: KO violation (board state would repeat)
            -1: Suicide (stone would have no liberties)
            0: Valid pass move
            ≥1: Number of opponent stones captured
        
        Side effects:
            - Updates board state, move history, and current move number
            - Does NOT update if validation fails
        """
        move_upper = move.upper().strip()
        
        # Determine player color (1 = black, 2 = white)
        # Black goes on even moves (0, 2, 4...), white on odd (1, 3, 5...)
        friendly_color = Stone.BLACK if self.current_move_number % 2 == 0 else Stone.WHITE
        enemy_color = Stone.WHITE if friendly_color == Stone.BLACK else Stone.BLACK
        
        # Handle pass
        if move_upper.startswith("PA"):
            self.moves[self.current_move_number] = "PASS"
            self.current_move_number += 1
            self.history[self.current_move_number] = self.board.copy()
            logger.debug(f"Move {self.current_move_number}: PASS")
            return MoveError.VALID
        
        # Validate and parse move
        index = self.move_to_index(move)
        if index < 0:
            return index
        
        # Check square is empty
        if self.board[index] != Stone.EMPTY:
            return MoveError.OCCUPIED
        
        # Save state for undo if validation fails
        prev_board = self.board.copy()
        
        # Place stone
        self.board[index] = friendly_color
        
        # Check captures in all 4 directions
        captured_total = []
        for direction in self.directions:
            neighbor = index + direction
            neighbor_stone = self.board[neighbor]
            
            if neighbor_stone == enemy_color:
                captured = self._capture_group(neighbor)
                if captured:
                    # Remove captured stones from board
                    for stone_pos in captured:
                        self.board[stone_pos] = Stone.EMPTY
                    captured_total.extend(captured)
        
        # Check suicide (own stone would have no liberties after move)
        if not captured_total:
            own_group = self._capture_group(index)
            if own_group:  # Non-empty list means no liberties
                self.board = prev_board  # Undo the move
                return MoveError.SUICIDE
        
        # Check KO rule (board state cannot be repeated)
        for move_num in range(self.current_move_number):
            if self.history[move_num] == self.board:
                self.board = prev_board  # Undo the move
                return MoveError.KO_VIOLATION
        
        # Move is valid - record it
        self.moves[self.current_move_number] = move_upper
        self.current_move_number += 1
        self.history[self.current_move_number] = self.board.copy()
        
        logger.debug(f"Move {self.current_move_number}: {move_upper} (captured {len(captured_total)})")
        
        return len(captured_total)
    
    def undo_move(self) -> bool:
        """
        Undo the last move.
        
        Returns:
            True if move was undone, False if at start of game
        """
        if self.current_move_number > 0:
            self.current_move_number -= 1
            self.board = self.history[self.current_move_number].copy()
            logger.debug(f"Undid move, now at move {self.current_move_number}")
            return True
        return False
    
    def undo_all(self) -> None:
        """Reset to start of game."""
        self.current_move_number = 0
        self.board = self.history[0].copy()
        logger.debug("Reset to start of game")
    
    def two_pass(self) -> bool:
        """
        Check if last two moves were passes (game end condition).
        
        Returns:
            True if both players have consecutively passed
        """
        if self.current_move_number < 2:
            return False
        
        move_n1 = self.moves.get(self.current_move_number - 1)
        move_n2 = self.moves.get(self.current_move_number - 2)
        
        return move_n1 == "PASS" and move_n2 == "PASS"
    
    def list_moves(self) -> List[str]:
        """
        Get all moves played so far.
        
        Returns:
            List of moves in order (includes PASS moves)
        """
        return [self.moves[i] for i in range(self.current_move_number)]
    
    def get_board(self) -> List[int]:
        """
        Get current board state (interior only, no borders).
        
        Returns:
            List of Stone values for the visible playing area (size x size).
            Ordered left-to-right, top-to-bottom.
        """
        board = []
        for y in range(1, self.size + 1):
            for x in range(1, self.n1):
                board.append(self.board[y * self.n1 + x])
        return board
    
    @property
    def color_to_move(self) -> Stone:
        """
        Get whose turn it is.
        
        Returns:
            Stone.BLACK (1) if black to move, Stone.WHITE (2) if white to move
        """
        # Black goes first (move 0, 2, 4, ...). White goes on odd moves (1, 3, 5, ...)
        if self.current_move_number % 2 == 0:
            return Stone.BLACK
        else:
            return Stone.WHITE
    
    def score_board(self, dead_list: List[str]) -> List[int]:
        """
        Calculate final board state for scoring.
        
        Removes dead stones and determines territory ownership.
        
        Args:
            dead_list: List of dead stones in algebraic notation (e.g., ["A1", "B2"])
        
        Returns:
            Board with dead stones removed and territory marked
        """
        b = self.board.copy()
        
        # Remove dead stones
        for move in dead_list:
            index = self.move_to_index(move)
            if index > 0:
                b[index] = Stone.EMPTY
        
        # Determine territory ownership
        flag: Dict[int, bool] = {}
        
        for y in range(1, self.size + 1):
            for x in range(1, self.n1):
                i = y * self.n1 + x
                
                if b[i] == 0 and i not in flag:  # Empty and not yet processed
                    lst = [i]
                    cc = 0  # Color of surrounding stones
                    flag[i] = True
                    
                    while True:
                        nlst: List[int] = []
                        
                        for ix in lst:
                            for d in self.directions:
                                p = ix + d
                                
                                if p not in flag:
                                    flag[p] = True
                                    if b[p] == Stone.EMPTY:
                                        nlst.append(p)
                                    elif b[p] == Stone.BLACK:
                                        cc |= 1
                                    elif b[p] == Stone.WHITE:
                                        cc |= 2
                        
                        if not nlst:
                            # Mark territory with controlling color
                            if cc == 1 or cc == 2:
                                for ix in [x for x in flag if flag[x]]:
                                    b[ix] = cc
                            break
                        
                        lst = nlst
        
        return b
    
    def get_final_board(self, dead: List[str]) -> List[int]:
        """
        Get final board state after scoring.
        
        Args:
            dead: List of dead stones in algebraic notation
        
        Returns:
            Scored board (interior only, no borders)
        """
        b = self.score_board(dead)
        board = []
        for y in range(1, self.size + 1):
            for x in range(1, self.n1):
                board.append(b[y * self.n1 + x])
        return board
