"""
Main application window for CGOSVIEW.

Displays game list and provides controls for viewing games.
"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QSplitter, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon

from cgosview.game.gogame import GoGame
from cgosview.gui.board_widget import GameBoardWidget


class MainWindow(QMainWindow):
    """
    Main application window for CGOSVIEW.
    
    Displays:
    - Server connection status
    - List of active games
    - Currently selected game board
    - Navigation controls
    """
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        self.setWindowTitle("CGOSVIEW - Go Game Viewer")
        self.setGeometry(100, 100, 1200, 800)
        
        # Application state
        self.current_game: GoGame | None = None
        self.games_list: dict = {}
        
        # Create UI
        self._create_ui()
        
        # Apply styles
        self._apply_styles()
        
        # Create status timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        
    def _create_ui(self) -> None:
        """Create user interface elements."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout()
        
        # ===== LEFT PANEL: Game List =====
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # Server info
        server_label = QLabel("CGOS Server")
        server_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        left_layout.addWidget(server_label)
        
        self.server_status = QLabel("Status: Disconnected")
        self.server_status.setStyleSheet("color: red;")
        left_layout.addWidget(self.server_status)
        
        # Connection buttons
        button_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        button_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.disconnect_btn.setEnabled(False)
        button_layout.addWidget(self.disconnect_btn)
        
        left_layout.addLayout(button_layout)
        
        # Games list
        games_label = QLabel("Active Games")
        games_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        left_layout.addWidget(games_label)
        
        self.games_widget = QListWidget()
        self.games_widget.itemClicked.connect(self._on_game_selected)
        left_layout.addWidget(self.games_widget)
        
        left_panel.setLayout(left_layout)
        
        # ===== RIGHT PANEL: Game Board =====
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # Game info
        self.game_info = QLabel(
            "Select a game from the list\n"
            "White: N/A vs Black: N/A"
        )
        self.game_info.setFont(QFont("Arial", 10))
        self.game_info.setStyleSheet("background-color: #f0f0f0; padding: 10px;")
        right_layout.addWidget(self.game_info)
        
        # Board widget
        self.board_widget = GameBoardWidget(19)
        self.board_widget.setMinimumSize(QSize(600, 600))
        right_layout.addWidget(self.board_widget)
        
        # Navigation buttons
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
        
        right_layout.addLayout(nav_layout)
        
        right_panel.setLayout(right_layout)
        
        # Add panels to main layout with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)
        central.setLayout(main_layout)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def _apply_styles(self) -> None:
        """Apply application styles."""
        style = """
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QPushButton {
                background-color: #e0e0e0;
                border: 1px solid #999;
                border-radius: 3px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #999;
            }
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """
        self.setStyleSheet(style)
    
    def _on_connect(self) -> None:
        """Handle connect button click."""
        self.server_status.setText("Status: Connecting...")
        self.server_status.setStyleSheet("color: orange;")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        
        # Add sample games for testing
        self._add_sample_games()
        
        self.status_timer.start(1000)
    
    def _on_disconnect(self) -> None:
        """Handle disconnect button click."""
        self.server_status.setText("Status: Disconnected")
        self.server_status.setStyleSheet("color: red;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        
        self.status_timer.stop()
    
    def _on_game_selected(self, item: QListWidgetItem) -> None:
        """Handle game selection from list."""
        game_name = item.text()
        # Extract game ID from display name
        parts = game_name.split(" - ")
        if len(parts) >= 1:
            try:
                gid = int(parts[0])
                self._load_game(gid)
            except ValueError:
                pass
    
    def _load_game(self, gid: int) -> None:
        """Load and display a game."""
        if gid not in self.games_list:
            return
        
        game_info = self.games_list[gid]
        
        # Create new game instance
        self.current_game = GoGame(game_info["size"])
        
        # Play moves if available
        for move in game_info.get("moves", []):
            self.current_game.make_move(move)
        
        # Update display
        self.board_widget.set_game(self.current_game)
        
        self.game_info.setText(
            f"White: {game_info['white']} vs Black: {game_info['black']}\n"
            f"Board: {game_info['size']}x{game_info['size']} | "
            f"Komi: {game_info['komi']}"
        )
        
        self._update_move_label()
        self.statusBar().showMessage(f"Loaded game {gid}")
    
    def _add_sample_games(self) -> None:
        """Add sample games for demonstration."""
        sample_games = [
            {"gid": 1, "white": "Engine1", "black": "Engine2", "size": 19, "komi": 6.5, "moves": []},
            {"gid": 2, "white": "Player1", "black": "Player2", "size": 9, "komi": 6.5, "moves": []},
            {"gid": 3, "white": "Bot_A", "black": "Bot_B", "size": 13, "komi": 7.5, "moves": []},
        ]
        
        self.games_list = {}
        self.games_widget.clear()
        
        for game in sample_games:
            self.games_list[game["gid"]] = game
            item_text = f"{game['gid']} - {game['white']} vs {game['black']}"
            self.games_widget.addItem(item_text)
    
    def _update_status(self) -> None:
        """Update connection status."""
        self.server_status.setText("Status: Connected")
        self.server_status.setStyleSheet("color: green;")
    
    def _update_move_label(self) -> None:
        """Update the move counter label."""
        if self.current_game:
            total = len(self.current_game.list_moves())
            current = self.current_game.current_move_number
            self.move_label.setText(f"Move: {current}/{total}")
        else:
            self.move_label.setText("Move: 0/0")
    
    def _on_nav_first(self) -> None:
        """Go to first move."""
        if self.current_game:
            self.current_game.undo_all()
            self.board_widget.update()
            self._update_move_label()
    
    def _on_nav_prev(self) -> None:
        """Go to previous move."""
        if self.current_game:
            self.current_game.undo_move()
            self.board_widget.update()
            self._update_move_label()
    
    def _on_nav_next(self) -> None:
        """Go to next move."""
        QMessageBox.information(self, "Info", "Next move feature coming soon")
    
    def _on_nav_last(self) -> None:
        """Go to last move."""
        QMessageBox.information(self, "Info", "Last move feature coming soon")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
