"""
Quick test script to verify Flask API and UniFi API work correctly
"""
import sys
import time

print("="*60)
print("Testing Flask API (app.py)")
print("="*60)

try:
    # Test Flask API directly
    sys.path.insert(0, 'server')
    from server.app import create_app
    
    app = create_app()
    
    # Test health endpoint
    with app.test_client() as client:
        response = client.get('/api/health')
        print(f"✓ Health endpoint: {response.status_code}")
        print(f"  Response: {response.get_json()}")
        
        # Test login endpoint
        response = client.post('/api/login', json={
            'username': 'test',
            'password': 'test'
        })
        print(f"✓ Login endpoint: {response.status_code}")
        
    print("\n✅ Flask API tests passed!\n")
    
except Exception as e:
    print(f"\n❌ Flask API test failed: {e}\n")
    import traceback
    traceback.print_exc()

print("="*60)
print("Testing UniFi API (unifi_api.py)")
print("="*60)

try:
    # Import the unifi_api app
    from server.unifi_api import app as unifi_app
    
    # Test health endpoint
    with unifi_app.test_client() as client:
        response = client.get('/api/health')
        print(f"✓ Health endpoint: {response.status_code}")
        print(f"  Response: {response.get_json()}")
        
        # Test devices endpoint
        response = client.get('/api/unifi/devices')
        print(f"✓ Devices endpoint: {response.status_code}")
        
    print("\n✅ UniFi API tests passed!\n")
    
except Exception as e:
    print(f"\n❌ UniFi API test failed: {e}\n")
    import traceback
    traceback.print_exc()

print("="*60)
print("All tests completed!")
print("="*60)
