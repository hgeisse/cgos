"""
Move History Table widget for displaying game moves in a table format.

Displays Black moves on the left and White moves on the right.
Updates automatically when the game is updated.
Clicking on a move emits a signal with the move number.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QMouseEvent

from cgosview.game.gogame import GoGame

logger = logging.getLogger(__name__)


class MoveHistoryTable(QTableWidget):
    """
    Table widget displaying game move history with two columns.
    
    Layout:
    - Left column: Black moves
    - Right column: White moves
    - One row per move pair (Black + White)
    
    Supports:
    - Visual highlighting of current move
    - Click to navigate to a specific move
    - Read-only display
    """
    
    # Signal emitted when a move is clicked
    move_clicked = pyqtSignal(int)  # Emits move number (0-indexed)
    
    def __init__(self):
        """Initialize the move history table."""
        super().__init__()
        
        # Setup table with 2 columns
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Black", "White"])
        
        # Hide row numbers
        self.verticalHeader().setVisible(False)
        
        # Make table read-only
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        
        # Set equal column widths
        self.setColumnWidth(0, 100)  # Black moves
        self.setColumnWidth(1, 100)  # White moves
        
        # Stretch columns equally to fill available space
        self.horizontalHeader().setStretchLastSection(False)
        from PyQt6.QtWidgets import QHeaderView
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # Font for table
        self.setFont(QFont("Consolas", 10))
        
        logger.debug("MoveHistoryTable initialized")
    
    def populate_from_game(self, game: Optional[GoGame]) -> None:
        """
        Populate the table from a GoGame instance.
        
        Organizes moves into rows with Black on left and White on right.
        Move numbers are prepended to each move (e.g., "23. D4").
        
        Args:
            game: GoGame instance with move history, or None to clear
        """
        self.setRowCount(0)  # Clear existing rows
        
        if not game:
            logger.debug("No game provided, table cleared")
            return
        
        # Get all moves from the game
        moves = game.list_moves()
        
        # Group moves into pairs (Black, White)
        for i in range(0, len(moves), 2):
            black_move = moves[i] if i < len(moves) else None
            white_move = moves[i + 1] if i + 1 < len(moves) else None
            
            self._add_move_row(i, black_move, white_move)
        
        logger.debug(f"Populated move history table with {len(moves)} moves")
    
    def _add_move_row(self, move_index: int, black_move: Optional[str], white_move: Optional[str]) -> None:
        """
        Add a single row to the table for a Black/White move pair.
        
        Args:
            move_index: Index of the first move (Black's move) in the pair (0-indexed)
            black_move: Black's move in algebraic notation or "PASS", or None
            white_move: White's move in algebraic notation or "PASS", or None
        """
        row = self.rowCount()
        self.insertRow(row)
        
        # Black move (left column) with move number
        if black_move:
            move_num = move_index + 1  # Convert to 1-indexed for display
            black_text = f"{move_num}. {black_move}"
            black_item = QTableWidgetItem(black_text)
            black_item.setFlags(black_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row, 0, black_item)
        
        # White move (right column) with move number
        if white_move:
            move_num = move_index + 2  # White's move is move_index + 1, displayed as move_index + 2
            white_text = f"{move_num}. {white_move}"
            white_item = QTableWidgetItem(white_text)
            white_item.setFlags(white_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row, 1, white_item)
    
    def highlight_current_move(self, move_number: int) -> None:
        """
        Highlight only the last move cell (the move that was just played).
        
        Args:
            move_number: Current move number (0-indexed, points to next move)
        """
        # Clear previous selection
        self.clearSelection()
        
        # If no moves have been played yet, don't highlight anything
        if move_number == 0:
            return
        
        # Get the last move number
        last_move = move_number - 1
        
        # Calculate row and column from last move number
        # Moves 0,1 are in row 0; moves 2,3 are in row 1, etc.
        # Even moves (0,2,4...) are Black (column 0)
        # Odd moves (1,3,5...) are White (column 1)
        row = last_move // 2
        col = last_move % 2
        
        # Select only the specific cell
        if 0 <= row < self.rowCount() and 0 <= col < 2:
            item = self.item(row, col)
            if item:
                self.setCurrentItem(item)
                self.scrollToItem(item)
        
        logger.debug(f"Highlighted last move {last_move} (row {row}, col {col})")
    
    def scroll_to_top(self) -> None:
        """Scroll the table to the top."""
        self.scrollToTop()
        logger.debug("Scrolled table to top")
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse click on the table.
        Emits move_clicked signal with the move number if a valid move cell is clicked.
        
        Args:
            event: The mouse press event
        """
        # Get the item at the clicked position
        item = self.itemAt(event.pos())
        
        # If clicked on a valid cell
        if item:
            row = self.row(item)
            col = self.column(item)
            
            # Convert row and column to move number
            # Row 0, Col 0 (Black) = Move 0
            # Row 0, Col 1 (White) = Move 1
            # Row 1, Col 0 (Black) = Move 2
            # Row 1, Col 1 (White) = Move 3
            move_number = row * 2 + col
            
            logger.debug(f"Move cell clicked: row {row}, col {col} -> move {move_number}")
            self.move_clicked.emit(move_number)
        
        # Call parent implementation to handle normal selection behavior
        super().mousePressEvent(event)
