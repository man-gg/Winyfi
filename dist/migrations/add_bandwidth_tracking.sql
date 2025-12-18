-- Database Migration: Add bandwidth tracking columns and tables
-- Run this migration to enable cumulative bandwidth tracking

-- 1. Add cumulative bandwidth columns to routers table
ALTER TABLE routers 
ADD COLUMN IF NOT EXISTS total_rx_bytes BIGINT UNSIGNED DEFAULT 0 COMMENT 'Total bytes received (cumulative)',
ADD COLUMN IF NOT EXISTS total_tx_bytes BIGINT UNSIGNED DEFAULT 0 COMMENT 'Total bytes transmitted (cumulative)',
ADD COLUMN IF NOT EXISTS last_bandwidth_update DATETIME NULL COMMENT 'Last bandwidth update timestamp';

-- 2. Create bandwidth_snapshots table for tracking deltas over time
CREATE TABLE IF NOT EXISTS bandwidth_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    router_id INT NOT NULL,
    rx_bytes_total BIGINT UNSIGNED NOT NULL COMMENT 'Total RX bytes at this point in time',
    tx_bytes_total BIGINT UNSIGNED NOT NULL COMMENT 'Total TX bytes at this point in time',
    rx_bytes_diff BIGINT UNSIGNED DEFAULT 0 COMMENT 'RX bytes since last snapshot',
    tx_bytes_diff BIGINT UNSIGNED DEFAULT 0 COMMENT 'TX bytes since last snapshot',
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_router_time (router_id, timestamp),
    INDEX idx_timestamp (timestamp),
    FOREIGN KEY (router_id) REFERENCES routers(id) ON DELETE CASCADE
) COMMENT 'Tracks bandwidth usage snapshots and deltas over time';

-- 3. Add computed columns to bandwidth_logs for backward compatibility (optional)
-- This allows existing queries to still work
ALTER TABLE bandwidth_logs
ADD COLUMN IF NOT EXISTS rx_bytes_diff BIGINT UNSIGNED DEFAULT 0 COMMENT 'RX bytes delta',
ADD COLUMN IF NOT EXISTS tx_bytes_diff BIGINT UNSIGNED DEFAULT 0 COMMENT 'TX bytes delta';

-- 4. Create view for easy bandwidth analysis
CREATE OR REPLACE VIEW v_bandwidth_summary AS
SELECT 
    r.id as router_id,
    r.name as router_name,
    r.ip_address,
    r.mac_address,
    r.total_rx_bytes,
    r.total_tx_bytes,
    r.last_bandwidth_update,
    ROUND(r.total_rx_bytes / 1024 / 1024 / 1024, 2) as total_rx_gb,
    ROUND(r.total_tx_bytes / 1024 / 1024 / 1024, 2) as total_tx_gb,
    (SELECT COUNT(*) FROM bandwidth_snapshots bs WHERE bs.router_id = r.id) as snapshot_count,
    (SELECT timestamp FROM bandwidth_snapshots bs WHERE bs.router_id = r.id ORDER BY timestamp DESC LIMIT 1) as last_snapshot
FROM routers r
WHERE r.brand = 'UniFi'
ORDER BY r.name;

-- 5. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_routers_bandwidth ON routers(last_bandwidth_update);
CREATE INDEX IF NOT EXISTS idx_routers_brand ON routers(brand);

-- Success message
SELECT 'Bandwidth tracking migration completed successfully!' as status;
