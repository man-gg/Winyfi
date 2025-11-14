-- Add is_agent column to users table for subnet agent functionality
-- This allows designated clients to perform network scanning on their subnet

ALTER TABLE users 
ADD COLUMN is_agent BOOLEAN DEFAULT FALSE AFTER role;
