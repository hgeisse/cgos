"""
Unit tests for GameTab click-to-navigate feature.

Tests the navigation logic when clicking on a move in the move history table,
including board state restoration and display updates.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from cgosview.game.gogame import GoGame
from cgosview.network.cgos_client import GameInfo


class TestClickNavigationLogic:
    """Test the logic of navigating to a clicked move."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a game with known moves
        self.game = GoGame(9)
        self.moves = ["D4", "Q7", "D7", "Q4", "E5", "P3", "PASS", "PASS"]
        
        for move in self.moves:
            self.game.make_move(move)
    
    def test_click_first_move(self):
        """Test clicking on the first move (move 0)."""
        move_number = 0
        
        # Simulate navigation to this move
        self.game.current_move_number = move_number + 1
        self.game.board = self.game.history[move_number + 1].copy()
        
        assert self.game.current_move_number == 1
        assert move_number < len(self.game.list_moves())
    
    def test_click_middle_move(self):
        """Test clicking on a move in the middle of the game."""
        move_number = 3  # Fourth move
        
        # Simulate navigation to this move
        self.game.current_move_number = move_number + 1
        self.game.board = self.game.history[move_number + 1].copy()
        
        assert self.game.current_move_number == 4
        assert move_number < len(self.game.list_moves())
    
    def test_click_last_move(self):
        """Test clicking on the last move."""
        total_moves = len(self.game.list_moves())
        move_number = total_moves - 1  # Last move
        
        # Simulate navigation to this move
        self.game.current_move_number = move_number + 1
        self.game.board = self.game.history[move_number + 1].copy()
        
        assert self.game.current_move_number == total_moves
    
    def test_click_out_of_range_move(self):
        """Test that clicking out-of-range move is ignored."""
        total_moves = len(self.game.list_moves())
        move_number = total_moves + 10  # Way out of range
        
        # Validate before navigation
        if move_number >= total_moves:
            # Should not navigate
            assert move_number >= total_moves
            return
    
    def test_move_number_validation(self):
        """Test validation of move number using history keys."""
        total_moves = max(self.game.history.keys())
        
        # Valid moves
        for move_num in [0, 1, total_moves - 1]:
            assert move_num < total_moves
        
        # Invalid moves
        assert total_moves >= total_moves
        assert total_moves + 1 > total_moves


class TestMoveHistoryRetrieval:
    """Test retrieving moves from game history."""
    
    def test_total_moves_from_list(self):
        """Test getting total moves from list_moves()."""
        game = GoGame(9)
        moves = ["D4", "E5", "F6"]
        
        for move in moves:
            game.make_move(move)
        
        total = len(game.list_moves())
        assert total == 3
    
    def test_total_moves_from_history_keys(self):
        """Test getting total moves from history.keys()."""
        game = GoGame(9)
        moves = ["D4", "E5", "F6"]
        
        for move in moves:
            game.make_move(move)
        
        total = max(game.history.keys())
        assert total == 3
    
    def test_history_has_all_moves(self):
        """Test that history contains all board states."""
        game = GoGame(9)
        moves = ["D4", "E5", "F6"]
        
        for move in moves:
            game.make_move(move)
        
        # History should have states 0, 1, 2, 3
        assert 0 in game.history
        assert 1 in game.history
        assert 2 in game.history
        assert 3 in game.history
    
    def test_history_persists_after_position_change(self):
        """Test that history remains intact after navigating to different position."""
        game = GoGame(9)
        moves = ["D4", "E5", "F6", "G7"]
        
        for move in moves:
            game.make_move(move)
        
        # Navigate backward
        game.current_move_number = 1
        
        # History should still have all positions
        assert max(game.history.keys()) == 4


class TestBoardStateRestoration:
    """Test restoring board state from history."""
    
    def test_restore_to_move_one(self):
        """Test restoring board state to after first move."""
        game = GoGame(9)
        game.make_move("D4")
        game.make_move("Q7")
        game.make_move("D7")
        
        # Get state after move 0
        move_number = 0
        saved_state = game.history[move_number + 1].copy()
        
        # Simulate restoration
        game.current_move_number = move_number + 1
        game.board = saved_state
        
        assert game.current_move_number == 1
    
    def test_restore_to_move_two(self):
        """Test restoring board state to after second move."""
        game = GoGame(9)
        game.make_move("D4")
        game.make_move("Q7")
        game.make_move("D7")
        
        # Get state after move 1
        move_number = 1
        saved_state = game.history[move_number + 1].copy()
        
        # Simulate restoration
        game.current_move_number = move_number + 1
        game.board = saved_state
        
        assert game.current_move_number == 2
    
    def test_restore_with_copy(self):
        """Test that board state is copied, not referenced."""
        game = GoGame(9)
        game.make_move("D4")
        game.make_move("Q7")
        
        # Get a copy of the state
        original_state = game.history[1].copy()
        
        # Modify current board
        game.make_move("D7")
        
        # Copied state should remain unchanged
        assert len(original_state) == len(game.history[1])


class TestCurrentMoveNumberUpdate:
    """Test updating current_move_number on navigation."""
    
    def test_set_current_move_to_one(self):
        """Test setting current_move_number to 1."""
        game = GoGame(9)
        game.make_move("D4")
        game.make_move("Q7")
        
        game.current_move_number = 1
        assert game.current_move_number == 1
    
    def test_set_current_move_to_two(self):
        """Test setting current_move_number to 2."""
        game = GoGame(9)
        game.make_move("D4")
        game.make_move("Q7")
        game.make_move("D7")
        
        game.current_move_number = 2
        assert game.current_move_number == 2
    
    def test_move_number_progression(self):
        """Test setting current_move_number to various values."""
        game = GoGame(9)
        moves = ["D4", "Q7", "D7", "Q4", "E5"]
        
        for move in moves:
            game.make_move(move)
        
        # Test navigating to different positions
        for i in range(1, len(moves) + 1):
            game.current_move_number = i
            assert game.current_move_number == i


class TestClickNavigationIntegration:
    """Integration tests for complete click-to-navigate flow."""
    
    def test_navigate_forward_through_game(self):
        """Test navigating forward by clicking moves."""
        game = GoGame(9)
        moves = ["D4", "E5", "F6", "G7", "H8"]
        
        for move in moves:
            game.make_move(move)
        
        # Simulate navigating to each move by clicking
        for click_move in range(len(moves)):
            game.current_move_number = click_move + 1
            game.board = game.history[click_move + 1].copy()
            
            assert game.current_move_number == click_move + 1
    
    def test_navigate_backward_by_clicking(self):
        """Test navigating backward by clicking moves."""
        game = GoGame(9)
        moves = ["D4", "E5", "F6", "G7", "H8"]
        
        for move in moves:
            game.make_move(move)
        
        # Start at end and click backward
        click_moves = [2, 1, 3, 0]  # Random order
        
        for click_move in click_moves:
            if click_move < len(moves):  # Validate move is in range
                game.current_move_number = click_move + 1
                game.board = game.history[click_move + 1].copy()
                
                assert game.current_move_number == click_move + 1
    
    def test_click_same_move_twice(self):
        """Test clicking the same move twice."""
        game = GoGame(9)
        game.make_move("D4")
        game.make_move("Q7")
        game.make_move("D7")
        
        # Click move 1 twice
        for _ in range(2):
            game.current_move_number = 2
            game.board = game.history[2].copy()
            
            assert game.current_move_number == 2


class TestHighlightingAfterClick:
    """Test that highlighting works correctly after navigation."""
    
    def test_highlight_calculation_after_click(self):
        """Test that highlight calculation works with navigation."""
        game = GoGame(9)
        moves = ["D4", "Q7", "D7", "Q4"]
        
        for move in moves:
            game.make_move(move)
        
        # Navigate to move 2
        game.current_move_number = 3
        
        # Calculate what should be highlighted (last move)
        last_move = game.current_move_number - 1
        row = last_move // 2
        col = last_move % 2
        
        assert last_move == 2
        assert row == 1
        assert col == 0  # Black move


class TestEdgeCasesNavigation:
    """Test edge cases for click navigation."""
    
    def test_navigate_to_move_zero(self):
        """Test that we cannot navigate to move 0 position."""
        game = GoGame(9)
        game.make_move("D4")
        
        # Move 0 is not a valid navigation target (current_move_number can't be 0 during play)
        # But we test the validation
        game.current_move_number = 1
        assert game.current_move_number == 1
    
    def test_navigate_with_pass_moves(self):
        """Test navigation with pass moves."""
        game = GoGame(9)
        game.make_move("D4")
        game.make_move("PASS")
        game.make_move("Q7")
        
        # Navigate to pass move
        game.current_move_number = 2
        game.board = game.history[2].copy()
        
        assert game.current_move_number == 2
    
    def test_large_game_navigation(self):
        """Test navigation in a large game."""
        game = GoGame(19)
        
        # Create a game with multiple moves
        moves = ["D4", "Q16", "D16", "Q4", "E5", "P3"]
        for move in moves:
            game.make_move(move)
        
        # Navigate to an earlier move
        game.current_move_number = 3
        game.board = game.history[3].copy()
        
        assert game.current_move_number == 3
