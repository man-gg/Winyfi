-- Add accomplishment and technician assignment fields to ict_service_requests table

-- Add accomplishment tracking fields
ALTER TABLE ict_service_requests 
ADD COLUMN accomplishment TEXT,
ADD COLUMN accomplished_by INT,
ADD COLUMN accomplished_at DATETIME,
ADD COLUMN technician_assigned_id INT,
ADD COLUMN assigned_at DATETIME,
ADD COLUMN assigned_by INT;

-- Add foreign key constraints
ALTER TABLE ict_service_requests 
ADD CONSTRAINT fk_accomplished_by FOREIGN KEY (accomplished_by) REFERENCES users(id),
ADD CONSTRAINT fk_technician_assigned_id FOREIGN KEY (technician_assigned_id) REFERENCES users(id),
ADD CONSTRAINT fk_assigned_by FOREIGN KEY (assigned_by) REFERENCES users(id);

-- Create technicians table for better management
CREATE TABLE IF NOT EXISTS technicians (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    specialization VARCHAR(100),
    department VARCHAR(100),
    contact_number VARCHAR(20),
    email VARCHAR(100),
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Insert default technicians
INSERT INTO technicians (user_id, name, specialization, department, contact_number, email) VALUES
(2, 'Admin Technician', 'General IT Support', 'IT Department', '123-456-7890', 'admin@company.com'),
(3, 'CJay Martinez', 'Network Administration', 'IT Department', '123-456-7891', 'cjay@company.com'),
(4, 'Tech Support', 'Hardware Support', 'IT Department', '123-456-7892', 'support@company.com')
ON DUPLICATE KEY UPDATE name=VALUES(name);