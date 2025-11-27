"""Migration script to add fill_color column to topology_shapes table."""
import sys
sys.path.insert(0, '.')
from db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    
    # Add fill_color column if it doesn't exist
    cur.execute("ALTER TABLE topology_shapes ADD COLUMN fill_color VARCHAR(32) NULL AFTER color")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("✓ Migration complete: Added fill_color column to topology_shapes table")
except Exception as e:
    if "Duplicate column name" in str(e):
        print("✓ Column fill_color already exists, no migration needed")
    else:
        print(f"✗ Migration failed: {e}")
