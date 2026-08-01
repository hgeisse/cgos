"""
Custom widget for rendering Go board and stones.

Displays the game board with grid, stones, and coordinates.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PyQt6.QtCore import Qt, QSize

from cgosview.game.gogame import GoGame, Stone


class GameBoardWidget(QWidget):
    """
    Custom widget for rendering a Go game board.
    
    Draws:
    - Board grid
    - Black and white stones
    - Board coordinates (A-Z columns, 1-25 rows)
    - Handicap points (if applicable)
    """
    
    # Board rendering constants
    STONE_SIZE = 22
    BOARD_OFFSET = 33
    SQUARE_SIZE = 22
    
    def __init__(self, size: int = 19):
        """
        Initialize board widget.
        
        Args:
            size: Board size (7-25)
        """
        super().__init__()
        
        self.size = size
        self.game: GoGame | None = None
        self.board: list[int] = [Stone.EMPTY] * (size * size)
        
        # Calculate widget size
        self.canvas_size = self.BOARD_OFFSET * 2 + (size - 1) * self.SQUARE_SIZE
        self.setMinimumSize(QSize(self.canvas_size + 20, self.canvas_size + 20))
        
        # Colors
        self.board_color = QColor("#D2B48C")
        self.line_color = QColor("#000000")
        self.stone_black = QColor("#000000")
        self.stone_white = QColor("#FFFFFF")
        self.text_color = QColor("#000000")
        
        # Coordinate labels
        self.columns = [chr(ord('A') + i) if i < 8 else chr(ord('B') + i) 
                       for i in range(25)][:size]
        self.rows = [str(i) for i in range(size, 0, -1)]
    
    def set_game(self, game: GoGame) -> None:
        """
        Set the game to display.
        
        Args:
            game: GoGame instance
        """
        self.game = game
        self.size = game.size
        self.board = game.get_board()
        self.update()
    
    def paintEvent(self, event) -> None:
        """
        Paint the board.
        
        Args:
            event: Paint event
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), self.board_color)
        
        # Draw board grid
        self._draw_board(painter)
        
        # Draw stones
        self._draw_stones(painter)
        
        # Draw coordinates
        self._draw_coordinates(painter)
        
        # Draw handicap points (for full boards)
        if self.size >= 7:
            self._draw_handicap_points(painter)
    
    def _draw_board(self, painter: QPainter) -> None:
        """
        Draw the board grid lines.
        
        Args:
            painter: QPainter instance
        """
        pen = QPen(self.line_color, 1)
        painter.setPen(pen)
        
        # Draw vertical lines
        for i in range(self.size):
            x = self.BOARD_OFFSET + i * self.SQUARE_SIZE
            y1 = self.BOARD_OFFSET
            y2 = self.BOARD_OFFSET + (self.size - 1) * self.SQUARE_SIZE
            painter.drawLine(x, y1, x, y2)
        
        # Draw horizontal lines
        for i in range(self.size):
            y = self.BOARD_OFFSET + i * self.SQUARE_SIZE
            x1 = self.BOARD_OFFSET
            x2 = self.BOARD_OFFSET + (self.size - 1) * self.SQUARE_SIZE
            painter.drawLine(x1, y, x2, y)
    
    def _draw_stones(self, painter: QPainter) -> None:
        """
        Draw black and white stones on the board.
        
        Args:
            painter: QPainter instance
        """
        for y in range(self.size):
            for x in range(self.size):
                stone = self.board[y * self.size + x]
                
                if stone != Stone.EMPTY:
                    px = self.BOARD_OFFSET + x * self.SQUARE_SIZE
                    py = self.BOARD_OFFSET + y * self.SQUARE_SIZE
                    
                    # Draw stone
                    if stone == Stone.BLACK:
                        painter.setBrush(QBrush(self.stone_black))
                        painter.setPen(QPen(QColor("#000000"), 1))
                    else:  # White
                        painter.setBrush(QBrush(self.stone_white))
                        painter.setPen(QPen(QColor("#000000"), 1))
                    
                    # Draw circle
                    radius = self.STONE_SIZE // 2 - 1
                    painter.drawEllipse(px - radius, py - radius, 
                                      radius * 2, radius * 2)
    
    def _draw_coordinates(self, painter: QPainter) -> None:
        """
        Draw board coordinates (file and rank labels).
        
        Args:
            painter: QPainter instance
        """
        font = QFont("Arial", 8)
        painter.setFont(font)
        painter.setPen(QPen(self.text_color))
        
        # Column labels (A-Z)
        for i in range(self.size):
            label = self.columns[i]
            x = self.BOARD_OFFSET + i * self.SQUARE_SIZE
            y = self.BOARD_OFFSET - 15
            
            painter.drawText(x - 5, y, 10, 10, 
                            Qt.AlignmentFlag.AlignCenter, label)
            
            # Also at bottom
            y = self.BOARD_OFFSET + (self.size - 1) * self.SQUARE_SIZE + 15
            painter.drawText(x - 5, y - 5, 10, 10,
                            Qt.AlignmentFlag.AlignCenter, label)
        
        # Row labels (1-25)
        for i in range(self.size):
            label = self.rows[i]
            y = self.BOARD_OFFSET + i * self.SQUARE_SIZE
            x = self.BOARD_OFFSET - 20
            
            painter.drawText(x, y - 4, 15, 10,
                            Qt.AlignmentFlag.AlignCenter, label)
            
            # Also at right side
            x = self.BOARD_OFFSET + (self.size - 1) * self.SQUARE_SIZE + 15
            painter.drawText(x, y - 4, 15, 10,
                            Qt.AlignmentFlag.AlignCenter, label)
    
    def _draw_handicap_points(self, painter: QPainter) -> None:
        """
        Draw handicap points on the board.
        
        Handicap points are standard positions for Go handicaps.
        
        Args:
            painter: QPainter instance
        """
        # Handicap point positions for different board sizes
        handicap_map = {
            7: [(2, 2), (2, 4), (4, 2), (4, 4)],
            9: [(2, 2), (2, 6), (6, 2), (6, 6), (4, 4)],
            13: [(3, 3), (3, 9), (9, 3), (9, 9), (6, 6)],
            15: [(3, 3), (3, 11), (11, 3), (11, 11), (7, 7)],
            19: [(3, 3), (3, 9), (3, 15), (9, 3), (9, 9), (9, 15),
                 (15, 3), (15, 9), (15, 15)],
        }
        
        if self.size not in handicap_map:
            return
        
        points = handicap_map[self.size]
        
        painter.setPen(QPen(self.line_color, 1))
        painter.setBrush(QBrush(self.line_color))
        
        for col, row in points:
            x = self.BOARD_OFFSET + (col - 1) * self.SQUARE_SIZE
            y = self.BOARD_OFFSET + (row - 1) * self.SQUARE_SIZE
            
            # Draw small circle
            painter.drawEllipse(x - 3, y - 3, 6, 6)
