-- ============================================
-- Activity Log Table Creation Script
-- WinyFi Network Monitoring System
-- ============================================

-- Create activity_logs table if it doesn't exist
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(255) NOT NULL,
    target VARCHAR(255),
    ip_address VARCHAR(50),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_action (action),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Verify table creation
SELECT 'activity_logs table created successfully' AS status;

-- Show table structure
DESC activity_logs;

-- Optional: Insert test data (for development/testing only)
-- Uncomment the lines below if you want to test with sample data

/*
INSERT INTO activity_logs (user_id, action, target, ip_address, timestamp) VALUES
(1, 'Login', NULL, '192.168.1.100', NOW()),
(1, 'Add Router', 'Office Router 1', '192.168.1.100', NOW()),
(1, 'Edit Router', 'Office Router 1', '192.168.1.100', NOW()),
(1, 'Add User', 'john_doe', '192.168.1.100', NOW()),
(1, 'Logout', NULL, '192.168.1.100', NOW());
*/

-- Query to view all activity logs
-- SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT 50;

-- Query to view activity logs with user information
-- SELECT 
--     al.id,
--     al.timestamp,
--     CONCAT(u.first_name, ' ', u.last_name) as user_name,
--     u.username,
--     al.action,
--     al.target,
--     al.ip_address
-- FROM activity_logs al
-- LEFT JOIN users u ON al.user_id = u.id
-- ORDER BY al.timestamp DESC
-- LIMIT 50;

-- Query to get activity statistics
-- SELECT 
--     action,
--     COUNT(*) as count
-- FROM activity_logs
-- GROUP BY action
-- ORDER BY count DESC;

-- Query to get recent activities (last 24 hours)
-- SELECT COUNT(*) as recent_count
-- FROM activity_logs
-- WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR);
