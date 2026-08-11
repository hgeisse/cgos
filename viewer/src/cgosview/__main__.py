"""
Application entry point for CGOSVIEW.

Handles initialization and startup of the GUI application.
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main() -> int:
    """
    Main application entry point.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    logger.info("Starting CGOSVIEW")
    
    try:
        # Parse command-line arguments
        from cgosview.config import get_config
        config = get_config()
        
        logger.info(f"Server: {config.server}:{config.port}")
        logger.info(f"Max games: {config.max_games}")
        
        # Import PyQt6 components
        from PyQt6.QtWidgets import QApplication
        from cgosview.gui.main_window import MainWindow
        
        # Create application
        app = QApplication(sys.argv)
        
        # Create and show main window with config
        window = MainWindow(config)
        window.show()
        
        # Run event loop
        exit_code = app.exec()
        
        logger.info("Application closed successfully")
        return exit_code
    
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Install dependencies with: pip install -e .[dev]")
        return 1
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
