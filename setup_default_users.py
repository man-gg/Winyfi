#!/usr/bin/env python3
"""
Script to create a default client user for ICT service request submissions.
Run this script to ensure there's always a valid user for client portal submissions.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db import get_connection
import hashlib

def create_default_client_user():
    """Create a default client user if none exists."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Checking for existing users...")
        
        # Check if any users exist
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            print("No users found. Creating default users...")
            
            # Create admin user
            admin_password = "admin123"
            admin_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, created_at) 
                VALUES (%s, %s, %s, NOW())
            """, ("admin", admin_hash, "admin"))
            
            # Create client user
            client_password = "client123"
            client_hash = hashlib.sha256(client_password.encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, created_at) 
                VALUES (%s, %s, %s, NOW())
            """, ("client", client_hash, "client"))
            
            conn.commit()
            print("✓ Default users created:")
            print("  Admin: username='admin', password='admin123'")
            print("  Client: username='client', password='client123'")
            
        else:
            # Check if there's a client user
            cursor.execute("SELECT id, username FROM users WHERE role='client' OR username='client' LIMIT 1")
            client_user = cursor.fetchone()
            
            if not client_user:
                print("No client user found. Creating default client user...")
                
                client_password = "client123"
                client_hash = hashlib.sha256(client_password.encode()).hexdigest()
                
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role, created_at) 
                    VALUES (%s, %s, %s, NOW())
                """, ("client", client_hash, "client"))
                
                conn.commit()
                print("✓ Default client user created: username='client', password='client123'")
            else:
                print(f"✓ Client user already exists: {client_user[1]} (ID: {client_user[0]})")
        
        # Show all users
        cursor.execute("SELECT id, username, role FROM users ORDER BY id")
        users = cursor.fetchall()
        
        print(f"\n📋 Current users in system ({len(users)} total):")
        for user in users:
            print(f"  ID: {user[0]}, Username: {user[1]}, Role: {user[2]}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 User setup completed successfully!")
        print("The client portal can now submit tickets using the available users.")
        
    except Exception as e:
        print(f"❌ Error setting up users: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_default_client_user()