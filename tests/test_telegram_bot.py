"""
Unit tests for Telegram bot functionality.
"""

import datetime
from unittest.mock import patch

import pytest

from src.telegram_bot import parse_date_input


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
    assert parse_date_input('4.9.2025') == datetime.date(2025, 9, 4)
    assert parse_date_input('25.12.2024') == datetime.date(2024, 12, 25)
    
    # Invalid dates
    assert parse_date_input('32.1') is None
    assert parse_date_input('1.13') is None
    assert parse_date_input('invalid') is None
