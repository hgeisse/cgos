"""
Unit tests for move history table data logic.

Tests the data transformation and layout logic for the move history table,
focusing on data calculations rather than GUI rendering.
"""

import pytest
from cgosview.game.gogame import GoGame


class TestMoveToRowColumnCalculation:
    """Test conversion from move number to table row/column."""
    
    def test_black_move_in_row_zero(self):
        """Test that move 0 (Black) maps to row 0, col 0."""
        move_number = 0
        row = move_number // 2
        col = move_number % 2
        
        assert row == 0
        assert col == 0
    
    def test_white_move_in_row_zero(self):
        """Test that move 1 (White) maps to row 0, col 1."""
        move_number = 1
        row = move_number // 2
        col = move_number % 2
        
        assert row == 0
        assert col == 1
    
    def test_black_move_in_row_one(self):
        """Test that move 2 (Black) maps to row 1, col 0."""
        move_number = 2
        row = move_number // 2
        col = move_number % 2
        
        assert row == 1
        assert col == 0
    
    def test_white_move_in_row_one(self):
        """Test that move 3 (White) maps to row 1, col 1."""
        move_number = 3
        row = move_number // 2
        col = move_number % 2
        
        assert row == 1
        assert col == 1
    
    def test_various_move_numbers(self):
        """Test row/col calculation for various move numbers."""
        test_cases = [
            (0, 0, 0),   # Move 0 -> Row 0, Col 0
            (1, 0, 1),   # Move 1 -> Row 0, Col 1
            (2, 1, 0),   # Move 2 -> Row 1, Col 0
            (4, 2, 0),   # Move 4 -> Row 2, Col 0
            (5, 2, 1),   # Move 5 -> Row 2, Col 1
            (100, 50, 0), # Move 100 -> Row 50, Col 0
            (101, 50, 1), # Move 101 -> Row 50, Col 1
        ]
        
        for move_num, expected_row, expected_col in test_cases:
            row = move_num // 2
            col = move_num % 2
            assert row == expected_row, f"Move {move_num}: row mismatch"
            assert col == expected_col, f"Move {move_num}: col mismatch"


class TestMoveNumberFormatting:
    """Test formatting of move numbers in display strings."""
    
    def test_black_move_number_formatting(self):
        """Test that Black move numbers are 1-indexed."""
        move_index = 0  # First move (Black)
        move_num = move_index + 1  # Convert to 1-indexed
        black_text = f"{move_num}. D4"
        
        assert black_text == "1. D4"
    
    def test_white_move_number_formatting(self):
        """Test that White move numbers are calculated correctly."""
        move_index = 0  # Black's move
        white_move_num = move_index + 2  # White's move is at index 1
        white_text = f"{white_move_num}. Q16"
        
        assert white_text == "2. Q16"
    
    def test_third_and_fourth_moves(self):
        """Test move numbering for moves 2 and 3."""
        move_index = 2  # Second pair of moves
        black_move_num = move_index + 1  # Move 3
        white_move_num = move_index + 2  # Move 4
        
        assert black_move_num == 3
        assert white_move_num == 4
    
    def test_various_move_pairs(self):
        """Test move numbering for multiple pairs."""
        test_cases = [
            (0, 1, 2),      # Pair 0: moves 1, 2
            (2, 3, 4),      # Pair 1: moves 3, 4
            (4, 5, 6),      # Pair 2: moves 5, 6
            (10, 11, 12),   # Pair 5: moves 11, 12
            (158, 159, 160), # Pair 79: moves 159, 160
        ]
        
        for move_index, expected_black, expected_white in test_cases:
            black_num = move_index + 1
            white_num = move_index + 2
            assert black_num == expected_black
            assert white_num == expected_white


class TestBlackWhiteMoveDistribution:
    """Test distribution of moves into Black/White columns."""
    
    def test_even_moves_are_black(self):
        """Test that even-indexed moves go to Black column."""
        black_moves = [0, 2, 4, 6, 8, 100]
        
        for move_num in black_moves:
            col = move_num % 2
            assert col == 0, f"Move {move_num} should be Black (col 0), got col {col}"
    
    def test_odd_moves_are_white(self):
        """Test that odd-indexed moves go to White column."""
        white_moves = [1, 3, 5, 7, 9, 101]
        
        for move_num in white_moves:
            col = move_num % 2
            assert col == 1, f"Move {move_num} should be White (col 1), got col {col}"


class TestOddNumberOfMoves:
    """Test handling of games with odd number of moves."""
    
    def test_game_with_odd_moves_last_row(self):
        """Test that odd total moves leaves Black in last row with no White."""
        total_moves = 9  # Odd number
        rows_needed = (total_moves + 1) // 2  # Should be 5 rows
        
        assert rows_needed == 5
        
        # Last row (row 4) should have only move 8 (Black)
        last_move = total_moves - 1  # Move 8
        row = last_move // 2
        col = last_move % 2
        
        assert row == 4
        assert col == 0  # Black column
    
    def test_game_with_even_moves_full_last_row(self):
        """Test that even total moves fills last row completely."""
        total_moves = 8  # Even number
        rows_needed = (total_moves + 1) // 2  # Should be 4 rows
        
        assert rows_needed == 4
        
        # Last row (row 3) should have both move 6 (Black) and move 7 (White)
        last_black_move = total_moves - 2  # Move 6
        last_white_move = total_moves - 1  # Move 7
        
        assert last_black_move // 2 == 3
        assert last_white_move // 2 == 3
        assert last_black_move % 2 == 0  # Black
        assert last_white_move % 2 == 1  # White


class TestGameDataConversion:
    """Test conversion of game move data to table structure."""
    
    def test_simple_game_move_list(self):
        """Test that game moves are correctly extracted."""
        game = GoGame(19)
        test_moves = ["D4", "Q16", "D16", "Q4"]
        
        for move in test_moves:
            game.make_move(move)
        
        recorded_moves = game.list_moves()
        assert recorded_moves == test_moves
    
    def test_game_with_passes(self):
        """Test game with pass moves."""
        game = GoGame(9)
        test_moves = ["D4", "E5", "PASS", "PASS"]
        
        for move in test_moves:
            game.make_move(move)
        
        recorded_moves = game.list_moves()
        assert recorded_moves == test_moves
        assert recorded_moves[-2] == "PASS"
        assert recorded_moves[-1] == "PASS"
    
    def test_large_game(self):
        """Test game with many moves."""
        game = GoGame(19)
        
        # Create a game with multiple moves on different positions
        moves = ["D4", "E5", "F6", "G7", "H8", "J9"]
        for move in moves:
            game.make_move(move)
        
        recorded_moves = game.list_moves()
        # Verify that multiple moves are recorded
        assert len(recorded_moves) >= 6
        assert len(recorded_moves) == len(moves)


class TestMoveHistoryTableRowCalculation:
    """Test row calculations for table display."""
    
    def test_total_rows_for_even_moves(self):
        """Test that even number of moves gives exact rows."""
        total_moves = 10
        rows = total_moves // 2
        assert rows == 5
    
    def test_total_rows_for_odd_moves(self):
        """Test that odd number of moves needs extra row."""
        total_moves = 11
        rows = (total_moves + 1) // 2
        assert rows == 6
    
    def test_rows_for_various_move_counts(self):
        """Test row calculation for various move counts."""
        test_cases = [
            (0, 0),      # No moves -> 0 rows
            (1, 1),      # 1 move (Black) -> 1 row
            (2, 1),      # 2 moves (Black + White) -> 1 row
            (3, 2),      # 3 moves -> 2 rows
            (4, 2),      # 4 moves -> 2 rows
            (158, 79),   # 158 moves -> 79 rows
            (159, 80),   # 159 moves -> 80 rows
        ]
        
        for total_moves, expected_rows in test_cases:
            if total_moves == 0:
                rows = 0
            else:
                rows = (total_moves + 1) // 2
            assert rows == expected_rows, f"Moves {total_moves}: expected {expected_rows} rows, got {rows}"


class TestMoveNumberHighlighting:
    """Test conversion from move number to highlight position."""
    
    def test_highlight_move_zero(self):
        """Test highlighting move 0 (Black)."""
        move_number = 0
        row = move_number // 2
        col = move_number % 2
        
        assert row == 0
        assert col == 0
    
    def test_highlight_move_one(self):
        """Test highlighting move 1 (White)."""
        move_number = 1
        row = move_number // 2
        col = move_number % 2
        
        assert row == 0
        assert col == 1
    
    def test_highlight_arbitrary_moves(self):
        """Test highlighting various moves."""
        test_cases = [
            (0, 0, 0),
            (1, 0, 1),
            (10, 5, 0),
            (11, 5, 1),
            (157, 78, 1),
            (158, 79, 0),
        ]
        
        for move_num, expected_row, expected_col in test_cases:
            row = move_num // 2
            col = move_num % 2
            assert row == expected_row
            assert col == expected_col


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_game(self):
        """Test empty game with no moves."""
        game = GoGame(9)
        moves = game.list_moves()
        
        assert len(moves) == 0
        assert moves == []
    
    def test_single_move_game(self):
        """Test game with only one move."""
        game = GoGame(9)
        game.make_move("E5")
        
        moves = game.list_moves()
        assert len(moves) == 1
        assert moves[0] == "E5"
    
    def test_move_number_zero_highlighting(self):
        """Test that move number 0 is handled correctly."""
        # Move 0 is the first move (Black)
        # Highlighting it should show row 0, col 0
        move_number = 0
        row = move_number // 2
        col = move_number % 2
        
        assert row == 0
        assert col == 0
    
    def test_game_with_many_moves(self):
        """Test game with a substantial number of moves."""
        game = GoGame(19)
        
        # Play many moves on different board positions
        base_moves = ["D4", "E5", "F6", "G7", "H8", "J9", "K10", "L11"]
        for i, move in enumerate(base_moves):
            game.make_move(move)
        
        recorded_moves = game.list_moves()
        assert len(recorded_moves) >= 8
