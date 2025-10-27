"""
Database migration to add enhanced loop detection fields.

This migration adds support for:
- Cross-subnet detection
- Efficiency metrics
- Advanced severity breakdown
- Subnet tracking

Run this AFTER deploying the enhanced loop detection system.
"""

import mysql.connector
from db import get_connection

def migrate_enhanced_loop_detection():
    """Add enhanced fields to loop_detections table."""
    print("🔧 Starting enhanced loop detection migration...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'loop_detections' 
            AND COLUMN_NAME IN (
                'cross_subnet_detected', 'unique_subnets', 'unique_macs',
                'packets_analyzed', 'sample_rate', 'efficiency_score'
            )
        """)
        existing_columns = {row[0] for row in cursor.fetchall()}
        
        # Add cross_subnet_detected column
        if 'cross_subnet_detected' not in existing_columns:
            print("  ➕ Adding cross_subnet_detected column...")
            cursor.execute("""
                ALTER TABLE loop_detections 
                ADD COLUMN cross_subnet_detected BOOLEAN DEFAULT FALSE
                COMMENT 'Whether loop was detected across multiple subnets'
            """)
            print("  ✅ Added cross_subnet_detected")
        
        # Add unique_subnets column
        if 'unique_subnets' not in existing_columns:
            print("  ➕ Adding unique_subnets column...")
            cursor.execute("""
                ALTER TABLE loop_detections 
                ADD COLUMN unique_subnets INT DEFAULT 0
                COMMENT 'Number of unique subnets involved in loop'
            """)
            print("  ✅ Added unique_subnets")
        
        # Add unique_macs column
        if 'unique_macs' not in existing_columns:
            print("  ➕ Adding unique_macs column...")
            cursor.execute("""
                ALTER TABLE loop_detections 
                ADD COLUMN unique_macs INT DEFAULT 0
                COMMENT 'Number of unique MAC addresses involved'
            """)
            print("  ✅ Added unique_macs")
        
        # Add packets_analyzed column
        if 'packets_analyzed' not in existing_columns:
            print("  ➕ Adding packets_analyzed column...")
            cursor.execute("""
                ALTER TABLE loop_detections 
                ADD COLUMN packets_analyzed INT DEFAULT 0
                COMMENT 'Total packets analyzed (including filtered)'
            """)
            print("  ✅ Added packets_analyzed")
        
        # Add sample_rate column
        if 'sample_rate' not in existing_columns:
            print("  ➕ Adding sample_rate column...")
            cursor.execute("""
                ALTER TABLE loop_detections 
                ADD COLUMN sample_rate FLOAT DEFAULT 1.0
                COMMENT 'Packet sampling rate used (1.0 = no sampling)'
            """)
            print("  ✅ Added sample_rate")
        
        # Add efficiency_score column
        if 'efficiency_score' not in existing_columns:
            print("  ➕ Adding efficiency_score column...")
            cursor.execute("""
                ALTER TABLE loop_detections 
                ADD COLUMN efficiency_score FLOAT DEFAULT 0.0
                COMMENT 'Detection efficiency score (0-100)'
            """)
            print("  ✅ Added efficiency_score")
        
        # Add severity breakdown JSON column
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'loop_detections' 
            AND COLUMN_NAME = 'severity_breakdown'
        """)
        if not cursor.fetchone():
            print("  ➕ Adding severity_breakdown column...")
            cursor.execute("""
                ALTER TABLE loop_detections 
                ADD COLUMN severity_breakdown JSON DEFAULT NULL
                COMMENT 'Detailed breakdown of severity factors (JSON)'
            """)
            print("  ✅ Added severity_breakdown")
        
        # Add index for cross-subnet queries
        print("  ➕ Adding index for cross_subnet_detected...")
        try:
            cursor.execute("""
                CREATE INDEX idx_cross_subnet 
                ON loop_detections(cross_subnet_detected, detection_time DESC)
            """)
            print("  ✅ Added index idx_cross_subnet")
        except mysql.connector.Error as e:
            if e.errno == 1061:  # Duplicate key name
                print("  ℹ️ Index idx_cross_subnet already exists")
            else:
                raise
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("\nNew fields added:")
        print("  - cross_subnet_detected: Track multi-subnet loops")
        print("  - unique_subnets: Number of subnets involved")
        print("  - unique_macs: Number of MAC addresses")
        print("  - packets_analyzed: Total packets processed")
        print("  - sample_rate: Sampling efficiency")
        print("  - efficiency_score: Overall efficiency (0-100)")
        print("  - severity_breakdown: JSON breakdown of severity factors")
        
    except mysql.connector.Error as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def update_save_loop_detection():
    """
    Show how to update db.py save_loop_detection() to use new fields.
    This is informational only - you need to manually update db.py.
    """
    print("\n📝 To fully utilize enhanced fields, update db.py save_loop_detection():")
    print("""
def save_loop_detection(total_packets, offenders, stats, status, severity_score, 
                        interface="Wi-Fi", duration=5, efficiency_metrics=None):
    \"\"\"Save loop detection result to database with enhanced fields.\"\"\"
    conn = get_connection()
    cursor = conn.cursor()
    
    # Extract efficiency metrics
    cross_subnet = False
    unique_subnets = 0
    unique_macs = 0
    packets_analyzed = total_packets
    sample_rate = 1.0
    efficiency_score = 0.0
    severity_breakdown = None
    
    if efficiency_metrics:
        cross_subnet = efficiency_metrics.get('cross_subnet_detected', False)
        unique_subnets = efficiency_metrics.get('unique_subnets', 0)
        unique_macs = efficiency_metrics.get('unique_macs', 0)
        packets_analyzed = efficiency_metrics.get('packets_analyzed', total_packets)
        sample_rate = efficiency_metrics.get('sample_rate', 1.0)
        
        # Calculate efficiency score
        if packets_analyzed > 0:
            efficiency_score = (total_packets / packets_analyzed) * 100
    
    # If severity_score is a dict (advanced mode), extract breakdown
    if isinstance(severity_score, dict):
        severity_breakdown = severity_score
        severity_score = severity_score.get('total', 0)
    
    query = \"\"\"
        INSERT INTO loop_detections 
        (total_packets, offenders_count, offenders_data, severity_score, 
         network_interface, detection_duration, status,
         cross_subnet_detected, unique_subnets, unique_macs,
         packets_analyzed, sample_rate, efficiency_score, severity_breakdown)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    \"\"\"
    
    import json
    offenders_json = json.dumps({
        "offenders": offenders,
        "stats": stats
    })
    
    severity_json = json.dumps(severity_breakdown) if severity_breakdown else None
    
    cursor.execute(query, (
        total_packets, len(offenders), offenders_json, severity_score,
        interface, duration, status,
        cross_subnet, unique_subnets, unique_macs,
        packets_analyzed, sample_rate, efficiency_score, severity_json
    ))
    
    conn.commit()
    detection_id = cursor.lastrowid
    cursor.close()
    conn.close()
    
    return detection_id
""")

if __name__ == "__main__":
    print("=" * 70)
    print("Enhanced Loop Detection Database Migration")
    print("=" * 70)
    print()
    
    response = input("This will modify the loop_detections table. Continue? (y/n): ")
    if response.lower() == 'y':
        migrate_enhanced_loop_detection()
        print()
        update_save_loop_detection()
    else:
        print("❌ Migration cancelled")
