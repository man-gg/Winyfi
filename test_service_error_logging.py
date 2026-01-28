#!/usr/bin/env python3
"""
Test service manager error logging
"""
import service_manager
import time
from pathlib import Path

print("Testing Service Manager Error Logging...")
print("="*60)

# Create service manager
sm = service_manager.ServiceManager()

print(f"✅ Service Manager initialized")
print(f"   App directory: {sm.app_dir}")
print(f"   Logs directory: {sm.logs_dir}")
print(f"   Flask script: {sm.services['flask_api']['script']}")
print(f"   UniFi script: {sm.services['unifi_api']['script']}")

# Check if runtime error log exists
runtime_log = sm.logs_dir / "winyfi_runtime_error.log"
print(f"\n✅ Runtime error log: {runtime_log}")
print(f"   Exists: {runtime_log.exists()}")

# Try to start Flask service
print(f"\n🔄 Attempting to start Flask API service...")
result = sm.start_service('flask_api')

# Wait a bit for startup
time.sleep(5)

print(f"\n📊 Service Status:")
print(f"   Result: {result}")
print(f"   Process: {sm.services['flask_api']['process']}")
if sm.services['flask_api']['process']:
    print(f"   PID: {sm.services['flask_api']['process'].pid}")
    print(f"   Poll: {sm.services['flask_api']['process'].poll()}")

# Check logs
print(f"\n📄 Log Files:")
flask_log = sm.logs_dir / "flask-api.log"
flask_error_log = sm.logs_dir / "flask-api-error.log"

if flask_log.exists():
    print(f"   ✅ {flask_log}")
    with open(flask_log, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        print(f"      Last 5 lines:")
        for line in lines[-5:]:
            print(f"      {line.rstrip()}")

if flask_error_log.exists():
    print(f"   ✅ {flask_error_log}")
    with open(flask_error_log, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        print(f"      Last 5 lines:")
        for line in lines[-5:]:
            print(f"      {line.rstrip()}")

if runtime_log.exists():
    print(f"   ✅ {runtime_log}")
    with open(runtime_log, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        if lines:
            print(f"      Total lines: {len(lines)}")
            print(f"      Last 10 lines:")
            for line in lines[-10:]:
                print(f"      {line.rstrip()}")
        else:
            print(f"      (empty)")

print(f"\n✅ Test complete!")
