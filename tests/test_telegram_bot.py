"""
Unit tests for Telegram bot functionality.
"""

import datetime
from unittest.mock import patch

import pytest

from src.telegram_bot import parse_date_input, is_date_within_range


def test_date_parsing():
    """Test the date parsing functionality."""
    # Keywords
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    
    assert parse_date_input('T') == today
    assert parse_date_input('today') == today
    assert parse_date_input('M') == tomorrow
    assert parse_date_input('tomorrow') == tomorrow
    
    # European format
    current_year = today.year
    assert parse_date_input('4.9') == datetime.date(current_year, 9, 4)
    assert parse_date_input('4.9.') == datetime.date(current_year, 9, 4)  # Trailing dot
    assert parse_date_input('4.9.2025') == datetime.date(2025, 9, 4)
    assert parse_date_input('4.9.2025.') == datetime.date(2025, 9, 4)  # Trailing dot with year
    assert parse_date_input('25.12.2024') == datetime.date(2024, 12, 25)
    
    # Invalid dates
    assert parse_date_input('32.1') is None
    assert parse_date_input('1.13') is None
    assert parse_date_input('invalid') is None


def test_date_range_validation():
    """Test the date range validation (3 months limitation)."""
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    
    # Valid dates (today, tomorrow, and within 3 months)
    assert is_date_within_range(today) is True
    assert is_date_within_range(tomorrow) is True
    assert is_date_within_range(today - datetime.timedelta(days=30)) is True
    assert is_date_within_range(today - datetime.timedelta(days=90)) is True
    
    # Invalid dates (too old)
    assert is_date_within_range(today - datetime.timedelta(days=91)) is False
    assert is_date_within_range(today - datetime.timedelta(days=120)) is False
