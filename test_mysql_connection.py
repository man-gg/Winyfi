#!/usr/bin/env python
"""
MySQL Connection Diagnostic Script
Tests various connection scenarios and provides troubleshooting guidance
"""
import mysql.connector
from mysql.connector import Error
import json
import os
import sys

def test_basic_connection():
    """Test basic MySQL connection"""
    print("\n" + "="*60)
    print("TEST 1: Basic MySQL Connection")
    print("="*60)
    
    config = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "connection_timeout": 10
    }
    
    try:
        print(f"Attempting to connect to {config['host']} as {config['user']}...")
        conn = mysql.connector.connect(**config)
        
        if conn.is_connected():
            db_info = conn.get_server_info()
            print(f"✅ Connected successfully!")
            print(f"   MySQL Server version: {db_info}")
            conn.close()
            return True
        else:
            print("❌ Connection established but not active")
            return False
            
    except mysql.connector.Error as err:
        print(f"❌ Connection failed!")
        if err.errno == 2003:
            print(f"   Error: Cannot connect to MySQL server on '{config['host']}'")
            print(f"   Solution: Is MySQL running? Check:")
            print(f"      1. XAMPP Control Panel - Is MySQL started?")
            print(f"      2. Windows Services - Is MySQL service running?")
            print(f"      3. Try: mysql -h localhost -u root (in command line)")
        elif err.errno == 1045:
            print(f"   Error: Access denied for user '{config['user']}'")
            print(f"   Solution: Check your MySQL password")
        else:
            print(f"   Error {err.errno}: {err.msg}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_database_exists():
    """Test if winyfi database exists"""
    print("\n" + "="*60)
    print("TEST 2: Check if 'winyfi' Database Exists")
    print("="*60)
    
    config = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "connection_timeout": 10
    }
    
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        # Show all databases
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        
        print(f"Available databases:")
        db_names = [db[0] for db in databases]
        for db in db_names:
            marker = "✅" if db == "winyfi" else "  "
            print(f"   {marker} {db}")
        
        cursor.close()
        conn.close()
        
        if "winyfi" in db_names:
            print(f"\n✅ 'winyfi' database exists")
            return True
        else:
            print(f"\n❌ 'winyfi' database NOT found")
            print(f"   To create it:")
            print(f"      1. Open phpMyAdmin: http://localhost/phpmyadmin")
            print(f"      2. Click 'New' and create database 'winyfi'")
            print(f"      3. Or run: mysql -u root -e 'CREATE DATABASE winyfi;'")
            return False
            
    except Exception as e:
        print(f"❌ Error checking databases: {e}")
        return False

def test_winyfi_tables():
    """Test if winyfi database has required tables"""
    print("\n" + "="*60)
    print("TEST 3: Check 'winyfi' Database Tables")
    print("="*60)
    
    config = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "winyfi",
        "connection_timeout": 10
    }
    
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        # Show tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        if tables:
            print(f"✅ Database has {len(tables)} tables:")
            for table in tables:
                print(f"   • {table[0]}")
        else:
            print(f"❌ Database has NO tables!")
            print(f"   To import schema:")
            print(f"      1. Open phpMyAdmin: http://localhost/phpmyadmin")
            print(f"      2. Select 'winyfi' database")
            print(f"      3. Click 'Import' tab")
            print(f"      4. Select winyfi.sql file from Winyfi installation")
            print(f"      5. Click 'Go'")
        
        cursor.close()
        conn.close()
        
        return len(tables) > 0
            
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
        return False

def test_db_config_file():
    """Test if db_config.json exists and is valid"""
    print("\n" + "="*60)
    print("TEST 4: Check db_config.json")
    print("="*60)
    
    config_file = "db_config.json"
    
    if os.path.exists(config_file):
        print(f"✅ {config_file} exists")
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            print(f"   Host: {config.get('host', 'N/A')}")
            print(f"   User: {config.get('user', 'N/A')}")
            print(f"   Database: {config.get('database', 'N/A')}")
            print(f"✅ Config file is valid JSON")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
            return False
        except Exception as e:
            print(f"❌ Error reading config: {e}")
            return False
    else:
        print(f"❌ {config_file} NOT found")
        print(f"   Expected location: {os.path.abspath(config_file)}")
        return False

def print_summary(results):
    """Print test summary"""
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    failed = total - passed
    
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {failed}/{total}")
    
    if failed == 0:
        print(f"\n✅ All tests passed! MySQL is properly configured.")
        print(f"   You should be able to run: python main.py")
    else:
        print(f"\n❌ Some tests failed. Please fix the issues above.")

def main():
    print("\n")
    print("╔════════════════════════════════════════════════════════╗")
    print("║        WINYFI MySQL Connection Diagnostic Tool         ║")
    print("╚════════════════════════════════════════════════════════╝")
    
    results = {}
    
    # Run all tests
    results["Basic Connection"] = test_basic_connection()
    
    if results["Basic Connection"]:
        results["Database Exists"] = test_database_exists()
        if results["Database Exists"]:
            results["Tables Check"] = test_winyfi_tables()
    
    results["Config File"] = test_db_config_file()
    
    # Print summary
    print_summary(results)
    
    # Return exit code
    if all(results.values()):
        print("\n🚀 Ready to run: python main.py\n")
        return 0
    else:
        print("\n⚠️  Please resolve the above issues before running the app.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
