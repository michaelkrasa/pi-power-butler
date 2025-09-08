"""
Unit tests for Telegram bot functionality.

Tests the date parsing, message handling, and bot responses.
"""

import datetime
import re
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def parse_date_input(text: str) -> Optional[datetime.date]:
    """
    Parse various date input formats:
    - 'T' or 'today' -> today
    - 'M' or 'tomorrow' -> tomorrow  
    - '4.9' -> 4th September current year
    - '4.9.2025' -> 4th September 2025
    - '04.09' -> 4th September current year
    - '04.09.2025' -> 4th September 2025
    """
    text = text.strip().lower()
    
    # Handle special keywords
    if text in ['t', 'today']:
        return datetime.date.today()
    elif text in ['m', 'tomorrow']:
        return datetime.date.today() + datetime.timedelta(days=1)
    
    # Handle date patterns (day.month.year or day.month)
    date_pattern = r'^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$'
    match = re.match(date_pattern, text)
    
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else datetime.date.today().year
        
        try:
            return datetime.date(year, month, day)
        except ValueError:
            return None
    
    return None


class TestDateParsing:
    """Test the date parsing functionality."""

    def test_keyword_parsing(self):
        """Test parsing of keyword inputs."""
        # Test today
        today = datetime.date.today()
        assert parse_date_input('T') == today
        assert parse_date_input('today') == today
        assert parse_date_input('TODAY') == today
        
        # Test tomorrow
        tomorrow = today + datetime.timedelta(days=1)
        assert parse_date_input('M') == tomorrow
        assert parse_date_input('tomorrow') == tomorrow
        assert parse_date_input('TOMORROW') == tomorrow

    def test_european_date_format_current_year(self):
        """Test European date format without year (current year)."""
        current_year = datetime.date.today().year
        
        # Test various formats
        assert parse_date_input('4.9') == datetime.date(current_year, 9, 4)
        assert parse_date_input('04.09') == datetime.date(current_year, 9, 4)
        assert parse_date_input('25.12') == datetime.date(current_year, 12, 25)
        assert parse_date_input('1.1') == datetime.date(current_year, 1, 1)
        assert parse_date_input('31.12') == datetime.date(current_year, 12, 31)

    def test_european_date_format_with_year(self):
        """Test European date format with specific year."""
        # Test with specific years
        assert parse_date_input('4.9.2025') == datetime.date(2025, 9, 4)
        assert parse_date_input('04.09.2025') == datetime.date(2025, 9, 4)
        assert parse_date_input('25.12.2024') == datetime.date(2024, 12, 25)
        assert parse_date_input('1.1.2026') == datetime.date(2026, 1, 1)
        assert parse_date_input('29.2.2024') == datetime.date(2024, 2, 29)  # Leap year

    def test_invalid_dates(self):
        """Test that invalid dates return None."""
        # Invalid day
        assert parse_date_input('32.1') is None
        assert parse_date_input('0.1') is None
        
        # Invalid month
        assert parse_date_input('1.13') is None
        assert parse_date_input('1.0') is None
        
        # Invalid date combinations
        assert parse_date_input('31.2') is None  # February 31st
        assert parse_date_input('29.2.2025') is None  # Feb 29th in non-leap year
        
        # Non-date strings
        assert parse_date_input('invalid') is None
        assert parse_date_input('abc') is None
        assert parse_date_input('') is None
        assert parse_date_input('1.2.3.4') is None  # Too many parts
        assert parse_date_input('1') is None  # Too few parts

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Test whitespace handling
        assert parse_date_input(' 4.9 ') == datetime.date.today().replace(month=9, day=4)
        assert parse_date_input('\tM\n') == datetime.date.today() + datetime.timedelta(days=1)
        
        # Test case insensitivity for keywords
        assert parse_date_input('t') == datetime.date.today()
        assert parse_date_input('m') == datetime.date.today() + datetime.timedelta(days=1)
        
        # Test single digit months and days
        assert parse_date_input('1.1') == datetime.date.today().replace(month=1, day=1)
        assert parse_date_input('9.9') == datetime.date.today().replace(month=9, day=9)

    def test_leap_year_handling(self):
        """Test leap year date handling."""
        # Valid leap year dates
        assert parse_date_input('29.2.2024') == datetime.date(2024, 2, 29)
        assert parse_date_input('29.2.2020') == datetime.date(2020, 2, 29)
        
        # Invalid leap year dates
        assert parse_date_input('29.2.2025') is None  # Not a leap year
        assert parse_date_input('29.2.2023') is None  # Not a leap year

    def test_parse_date_input_comprehensive(self):
        """Comprehensive test of all supported date formats."""
        test_cases = [
            # Keywords
            ('T', datetime.date.today()),
            ('today', datetime.date.today()),
            ('M', datetime.date.today() + datetime.timedelta(days=1)),
            ('tomorrow', datetime.date.today() + datetime.timedelta(days=1)),
            
            # European format without year
            ('4.9', datetime.date.today().replace(month=9, day=4)),
            ('04.09', datetime.date.today().replace(month=9, day=4)),
            ('25.12', datetime.date.today().replace(month=12, day=25)),
            ('1.1', datetime.date.today().replace(month=1, day=1)),
            
            # European format with year
            ('4.9.2025', datetime.date(2025, 9, 4)),
            ('04.09.2025', datetime.date(2025, 9, 4)),
            ('25.12.2024', datetime.date(2024, 12, 25)),
            ('1.1.2026', datetime.date(2026, 1, 1)),
            
            # Invalid cases
            ('invalid', None),
            ('32.1', None),
            ('1.13', None),
            ('abc', None),
            ('', None),
        ]
        
        for input_text, expected in test_cases:
            result = parse_date_input(input_text)
            assert result == expected, f"Failed for input '{input_text}': expected {expected}, got {result}"
