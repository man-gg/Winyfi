"""
Manually trigger bandwidth logging for all routers to test immediately
"""
from db import get_connection
from bandwidth_logger import log_bandwidth

def get_all_routers():
    """Get all routers from database"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, ip_address, brand FROM routers WHERE ip_address IS NOT NULL AND ip_address != 'N/A'")
        routers = cursor.fetchall()
        cursor.close()
        conn.close()
        return routers
    except Exception as e:
        print(f"❌ Error getting routers: {e}")
        return []

def main():
    print("=" * 60)
    print("🚀 MANUAL BANDWIDTH LOGGING TEST")
    print("=" * 60)
    
    routers = get_all_routers()
    
    if not routers:
        print("❌ No routers found in database!")
        return
    
    print(f"\n✅ Found {len(routers)} router(s)\n")
    
    for router in routers:
        print(f"📡 Testing router: {router['name']} ({router['ip_address']})")
        print(f"   ID: {router['id']}, Brand: {router.get('brand', 'Unknown')}")
        
        # Skip UniFi routers (they're logged separately via API)
        if str(router.get('brand', '')).lower() == 'unifi':
            print(f"   ⏭️  Skipping (UniFi router - logged via API)")
            continue
        
        try:
            log_bandwidth(router['id'], router['ip_address'])
            print(f"   ✅ Bandwidth logged successfully\n")
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
    
    print("=" * 60)
    print("✅ Manual logging complete!")
    print("=" * 60)
    print("\n💡 Now check your bandwidth tab and click 'Refresh'")

if __name__ == "__main__":
    main()
