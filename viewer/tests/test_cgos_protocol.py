"""
Unit tests for CGOS protocol parsing.

Tests the new event-based protocol message parsing in cgos_client.py
"""

import pytest
from cgosview.network.cgos_client import CGOSClient


class TestCGOSProtocolParsing:
    """Test CGOS protocol message parsing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = CGOSClient()
    
    # MATCH message tests
    
    def test_parse_match_ongoing_game(self):
        """Test parsing MATCH message for ongoing game."""
        line = "match 12345 2026-08-01 14:30:00 19 6.5 AlphaGo(1950) Leela(1920) -"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, game_info = msg
        assert msg_type == "match"
        assert game_info.gid == 12345
        assert game_info.date == "2026-08-01"
        assert game_info.time == "14:30:00"
        assert game_info.board_size == 19
        assert game_info.komi == 6.5
        assert game_info.white_player == "AlphaGo"
        assert game_info.black_player == "Leela"
        assert game_info.result is None
        assert len(game_info.moves) == 0
    
    def test_parse_match_finished_game(self):
        """Test parsing MATCH message for finished game."""
        line = "match 12346 2026-08-01 14:35:00 9 0.0 KataGo(1850) Pachi(1800) W+2.5"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, game_info = msg
        assert msg_type == "match"
        assert game_info.gid == 12346
        assert game_info.result == "W+2.5"
    
    def test_parse_match_with_resignation(self):
        """Test parsing MATCH with resignation result."""
        line = "match 12347 2026-08-01 14:40:00 13 6.5 MoGo(1920) Fuego(1880) B+Resign"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, game_info = msg
        assert msg_type == "match"
        assert game_info.result == "B+Resign"
    
    def test_parse_match_with_draw(self):
        """Test parsing MATCH with draw result."""
        line = "match 12348 2026-08-01 15:00:00 19 6.5 Engine1(2000) Engine2(2000) Draw"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, game_info = msg
        assert msg_type == "match"
        assert game_info.result == "Draw"
    
    def test_parse_match_9x9_board(self):
        """Test parsing MATCH with 9x9 board."""
        line = "match 99999 2026-08-01 16:00:00 9 0.5 SmallEngine(1500) TinyBot(1400) -"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, game_info = msg
        assert game_info.board_size == 9
    
    # SETUP message tests
    
    def test_parse_setup_with_moves(self):
        """Test parsing SETUP message with initial moves."""
        line = "setup 12345 - - 19 6.5 AlphaGo(1950) Leela(1920) 300000 E5 2.45 D4 1.23 C4 0.89"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, moves) = msg
        assert msg_type == "setup"
        assert gid == 12345
        assert len(moves) == 3
        assert moves[0] == ("E5", 2.45)
        assert moves[1] == ("D4", 1.23)
        assert moves[2] == ("C4", 0.89)
    
    def test_parse_setup_no_moves(self):
        """Test parsing SETUP message with no moves."""
        line = "setup 12350 - - 19 6.5 Engine1(1900) Engine2(1850) 300000"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, moves) = msg
        assert msg_type == "setup"
        assert gid == 12350
        assert len(moves) == 0
    
    def test_parse_setup_odd_number_of_move_parts(self):
        """Test SETUP with odd number of move parts (incomplete last pair)."""
        line = "setup 12351 - - 19 6.5 Engine1(1900) Engine2(1850) 300000 E5 2.45 D4"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, moves) = msg
        assert len(moves) == 1  # D4 without time is ignored
        assert moves[0] == ("E5", 2.45)
    
    # UPDATE message tests
    
    def test_parse_update_basic(self):
        """Test parsing basic UPDATE message."""
        line = "update 12345 E5 298000"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, move, time) = msg
        assert msg_type == "update"
        assert gid == 12345
        assert move == "E5"
        assert time == 298.0  # Converted from 298000ms to 298s
    
    def test_parse_update_small_time(self):
        """Test UPDATE with small time value."""
        line = "update 12345 D4 50"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, move, time) = msg
        assert move == "D4"
        assert time == 50  # Small value kept as-is
    
    def test_parse_update_special_moves(self):
        """Test UPDATE with special moves (pass)."""
        line = "update 12345 pass 100000"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, move, time) = msg
        assert move == "pass"
    
    # GAMEOVER message tests
    
    def test_parse_gameover_point_win(self):
        """Test parsing GAMEOVER with point-based result."""
        line = "gameover 12345 W+3.5 299500 300000"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, result) = msg
        assert msg_type == "gameover"
        assert gid == 12345
        assert result == "W+3.5"
    
    def test_parse_gameover_resignation(self):
        """Test parsing GAMEOVER with resignation."""
        line = "gameover 12346 B+Resign 250000 300000"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, result) = msg
        assert result == "B+Resign"
    
    def test_parse_gameover_draw(self):
        """Test parsing GAMEOVER with draw."""
        line = "gameover 12347 Draw 150000 150000"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, result) = msg
        assert result == "Draw"
    
    # Edge cases and error handling
    
    def test_parse_comment_line(self):
        """Test that comment lines are ignored."""
        line = "# Server maintenance at 15:00 UTC"
        msg = self.client._parse_message(line)
        assert msg is None
    
    def test_parse_empty_line(self):
        """Test that empty lines are ignored."""
        msg = self.client._parse_message("")
        assert msg is None
    
    def test_parse_whitespace_only(self):
        """Test that whitespace-only lines are ignored."""
        msg = self.client._parse_message("   ")
        assert msg is None
    
    def test_parse_unknown_message_type(self):
        """Test that unknown message types are rejected."""
        line = "unknown 12345 some data"
        msg = self.client._parse_message(line)
        assert msg is None
    
    def test_parse_malformed_match_too_short(self):
        """Test that malformed MATCH messages are rejected."""
        line = "match 12345 2026-08-01"
        msg = self.client._parse_message(line)
        assert msg is None
    
    def test_parse_malformed_update_too_short(self):
        """Test that malformed UPDATE messages are rejected."""
        line = "update 12345"
        msg = self.client._parse_message(line)
        assert msg is None
    
    def test_parse_malformed_gameover_too_short(self):
        """Test that malformed GAMEOVER messages are rejected."""
        line = "gameover 12345"
        msg = self.client._parse_message(line)
        assert msg is None
    
    def test_parse_invalid_gid(self):
        """Test rejection of invalid GID."""
        line = "match notanumber 2026-08-01 14:30:00 19 6.5 A B -"
        msg = self.client._parse_message(line)
        assert msg is None
    
    def test_parse_invalid_board_size(self):
        """Test rejection of invalid board size."""
        line = "match 12345 2026-08-01 14:30:00 invalid 6.5 A B -"
        msg = self.client._parse_message(line)
        assert msg is None
    
    def test_parse_invalid_komi(self):
        """Test rejection of invalid komi."""
        line = "match 12345 2026-08-01 14:30:00 19 notafloat A B -"
        msg = self.client._parse_message(line)
        assert msg is None
    
    def test_parse_corner_move_a1(self):
        """Test parsing move at board corner A1."""
        line = "setup 12345 - - 19 6.5 A(1) B(1) 300000 A1 0.5"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, moves) = msg
        assert moves[0][0] == "A1"
    
    def test_parse_corner_move_s19(self):
        """Test parsing move at opposite corner S19."""
        line = "setup 12345 - - 19 6.5 A(1) B(1) 300000 S19 1.0"
        msg = self.client._parse_message(line)
        
        assert msg is not None
        msg_type, (gid, moves) = msg
        assert moves[0][0] == "S19"
    
    def test_extract_player_name_with_rating(self):
        """Test extraction of player name from player(rating) format."""
        name = CGOSClient._extract_player_name("AlphaGo(1950)")
        assert name == "AlphaGo"
    
    def test_extract_player_name_without_rating(self):
        """Test extraction of player name without rating."""
        name = CGOSClient._extract_player_name("Pachi")
        assert name == "Pachi"
    
    def test_extract_player_name_with_underscore(self):
        """Test extraction of player name with underscore."""
        name = CGOSClient._extract_player_name("Leela_Zero(1900)")
        assert name == "Leela_Zero"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
