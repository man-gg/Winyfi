# Test script to demonstrate dynamic ping alignment
import time
from network_utils import ping_latency, ping_manager

print("Testing Dynamic Ping Alignment")
print("=" * 40)

# Test IP
test_ip = "8.8.8.8"

print(f"Initial ping manager state:")
print(f"  Current interval: {ping_manager.current_interval} seconds")
print(f"  Should ping: {ping_manager.should_ping()}")
print()

# Simulate multiple ping attempts to see dynamic behavior
for i in range(5):
    print(f"Attempt {i+1}:")
    
    # Try to ping
    latency = ping_latency(test_ip, timeout=1000, bandwidth=10)
    
    if latency is not None:
        print(f"  ✅ Ping successful: {latency:.2f} ms")
    else:
        print(f"  ⏭️  Ping skipped (dynamic interval not reached)")
    
    print(f"  Current interval: {ping_manager.current_interval}s")
    print(f"  Should ping next: {ping_manager.should_ping()}")
    
    # Wait a moment before next attempt
    time.sleep(1)
    print()

print("Dynamic ping test completed!")
print("This demonstrates how the ping function now respects dynamic intervals")
print("to reduce network congestion while maintaining latency monitoring.")