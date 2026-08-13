"""
Main application window for CGOSVIEW.

Displays game list and provides controls for viewing games.
Integrates with async network client for real-time game streaming.
Supports multiple concurrent games in tabs (up to 10).
"""

import sys
import asyncio
import logging
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QSplitter, QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QColor

from cgosview.gui.game_tab import GameTab
from cgosview.network.cgos_client import CGOSClient, GameInfo, ConnectionState
from cgosview.gui.signals import NetworkSignals
from cgosview.utils.threading import AsyncioThread
from cgosview.config import ViewerConfig

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main application window for CGOSVIEW.
    
    Displays:
    - Server connection status
    - List of active games
    - Multiple game tabs (up to 10 concurrent games)
    - Navigation controls per tab
    
    Manages network connection and real-time game updates across all tabs.
    """
    
    # limit on how many game tabs can be open simultaneously
    MAX_OPEN_GAMES = 10
    
    def __init__(self, config: Optional[ViewerConfig] = None):
        """
        Initialize the main window.
        
        Args:
            config: ViewerConfig with server settings (optional)
        """
        super().__init__()
        
        self.setWindowTitle("CGOSVIEW - Go Game Viewer")
        self.setGeometry(100, 100, 1400, 800)
        
        # Configuration
        self.config = config or ViewerConfig()
        
        # Application state
        self.games_list: Dict[int, GameInfo] = {}
        self.open_tabs: Dict[int, GameTab] = {}  # gid -> GameTab widget
        self.is_closing = False  # Flag to prevent blocking dialogs during shutdown
        
        # Network components
        self.network_signals = NetworkSignals()
        self.client: Optional[CGOSClient] = None
        self.async_thread: Optional[AsyncioThread] = None
        self.receive_task = None
        
        # Create UI
        self._create_ui()
        
        # Apply styles
        self._apply_styles()
        
        # Connect network signals to GUI slots
        self._connect_signals()
        
        # Auto-connect on startup
        self._start_network_connection()
        
        logger.info("MainWindow initialized")
    
    def _connect_signals(self) -> None:
        """Connect network signals to GUI slots."""
        self.network_signals.game_added.connect(self._on_game_added)
        self.network_signals.game_updated.connect(self._on_game_updated)
        self.network_signals.game_finished.connect(self._on_game_finished)
        self.network_signals.connection_state_changed.connect(self._on_connection_state_changed)
        self.network_signals.error_occurred.connect(self._on_error)
    
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
        monospace_font = QFont("Consolas", 10)
        server_label = QLabel(f"Server: {self.config.server}      Port: {self.config.port}")
        server_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        server_label.setFont(monospace_font)
        server_label.setStyleSheet("font-weight: bold; padding: 5px 0px;")
        left_layout.addWidget(server_label)
        
        # Game list header with column titles
        monospace_font = QFont("Consolas", 10)
        header_label = QLabel("Game   White            Black            Result")
        header_label.setFont(monospace_font)
        header_label.setStyleSheet("font-weight: bold; padding: 5px 0px;")
        left_layout.addWidget(header_label)
        
        self.games_widget = QListWidget()
        self.games_widget.itemClicked.connect(self._on_game_selected)
        # Use monospace font for proper column alignment
        monospace_font = QFont("Consolas", 10)
        self.games_widget.setFont(monospace_font)
        left_layout.addWidget(self.games_widget)
        
        left_panel.setLayout(left_layout)
        
        # ===== RIGHT PANEL: Tab Widget =====
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        
        # Add panels to main layout with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.tab_widget)
        splitter.setSizes([455, 945])
        
        main_layout.addWidget(splitter)
        central.setLayout(main_layout)
    
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
    

    
    def _start_network_connection(self) -> None:
        """Start network client and connection in async thread."""
        try:
            logger.info(f"Attempting to connect to {self.config.server}:{self.config.port}")
            
            # Create async thread if not exists
            if self.async_thread is None:
                self.async_thread = AsyncioThread()
                self.async_thread.start()
            
            # Create client with callbacks connected to signals
            self.client = CGOSClient(
                host=self.config.server,
                port=self.config.port,
                connection_timeout=self.config.connection_timeout,
                heartbeat_interval=self.config.heartbeat_interval,
                max_retries=self.config.reconnect_max_retries,
                reconnect_base_delay=self.config.reconnect_base_delay,
                max_games=self.config.max_games
            )
            
            # Wire callbacks to signals
            def emit_game_added(game: GameInfo):
                self.network_signals.game_added.emit(game)
            
            def emit_game_updated(game: GameInfo):
                self.network_signals.game_updated.emit(game)
            
            def emit_game_finished(game: GameInfo):
                self.network_signals.game_finished.emit(game)
            
            def emit_connection_state_changed(state: ConnectionState, error: Optional[str]):
                self.network_signals.connection_state_changed.emit(state, error)
            
            self.client.on_game_added = emit_game_added
            self.client.on_game_updated = emit_game_updated
            self.client.on_game_finished = emit_game_finished
            self.client.on_connection_state_changed = emit_connection_state_changed
            
            # Schedule connection and receive in async thread
            async def connect_and_receive():
                if await self.client.connect_with_retry():
                    await self.client.receive_games()
                else:
                    self.network_signals.error_occurred.emit(
                        f"Failed to connect to {self.config.server}:{self.config.port}"
                    )
            
            if self.async_thread:
                self.receive_task = self.async_thread.run_async(connect_and_receive())
        
        except Exception as e:
            logger.error(f"Error starting network connection: {e}")
            self.network_signals.error_occurred.emit(f"Connection error: {e}")
    
    def _stop_network_connection(self) -> None:
        """Stop network client and async thread."""
        try:
            if self.client:
                # Schedule disconnect in async thread
                async def disconnect():
                    await self.client.disconnect()
                
                if self.async_thread:
                    self.async_thread.run_async(disconnect())
            
            if self.async_thread:
                self.async_thread.stop()
                self.async_thread = None
            
            self.client = None
            self.receive_task = None
            
            logger.info("Network connection stopped")
        
        except Exception as e:
            logger.error(f"Error stopping network connection: {e}")
    
    @pyqtSlot(GameInfo)
    def _on_game_added(self, game: GameInfo) -> None:
        """Handle new game added from server."""
        logger.info(f"Game added: {game.gid} - {game.white_player} vs {game.black_player}")
        
        # Store game
        self.games_list[game.gid] = game
        
        # Add to list at top (newest first)
        item_text = self._format_game_list_item(game)
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, game.gid)
        self.games_widget.insertItem(0, item)
        
        # Update colors
        self._update_game_list_item_color(item, game)
        
        # Auto-scroll to show new game
        self.games_widget.scrollToItem(item)
    
    @pyqtSlot(GameInfo)
    def _on_game_updated(self, game: GameInfo) -> None:
        """Handle game update (new moves) from server."""
        logger.debug(f"Game updated: {game.gid}, {len(game.moves)} moves")
        
        # Update stored game
        self.games_list[game.gid] = game
        
        # Update list item
        self._update_game_list_item(game)
        
        # If this game has an open tab, update it
        if game.gid in self.open_tabs:
            tab = self.open_tabs[game.gid]
            tab.update_game(game)
            # Update tab title with new move count
            tab_index = self.tab_widget.indexOf(tab)
            if tab_index >= 0:
                self.tab_widget.setTabText(tab_index, tab.get_tab_title())
    
    @pyqtSlot(GameInfo)
    def _on_game_finished(self, game: GameInfo) -> None:
        """Handle game finished from server."""
        logger.info(f"Game finished: {game.gid} - {game.result}")
        
        # Update stored game
        self.games_list[game.gid] = game
        
        # Update list item with finished styling
        self._update_game_list_item(game)
        
        # Update any open tab with finished game
        if game.gid in self.open_tabs:
            tab = self.open_tabs[game.gid]
            tab.update_game(game)
            # Update tab title to show result
            tab_index = self.tab_widget.indexOf(tab)
            if tab_index >= 0:
                self.tab_widget.setTabText(tab_index, tab.get_tab_title())
    
    @pyqtSlot(ConnectionState, object)
    def _on_connection_state_changed(self, state: ConnectionState, error: Optional[str]) -> None:
        """Handle connection state change."""
        if state == ConnectionState.CONNECTED:
            logger.info("Connected to server")
        elif state == ConnectionState.CONNECTING:
            logger.debug("Connecting to server...")
        elif state == ConnectionState.DISCONNECTED:
            logger.info("Disconnected from server")
        elif state == ConnectionState.ERROR:
            logger.error(f"Connection error: {error}")
            self._on_error(f"Connection error: {error or 'Unknown error'}")
    
    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        """Handle error from network client."""
        logger.error(f"Network error: {message}")
        # Don't show blocking dialogs if the application is closing
        # to avoid deadlock with thread shutdown
        if not self.is_closing:
            QMessageBox.warning(self, "Connection Error", message)
    
    def _on_game_selected(self, item: QListWidgetItem) -> None:
        """Handle game selection from list."""
        gid = item.data(Qt.ItemDataRole.UserRole)
        if gid and gid in self.games_list:
            self._open_or_switch_to_game_tab(gid)
    
    def _open_or_switch_to_game_tab(self, gid: int) -> None:
        """
        Open a new tab for the game, or switch to existing tab if already open.
        
        When opening a new tab, sends an observe command to the server to request
        the complete game data (including move list).
        
        Args:
            gid: Game ID to open/switch to
        """
        if gid not in self.games_list:
            return
        
        # If tab already exists, switch to it
        if gid in self.open_tabs:
            tab_index = self.tab_widget.indexOf(self.open_tabs[gid])
            if tab_index >= 0:
                self.tab_widget.setCurrentIndex(tab_index)
            logger.debug(f"Switched to existing tab for game {gid}")
            return
        
        # Check if we can open a new tab
        if len(self.open_tabs) >= self.MAX_OPEN_GAMES:
            QMessageBox.warning(
                self, 
                "Maximum Games Open",
                f"Maximum of {self.MAX_OPEN_GAMES} games can be open at once.\n"
                "Close a tab to open another game."
            )
            logger.warning(f"Cannot open game {gid}: maximum tabs reached")
            return
        
        # Create new tab
        game_info = self.games_list[gid]
        tab = GameTab(gid, game_info)
        
        # Add to tab widget
        self.open_tabs[gid] = tab
        tab_index = self.tab_widget.addTab(tab, tab.get_tab_title())
        self.tab_widget.setCurrentIndex(tab_index)
        
        logger.info(f"Opened new tab for game {gid}")
        
        # Send observe command to server to get complete game data (moves, result)
        if self.client and self.async_thread:
            self.async_thread.run_async(self.client.observe_game(gid))
    
    def _on_tab_close_requested(self, index: int) -> None:
        """
        Handle tab close button click.
        
        Args:
            index: Index of the tab to close
        """
        tab = self.tab_widget.widget(index)
        if isinstance(tab, GameTab):
            gid = tab.gid
            self.tab_widget.removeTab(index)
            if gid in self.open_tabs:
                del self.open_tabs[gid]
            logger.info(f"Closed tab for game {gid}")
    
    def _format_game_list_item(self, game: GameInfo) -> str:
        """
        Format game info for display in list.
        
        Args:
            game: GameInfo object
        
        Returns:
            Formatted string for list display
        """
        move_count = len(game.moves)
        status = game.result or f"{move_count} moves"
        return f"{game.gid:5d}  {game.white_player:15s}  {game.black_player:15s}  [{status}]"
    
    def _update_game_list_item(self, game: GameInfo) -> None:
        """
        Update a game list item with current game info.
        
        Args:
            game: GameInfo object to update
        """
        for i in range(self.games_widget.count()):
            item = self.games_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == game.gid:
                item.setText(self._format_game_list_item(game))
                self._update_game_list_item_color(item, game)
                break
    
    def _update_game_list_item_color(self, item: QListWidgetItem, game: GameInfo) -> None:
        """
        Update item color based on game status.
        
        In-progress games: normal text
        Finished games: different colors based on result
        
        Args:
            item: QListWidgetItem to update
            game: GameInfo with current status
        """
        if game.is_finished():
            # Game finished - use different colors
            if game.result:
                if game.result.startswith("W+"):
                    # White won
                    item.setForeground(QColor(100, 100, 100))  # Gray for finished
                elif game.result.startswith("B+"):
                    # Black won
                    item.setForeground(QColor(100, 100, 100))  # Gray for finished
                else:
                    # Draw or resignation
                    item.setForeground(QColor(100, 100, 100))  # Gray for finished
        else:
            # Game in progress - normal text
            item.setForeground(QColor(0, 0, 0))
    
    def closeEvent(self, event) -> None:
        """
        Handle window close event.
        
        Gracefully disconnects from the server before closing.
        
        Args:
            event: Close event
        """
        logger.info("Closing application")
        # Set flag BEFORE stopping network to prevent error dialogs during shutdown
        self.is_closing = True
        self._stop_network_connection()
        event.accept()
    



if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
