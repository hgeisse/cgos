"""
Qt signals for thread-safe communication between network and GUI threads.

These signals allow the async network client (running in a separate thread)
to communicate with the Qt GUI (running on the main thread) in a thread-safe manner.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from cgosview.network.cgos_client import GameInfo, ConnectionState


class NetworkSignals(QObject):
    """
    Qt signals for network events.
    
    These signals are emitted by the network client to notify the GUI
    of important events. Connect these signals to slots in the main window.
    
    Example:
        signals = NetworkSignals()
        signals.game_added.connect(main_window.on_game_added)
        signals.connection_state_changed.connect(main_window.on_connection_state_changed)
    """
    
    # Emitted when a new game appears on the server
    # Args: GameInfo object
    game_added = pyqtSignal(GameInfo)
    
    # Emitted when a game receives new moves
    # Args: GameInfo object (updated with new moves)
    game_updated = pyqtSignal(GameInfo)
    
    # Emitted when a game finishes
    # Args: GameInfo object (with result field set)
    game_finished = pyqtSignal(GameInfo)
    
    # Emitted when connection state changes
    # Args: ConnectionState enum, error message (str or None)
    connection_state_changed = pyqtSignal(ConnectionState, object)  # object is str or None
    
    # Emitted when an error occurs
    # Args: error message (str)
    error_occurred = pyqtSignal(str)
