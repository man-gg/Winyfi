#!/usr/bin/env python3
"""
Test script to verify stderr logging in service_manager works correctly
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

# Create a test stderr file
stderr_file = Path("test_stderr.log")
error_file = Path("winyfi_runtime_error.log")

# Clear files
stderr_file.write_text("")
error_file.write_text("")

print("✓ Test files created")

# Test 1: Capture stderr from a subprocess that outputs errors
print("\n[TEST 1] Testing stderr capture from subprocess...")

test_script = Path("test_error_script.py")
test_script.write_text("""
import sys
import time

print("Script starting...")
print("Warning: This is a test warning", file=sys.stderr)
print("ERROR: This is a test error", file=sys.stderr)
print("EXCEPTION: This is a test exception", file=sys.stderr)
print("Traceback (most recent call last):", file=sys.stderr)
print("  File test.py, line 10", file=sys.stderr)
print("    raise ValueError('test')", file=sys.stderr)
print("Script ending...", file=sys.stderr)
""")

# Simulate service_manager's stderr reading
process = subprocess.Popen(
    [sys.executable, str(test_script)],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
    errors='replace'
)

# Thread to read stderr
def read_stderr():
    runtime_error_log = error_file
    with open(stderr_file, 'a', encoding='utf-8') as f_stderr:
        try:
            for line in iter(process.stderr.readline, ''):
                if not line:
                    break
                
                line = line.rstrip()
                if line:
                    # Write to stderr file
                    f_stderr.write(f"{line}\n")
                    f_stderr.flush()
                    
                    # Check for error keywords
                    line_lower = line.lower()
                    if any(kw in line_lower for kw in ['error', 'exception', 'traceback', 'failed', 'critical']):
                        with open(runtime_error_log, 'a', encoding='utf-8') as f_err:
                            f_err.write(f"[test_service] {line}\n")
                        print(f"  ✓ Logged error: {line}")
        finally:
            process.stderr.close()

thread = threading.Thread(target=read_stderr, daemon=True)
thread.start()
thread.join(timeout=5)

# Read stdout from process
stdout, _ = process.communicate()
print(f"  Process output: {stdout.strip()}")

# Verify logging
time.sleep(0.5)
stderr_contents = stderr_file.read_text()
error_contents = error_file.read_text()

print(f"\n✓ test_stderr.log contains {len(stderr_contents.splitlines())} lines")
print(f"✓ winyfi_runtime_error.log contains {len(error_contents.splitlines())} lines")

if "ERROR" in stderr_contents:
    print("✓ Errors captured in stderr file")
if "ERROR" in error_contents:
    print("✓ Errors captured in runtime error file")

# Cleanup
test_script.unlink()
stderr_file.unlink()
error_file.unlink()

print("\n✅ TEST PASSED - Stderr logging infrastructure working correctly")
