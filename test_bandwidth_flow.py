"""
Test bandwidth flow from network_utils -> bandwidth_logger -> database -> API -> UI
"""
import sys
import time
from network_utils import get_bandwidth
from db import insert_bandwidth_log, get_connection

def test_get_bandwidth():
    """Test the new get_bandwidth function"""
    print("=" * 60)
    print("Testing get_bandwidth() function")
    print("=" * 60)
    
    # Test with a common gateway IP
    test_ips = ["192.168.1.1", "8.8.8.8"]
    
    for ip in test_ips:
        print(f"\n🔍 Testing IP: {ip}")
        try:
            result = get_bandwidth(ip)
            print(f"✅ Result:")
            print(f"   Latency: {result.get('latency')}")
            print(f"   Download: {result.get('download')}")
            print(f"   Upload: {result.get('upload')}")
            print(f"   Method: {result.get('method')}")
            print(f"   Quality: {result.get('quality')}")
        except Exception as e:
            print(f"❌ Error: {e}")

def test_insert_bandwidth():
    """Test inserting bandwidth data to database"""
    print("\n" + "=" * 60)
    print("Testing database insertion")
    print("=" * 60)
    
    # Test data
    test_data = {
        "router_id": 1,
        "download_mbps": 25.5,
        "upload_mbps": 10.2,
        "latency_ms": 15.3
    }
    
    print(f"\n🔍 Inserting test data: {test_data}")
    try:
        success = insert_bandwidth_log(
            test_data["router_id"],
            test_data["download_mbps"],
            test_data["upload_mbps"],
            test_data["latency_ms"]
        )
        if success:
            print(f"✅ Successfully inserted bandwidth log")
            
            # Verify insertion
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM bandwidth_logs 
                WHERE router_id = %s 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (test_data["router_id"],))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                print(f"✅ Verified in database:")
                print(f"   ID: {result.get('id')}")
                print(f"   Router ID: {result.get('router_id')}")
                print(f"   Download: {result.get('download_mbps')} Mbps")
                print(f"   Upload: {result.get('upload_mbps')} Mbps")
                print(f"   Latency: {result.get('latency_ms')} ms")
                print(f"   Timestamp: {result.get('timestamp')}")
            else:
                print(f"❌ Could not verify insertion")
        else:
            print(f"❌ Failed to insert bandwidth log")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_full_flow():
    """Test complete flow: measure -> log -> verify"""
    print("\n" + "=" * 60)
    print("Testing complete bandwidth flow")
    print("=" * 60)
    
    test_ip = "8.8.8.8"  # Google DNS (should be reachable)
    test_router_id = 1
    
    print(f"\n🔍 Step 1: Measure bandwidth for {test_ip}")
    try:
        bw = get_bandwidth(test_ip)
        print(f"✅ Bandwidth measured:")
        print(f"   Download: {bw.get('download')} Mbps")
        print(f"   Upload: {bw.get('upload')} Mbps")
        print(f"   Latency: {bw.get('latency')} ms")
        
        # Handle "N/A" values
        download = bw.get("download", 0)
        upload = bw.get("upload", 0)
        latency = bw.get("latency", None)
        
        if download == "N/A":
            download = 0
        if upload == "N/A":
            upload = 0
        
        print(f"\n🔍 Step 2: Insert to database")
        success = insert_bandwidth_log(
            test_router_id,
            float(download) if download else 0,
            float(upload) if upload else 0,
            latency
        )
        
        if success:
            print(f"✅ Successfully logged to database")
            
            print(f"\n🔍 Step 3: Verify via database query")
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM bandwidth_logs 
                WHERE router_id = %s 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (test_router_id,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                print(f"✅ Data verified in database:")
                print(f"   Download: {result.get('download_mbps')} Mbps")
                print(f"   Upload: {result.get('upload_mbps')} Mbps")
                print(f"   Latency: {result.get('latency_ms')} ms")
                print(f"   Timestamp: {result.get('timestamp')}")
                
                print(f"\n✅ COMPLETE FLOW TEST PASSED!")
                print(f"   Your bandwidth tab should now show this data via /api/bandwidth/logs")
            else:
                print(f"❌ Could not verify data in database")
        else:
            print(f"❌ Failed to insert to database")
            
    except Exception as e:
        print(f"❌ Error in flow test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n" + "🚀 " * 20)
    print("BANDWIDTH FLOW TEST")
    print("🚀 " * 20)
    
    test_get_bandwidth()
    time.sleep(1)
    
    test_insert_bandwidth()
    time.sleep(1)
    
    test_full_flow()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print("\n💡 Next steps:")
    print("   1. Check your bandwidth tab in the UI")
    print("   2. Click 'Refresh' to load the latest data")
    print("   3. Verify the chart updates with new bandwidth measurements")
    print("=" * 60)
