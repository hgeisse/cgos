"""
Custom widget for rendering Go board and stones.

Displays the game board with grid, stones, and coordinates.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QPixmap
from PyQt6.QtCore import Qt, QSize
import os
import logging

from cgosview.game.gogame import GoGame, Stone

logger = logging.getLogger(__name__)


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
        
        self.board_size = size
        self.game: GoGame | None = None
        self.board: list[int] = [Stone.EMPTY] * (size * size)
        
        # Calculate widget size
        self.canvas_size = self.BOARD_OFFSET * 2 + (size - 1) * self.SQUARE_SIZE
        self.setMinimumSize(QSize(self.canvas_size + 20, self.canvas_size + 20))
        
        # Load textures from resources directory
        self.wood_texture = None
        self.black_stone = None
        self.white_stone = None
        resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../resources")
        
        # Load wood texture
        wood_path = os.path.join(resources_dir, "wood.png")
        if os.path.exists(wood_path):
            self.wood_texture = QPixmap(wood_path)
            if not self.wood_texture.isNull():
                logger.info(f"Loaded wood texture from: {wood_path}")
            else:
                logger.warning(f"Wood texture file exists but could not be loaded: {wood_path}")
        else:
            logger.warning(f"Could not find wood texture at: {wood_path}")
        
        # Load stone images
        bstone_path = os.path.join(resources_dir, "bstone.png")
        if os.path.exists(bstone_path):
            self.black_stone = QPixmap(bstone_path)
            if not self.black_stone.isNull():
                logger.info(f"Loaded black stone from: {bstone_path}")
            else:
                logger.warning(f"Black stone file exists but could not be loaded: {bstone_path}")
        else:
            logger.warning(f"Could not find black stone at: {bstone_path}")
        
        wstone_path = os.path.join(resources_dir, "wstone.png")
        if os.path.exists(wstone_path):
            self.white_stone = QPixmap(wstone_path)
            if not self.white_stone.isNull():
                logger.info(f"Loaded white stone from: {wstone_path}")
            else:
                logger.warning(f"White stone file exists but could not be loaded: {wstone_path}")
        else:
            logger.warning(f"Could not find white stone at: {wstone_path}")
        
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
        self.board_size = game.size
        self.board = game.get_board()
        
        # Update coordinate labels for the new board size
        self.columns = [chr(ord('A') + i) if i < 8 else chr(ord('B') + i) 
                       for i in range(25)][:game.size]
        self.rows = [str(i) for i in range(game.size, 0, -1)]
        
        self.update()
    
    def sync_board(self) -> None:
        """
        Synchronize the widget's board state with the current game state.
        
        Call this when the game state has changed (e.g., after navigation)
        to update the displayed board before repainting.
        """
        if self.game:
            self.board = self.game.get_board()
            self.update()
    
    def paintEvent(self, event) -> None:
        """
        Paint the board.
        
        Args:
            event: Paint event
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background (white/transparent)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        
        # Draw board square background with border around grid and coordinates
        board_square_size = (self.board_size - 1) * self.SQUARE_SIZE
        border = 35
        board_rect_x = self.BOARD_OFFSET - border
        board_rect_y = self.BOARD_OFFSET - border
        board_rect_size = board_square_size + (2 * border)
        
        # Draw wood texture or fallback to solid color
        if self.wood_texture and not self.wood_texture.isNull():
            # Set clip region to board rectangle to prevent tiles from extending beyond
            painter.setClipRect(board_rect_x, board_rect_y, board_rect_size, board_rect_size)
            # Tile the wood texture across the board square
            texture_size = self.wood_texture.width()
            for y in range(board_rect_y, board_rect_y + board_rect_size, texture_size):
                for x in range(board_rect_x, board_rect_x + board_rect_size, texture_size):
                    painter.drawPixmap(x, y, self.wood_texture)
            painter.setClipRect(self.rect())  # Reset clip region
        else:
            # Fallback to solid color if texture not available
            painter.fillRect(board_rect_x, board_rect_y, board_rect_size, board_rect_size, self.board_color)
        
        # Draw board grid
        self._draw_board(painter)
        
        # Draw stones
        self._draw_stones(painter)
        
        # Draw coordinates
        self._draw_coordinates(painter)
        
        # Draw handicap points (for full boards)
        if self.board_size >= 7:
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
        for i in range(self.board_size):
            x = self.BOARD_OFFSET + i * self.SQUARE_SIZE
            y1 = self.BOARD_OFFSET
            y2 = self.BOARD_OFFSET + (self.board_size - 1) * self.SQUARE_SIZE
            painter.drawLine(x, y1, x, y2)
        
        # Draw horizontal lines
        for i in range(self.board_size):
            y = self.BOARD_OFFSET + i * self.SQUARE_SIZE
            x1 = self.BOARD_OFFSET
            x2 = self.BOARD_OFFSET + (self.board_size - 1) * self.SQUARE_SIZE
            painter.drawLine(x1, y, x2, y)
    
    def _draw_stones(self, painter: QPainter) -> None:
        """
        Draw black and white stones on the board.
        
        Args:
            painter: QPainter instance
        """
        for y in range(self.board_size):
            for x in range(self.board_size):
                stone = self.board[y * self.board_size + x]
                
                if stone != Stone.EMPTY:
                    px = self.BOARD_OFFSET + x * self.SQUARE_SIZE
                    py = self.BOARD_OFFSET + y * self.SQUARE_SIZE
                    
                    # Draw stone from image or fallback to circle
                    if stone == Stone.BLACK and self.black_stone and not self.black_stone.isNull():
                        # Center the stone image on the intersection
                        stone_size = self.black_stone.width()
                        painter.drawPixmap(px - stone_size // 2, py - stone_size // 2, self.black_stone)
                    elif stone == Stone.WHITE and self.white_stone and not self.white_stone.isNull():
                        # Center the stone image on the intersection
                        stone_size = self.white_stone.width()
                        painter.drawPixmap(px - stone_size // 2, py - stone_size // 2, self.white_stone)
                    else:
                        # Fallback to drawn circle if image not available
                        if stone == Stone.BLACK:
                            painter.setBrush(QBrush(self.stone_black))
                            painter.setPen(QPen(QColor("#000000"), 1))
                        else:  # White
                            painter.setBrush(QBrush(self.stone_white))
                            painter.setPen(QPen(QColor("#000000"), 1))
                        
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
        for i in range(self.board_size):
            label = self.columns[i]
            x = self.BOARD_OFFSET + i * self.SQUARE_SIZE
            
            # Top row - 20 pixels above the board
            y_top = self.BOARD_OFFSET - 20
            painter.drawText(x - 5, y_top - 5, 10, 10, 
                            Qt.AlignmentFlag.AlignCenter, label)
            
            # Also at bottom - 20 pixels below the board
            y_bottom = self.BOARD_OFFSET + (self.board_size - 1) * self.SQUARE_SIZE + 20
            painter.drawText(x - 5, y_bottom - 5, 10, 10,
                            Qt.AlignmentFlag.AlignCenter, label)
        
        # Row labels (1-25)
        for i in range(self.board_size):
            label = self.rows[i]
            y = self.BOARD_OFFSET + i * self.SQUARE_SIZE
            x = self.BOARD_OFFSET - 25
            
            painter.drawText(x, y - 4, 15, 10,
                            Qt.AlignmentFlag.AlignCenter, label)
            
            # Also at right side
            x = self.BOARD_OFFSET + (self.board_size - 1) * self.SQUARE_SIZE + 20
            painter.drawText(x, y - 4, 15, 10,
                            Qt.AlignmentFlag.AlignCenter, label)
    
    def _draw_handicap_points(self, painter: QPainter) -> None:
        """
        Draw handicap points on the board.
        
        Handicap points are standard positions for Go handicaps.
        
        Args:
            painter: QPainter instance
        """
        # Handicap point positions for different board sizes (1-indexed coordinates)
        handicap_map = {
            7: [(3, 3), (3, 5), (5, 3), (5, 5)],
            9: [(3, 3), (3, 7), (7, 3), (7, 7), (5, 5)],
            13: [(4, 4), (4, 10), (10, 4), (10, 10), (7, 7)],
            15: [(4, 4), (4, 12), (12, 4), (12, 12), (8, 8)],
            19: [(4, 4), (4, 10), (4, 16), (10, 4), (10, 10), (10, 16),
                 (16, 4), (16, 10), (16, 16)],
        }
        
        if self.board_size not in handicap_map:
            return
        
        points = handicap_map[self.board_size]
        
        painter.setPen(QPen(self.line_color, 1))
        painter.setBrush(QBrush(self.line_color))
        
        for col, row in points:
            x = self.BOARD_OFFSET + (col - 1) * self.SQUARE_SIZE
            y = self.BOARD_OFFSET + (row - 1) * self.SQUARE_SIZE
            
            # Draw small circle
            painter.drawEllipse(x - 3, y - 3, 6, 6)
