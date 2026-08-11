"""
Threading utilities for running asyncio event loop in separate thread.

Provides helpers for running async code alongside PyQt6 GUI.
"""

import asyncio
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class AsyncioThread(threading.Thread):
    """
    Thread that runs an asyncio event loop.
    
    Allows async operations to run in a separate thread while the main thread
    handles Qt GUI operations. Communication between threads happens via
    callbacks that emit Qt signals.
    
    Example:
        async_thread = AsyncioThread()
        async_thread.start()
        
        # Later, run async code
        async_thread.run_async(some_async_function())
        
        # Stop thread
        async_thread.stop()
    """
    
    def __init__(self):
        """Initialize async thread."""
        super().__init__(daemon=True)
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = threading.Event()
        self._stop_event = threading.Event()
        logger.info("AsyncioThread initialized")
    
    def run(self) -> None:
        """Run the event loop (called by thread.start())."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        logger.info("AsyncioThread event loop started")
        
        try:
            while not self._stop_event.is_set():
                try:
                    self.loop.run_until_complete(asyncio.sleep(0.1))
                except Exception as e:
                    logger.error(f"Error in event loop: {e}")
        finally:
            try:
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception as e:
                logger.debug(f"Error cleaning up tasks: {e}")
            finally:
                self.loop.close()
                logger.info("AsyncioThread event loop closed")
    
    def run_async(self, coro):
        """
        Schedule a coroutine to run in the event loop.
        
        Args:
            coro: Coroutine to run
        
        Returns:
            asyncio.Task for the scheduled coroutine
        """
        self._ready.wait()  # Wait for loop to be ready
        
        if self.loop is None or self._stop_event.is_set():
            logger.error("Event loop not ready")
            return None
        
        return asyncio.run_coroutine_threadsafe(coro, self.loop)
    
    def stop(self) -> None:
        """Stop the event loop and thread, and wait for it to finish."""
        if not self._stop_event.is_set():
            self._stop_event.set()
            logger.info("AsyncioThread stop requested")
            # Wait for the thread to actually finish before returning
            self.join(timeout=5.0)
            if self.is_alive():
                logger.warning("AsyncioThread did not stop within timeout")


def create_async_callback_wrapper(
    signals_obj: object,
    slot_name: str
) -> Callable:
    """
    Create a wrapper that calls a Qt signal from an async context.
    
    This is used to safely emit Qt signals from the network thread.
    
    Args:
        signals_obj: Object with PyQt signals (e.g., NetworkSignals)
        slot_name: Name of the signal attribute (e.g., 'game_added')
    
    Returns:
        Callable that takes the signal argument(s) and emits the signal
    
    Example:
        game_added_wrapper = create_async_callback_wrapper(signals, 'game_added')
        client.on_game_added = game_added_wrapper
    """
    def wrapper(*args, **kwargs):
        signal = getattr(signals_obj, slot_name)
        signal.emit(*args, **kwargs)
    
    return wrapper
