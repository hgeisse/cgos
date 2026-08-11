"""
GameTab widget for displaying a single game in the tabbed interface.

Each tab represents one actively observed game with its own board,
navigation controls, and game state.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSplitter
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont

from cgosview.game.gogame import GoGame
from cgosview.gui.board_widget import GameBoardWidget
from cgosview.gui.move_history_table import MoveHistoryTable
from cgosview.network.cgos_client import GameInfo

logger = logging.getLogger(__name__)


class GameTab(QWidget):
    """
    A single game tab widget containing board, navigation, and game info.
    
    Each tab maintains its own:
    - GoGame instance
    - Replay position (for independent navigation)
    - Board widget
    - Navigation controls
    """
    
    # Signals
    game_updated = pyqtSignal(int)  # Emitted when this tab's game is updated
    
    def __init__(self, gid: int, game_info: GameInfo):
        """
        Initialize a game tab.
        
        Args:
            gid: Game ID
            game_info: GameInfo object with initial game data
        """
        super().__init__()
        
        self.gid = gid
        self.game_info = game_info
        self.current_game: Optional[GoGame] = None
        self.replay_position = 0
        
        # Create UI
        self._create_ui()
        
        # Load initial game
        self._load_game(game_info)
        
        logger.info(f"GameTab created for game {gid}")
    
    def _create_ui(self) -> None:
        """Create the tab's user interface."""
        layout = QVBoxLayout()
        
        # ===== Game Info =====
        self.game_info_label = QLabel()
        self.game_info_label.setFont(QFont("Arial", 10))
        self.game_info_label.setStyleSheet("padding: 10px;")
        layout.addWidget(self.game_info_label)
        
        # ===== Board and Move History with Splitter =====
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Board widget (left side)
        self.board_widget = GameBoardWidget(self.game_info.board_size)
        self.board_widget.setMinimumSize(QSize(600, 600))
        splitter.addWidget(self.board_widget)
        
        # Move history table (right side)
        self.move_history_table = MoveHistoryTable()
        self.move_history_table.setMinimumWidth(250)
        self.move_history_table.move_clicked.connect(self._on_move_table_clicked)
        splitter.addWidget(self.move_history_table)
        
        # Set initial split proportion (70% board, 30% table)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter)
        
        # ===== Navigation Controls =====
        nav_layout = QHBoxLayout()
        
        self.nav_first = QPushButton("<<")
        self.nav_first.setMaximumWidth(60)
        self.nav_first.clicked.connect(self._on_nav_first)
        nav_layout.addWidget(self.nav_first)
        
        self.nav_prev = QPushButton("<")
        self.nav_prev.setMaximumWidth(60)
        self.nav_prev.clicked.connect(self._on_nav_prev)
        nav_layout.addWidget(self.nav_prev)
        
        self.move_label = QLabel("Move: 0/0")
        self.move_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(self.move_label)
        
        self.nav_next = QPushButton(">")
        self.nav_next.setMaximumWidth(60)
        self.nav_next.clicked.connect(self._on_nav_next)
        nav_layout.addWidget(self.nav_next)
        
        self.nav_last = QPushButton(">>")
        self.nav_last.setMaximumWidth(60)
        self.nav_last.clicked.connect(self._on_nav_last)
        nav_layout.addWidget(self.nav_last)
        
        layout.addLayout(nav_layout)
        
        self.setLayout(layout)
    
    def _load_game(self, game_info: GameInfo) -> None:
        """
        Load and display a game.
        
        Args:
            game_info: GameInfo object with game data
        """
        # Create new game instance
        self.current_game = GoGame(game_info.board_size)
        
        # Play all moves
        for move_str, _ in game_info.moves:
            result = self.current_game.make_move(move_str)
            if result < 0:
                logger.warning(f"Invalid move {move_str} in game {self.gid}: {result}")
        
        # Update display
        self.board_widget.set_game(self.current_game)
        self.move_history_table.populate_from_game(self.current_game)
        self._update_game_info()
        self._update_move_label()
        self.move_history_table.highlight_current_move(self.current_game.current_move_number)
        
        logger.info(f"Loaded game {self.gid} with {len(game_info.moves)} moves")
    
    def update_game(self, game_info: GameInfo) -> None:
        """
        Update the game with new moves from the server.
        
        If the user is at the end of the game, auto-advance.
        Otherwise, maintain the current replay position.
        
        Args:
            game_info: Updated GameInfo object
        """
        self.game_info = game_info
        
        if not self.current_game:
            self._load_game(game_info)
            return
        
        # Check if user is at the end
        total_moves = len(self.current_game.list_moves())
        at_end = self.current_game.current_move_number >= total_moves
        
        # Reload game with new moves
        self._load_game(game_info)
        
        # If user was at end, move to new end
        if at_end:
            self._on_nav_last()
        
        logger.debug(f"Updated game {self.gid}, now {len(game_info.moves)} moves")
    
    def _update_game_info(self) -> None:
        """Update the game info label."""
        status_text = f"White: {self.game_info.white_player} vs Black: {self.game_info.black_player}\n"
        status_text += f"Board: {self.game_info.board_size}x{self.game_info.board_size} | Komi: {self.game_info.komi}"
        if self.game_info.result:
            status_text += f" | Result: {self.game_info.result}"
        
        self.game_info_label.setText(status_text)
    
    def _update_move_label(self) -> None:
        """Update the move counter label."""
        if self.current_game:
            total = max(self.current_game.history.keys()) if self.current_game.history else 0
            current = self.current_game.current_move_number
            self.move_label.setText(f"Move: {current}/{total}")
        else:
            self.move_label.setText("Move: 0/0")
    
    def _on_nav_first(self) -> None:
        """Go to first move."""
        if self.current_game:
            self.current_game.undo_all()
            self.board_widget.sync_board()
            self._update_move_label()
            self.move_history_table.highlight_current_move(self.current_game.current_move_number)
            self.move_history_table.scroll_to_top()
    
    def _on_nav_prev(self) -> None:
        """Go to previous move."""
        if self.current_game:
            self.current_game.undo_move()
            self.board_widget.sync_board()
            self._update_move_label()
            self.move_history_table.highlight_current_move(self.current_game.current_move_number)
    
    def _on_nav_next(self) -> None:
        """Go to next move."""
        if self.current_game:
            total_moves = max(self.current_game.history.keys()) if self.current_game.history else 0
            if self.current_game.current_move_number < total_moves:
                self.current_game.current_move_number += 1
                self.current_game.board = self.current_game.history[self.current_game.current_move_number].copy()
                self.board_widget.sync_board()
                self._update_move_label()
                self.move_history_table.highlight_current_move(self.current_game.current_move_number)
    
    def _on_nav_last(self) -> None:
        """Go to last move."""
        if self.current_game:
            total_moves = max(self.current_game.history.keys()) if self.current_game.history else 0
            if self.current_game.current_move_number < total_moves:
                self.current_game.current_move_number = total_moves
                self.current_game.board = self.current_game.history[total_moves].copy()
                self.board_widget.sync_board()
                self._update_move_label()
                self.move_history_table.highlight_current_move(self.current_game.current_move_number)
    
    def _on_move_table_clicked(self, move_number: int) -> None:
        """
        Handle a click on a move in the move history table.
        
        Updates the board to show the game position after the clicked move.
        
        Args:
            move_number: The move number that was clicked (0-indexed)
        """
        if not self.current_game:
            return
        
        # Get the total number of moves from the game history
        # Use history keys, not list_moves(), because list_moves() only returns moves up to current_move_number
        total_moves = max(self.current_game.history.keys()) if self.current_game.history else 0
        
        # Validate the move number is within range
        if move_number >= total_moves:
            logger.warning(f"Move {move_number} out of range (total: {total_moves})")
            return
        
        # Update the game position to the clicked move (position after the move is played)
        self.current_game.current_move_number = move_number + 1
        self.current_game.board = self.current_game.history[move_number + 1].copy()
        
        # Update the display
        self.board_widget.sync_board()
        self._update_move_label()
        self.move_history_table.highlight_current_move(self.current_game.current_move_number)
        
        logger.debug(f"Navigated to move {move_number} via table click")
    
    def get_tab_title(self) -> str:
        """
        Get the title to display on the tab.
        
        Returns:
            Game ID only
        """
        return str(self.gid)
