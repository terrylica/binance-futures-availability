-- Migration: v1.1.0 - Add Trading Volume Metrics
-- Date: 2025-11-14
-- ADR: docs/decisions/0007-trading-volume-metrics.md
-- Description: Extend daily_availability table with 9 volume metric columns from 1d klines

-- Add volume metrics columns (all nullable for backward compatibility)
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS quote_volume_usdt DOUBLE;
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS trade_count BIGINT;
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS volume_base DOUBLE;
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS taker_buy_volume_base DOUBLE;
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS taker_buy_quote_volume_usdt DOUBLE;

-- Add OHLC price columns
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS open_price DOUBLE;
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS high_price DOUBLE;
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS low_price DOUBLE;
ALTER TABLE daily_availability ADD COLUMN IF NOT EXISTS close_price DOUBLE;

-- Create index for volume ranking queries
-- Index on (quote_volume_usdt DESC, date) enables fast "top N by volume" queries
CREATE INDEX IF NOT EXISTS idx_quote_volume_date
    ON daily_availability(quote_volume_usdt DESC, date);

-- Verification queries (run after migration)
-- SELECT COUNT(*) as column_count FROM pragma_table_info('daily_availability');
-- Expected: 17 columns (8 original + 9 new)

-- SELECT * FROM pragma_table_info('daily_availability') WHERE name LIKE '%volume%' OR name LIKE '%price%';
-- Expected: 9 new columns visible

-- SELECT * FROM pragma_index_list('daily_availability');
-- Expected: idx_quote_volume_date in list
