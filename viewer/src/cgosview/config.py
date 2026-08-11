"""
Configuration management for CGOSVIEW.

Handles command-line arguments and default settings.
"""

import argparse
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class ViewerConfig:
    """Configuration for CGOSVIEW viewer."""
    
    server: str = "cgos-hg.de"
    """CGOS server hostname"""
    
    port: int = 6809
    """CGOS server port"""
    
    max_games: int = 10
    """Maximum number of concurrent games to track"""
    
    connection_timeout: float = 10.0
    """Connection timeout in seconds"""
    
    heartbeat_interval: float = 30.0
    """Heartbeat/ping interval in seconds"""
    
    reconnect_max_retries: int = 5
    """Maximum number of reconnection attempts"""
    
    reconnect_base_delay: float = 1.0
    """Base delay for exponential backoff (seconds)"""


def parse_args(args: Optional[list] = None) -> ViewerConfig:
    """
    Parse command-line arguments.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
    
    Returns:
        ViewerConfig with parsed values
    
    Example:
        >>> config = parse_args()
        >>> print(config.server)
        'cgos-hg.de'
        
        >>> config = parse_args(['other.server.com', '1234'])
        >>> print(config.server, config.port)
        'other.server.com' 1234
    """
    parser = argparse.ArgumentParser(
        prog='cgosview',
        description='CGOSVIEW - Go game viewer for CGOS server'
    )
    
    parser.add_argument(
        'server',
        nargs='?',
        default='cgos-hg.de',
        help='CGOS server hostname (default: cgos-hg.de)'
    )
    
    parser.add_argument(
        'port',
        nargs='?',
        type=int,
        default=6809,
        help='CGOS server port (default: 6809)'
    )
    
    parser.add_argument(
        '--max-games',
        type=int,
        default=10,
        help='Maximum concurrent games to track (default: 10)'
    )
    
    parser.add_argument(
        '--timeout',
        type=float,
        default=10.0,
        help='Connection timeout in seconds (default: 10.0)'
    )
    
    parser.add_argument(
        '--heartbeat',
        type=float,
        default=30.0,
        help='Heartbeat interval in seconds (default: 30.0)'
    )
    
    parsed = parser.parse_args(args)
    
    return ViewerConfig(
        server=parsed.server,
        port=parsed.port,
        max_games=parsed.max_games,
        connection_timeout=parsed.timeout,
        heartbeat_interval=parsed.heartbeat
    )


def get_config(args: Optional[list] = None) -> ViewerConfig:
    """
    Get viewer configuration from command-line arguments.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
    
    Returns:
        ViewerConfig instance
    """
    return parse_args(args)
