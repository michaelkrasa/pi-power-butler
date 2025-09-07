import sqlite3
import datetime
import json
import structlog
from pathlib import Path
from typing import Optional, Dict, List

logger = structlog.get_logger()

class EnergyDataCache:
    """Cache for energy data (prices, irradiance, graphs) with automatic cleanup."""
    
    def __init__(self, db_path: str = ".cache.sqlite"):
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize the cache database with our energy data schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Check if old table exists with graph columns
            cursor = conn.execute("PRAGMA table_info(energy_cache)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'price_graph' in columns or 'irradiance_graph' in columns:
                # Drop old table and recreate without graph columns
                logger.info("Migrating cache schema - removing graph columns")
                conn.execute("DROP TABLE IF EXISTS energy_cache")
            
            # Create our energy data table (data only, no graphs)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS energy_cache (
                    date TEXT PRIMARY KEY,
                    prices TEXT,
                    irradiance TEXT,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster queries
            conn.execute("CREATE INDEX IF NOT EXISTS date_idx ON energy_cache(date)")
            conn.commit()
            logger.info("Energy cache database initialized")
    
    def get_cached_data(self, date: datetime.date) -> Optional[Dict]:
        """Get cached energy data for a specific date."""
        date_str = date.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT prices, irradiance, cached_at
                FROM energy_cache 
                WHERE date = ?
            """, (date_str,))
            
            row = cursor.fetchone()
            if row:
                prices_json, irradiance_json, cached_at = row
                
                # Parse JSON data
                prices = json.loads(prices_json) if prices_json else None
                irradiance = json.loads(irradiance_json) if irradiance_json else None
                
                logger.info("Cache hit for date", date=date_str, cached_at=cached_at)
                
                return {
                    'date': date,
                    'prices': prices,
                    'irradiance': irradiance,
                    'cached_at': cached_at
                }
        
        logger.info("Cache miss for date", date=date_str)
        return None
    
    def cache_data(self, date: datetime.date, prices: List[float], irradiance: List[float]):
        """Cache energy data for a specific date (data only, no graphs)."""
        date_str = date.isoformat()
        logger.info(f"Starting cache operation for {date_str} with {len(prices)} prices and {len(irradiance)} irradiance values")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                logger.info(f"Connected to database: {self.db_path}")
                conn.execute("""
                    INSERT OR REPLACE INTO energy_cache 
                    (date, prices, irradiance)
                    VALUES (?, ?, ?)
                """, (
                    date_str,
                    json.dumps(prices),
                    json.dumps(irradiance)
                ))
                logger.info(f"Executed SQL insert for {date_str}")
                conn.commit()
                logger.info(f"Committed transaction for {date_str}")
                
            logger.info("Successfully cached energy data for date", date=date_str, 
                       prices_count=len(prices), irradiance_count=len(irradiance))
        except Exception as e:
            logger.error(f"Error caching data for {date_str}: {e}", exc_info=True)
            raise
    
    def cleanup_old_data(self):
        """Remove data older than today (keep only today and tomorrow)."""
        today = datetime.date.today()
        cutoff_date = today.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM energy_cache WHERE date < ?", (cutoff_date,))
            deleted_count = cursor.rowcount
            conn.commit()
            
        if deleted_count > 0:
            logger.info("Cleaned up old cache data", deleted_count=deleted_count, cutoff_date=cutoff_date)
        
        return deleted_count
    
