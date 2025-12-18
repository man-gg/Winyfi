"""
Test the built EXE to verify it works correctly
Run: python test_exe.py
"""
import os
import sys
import subprocess
import time

def test_exe():
    exe_path = os.path.join('dist', 'Winyfi.exe')
    
    print("="*60)
    print("  TESTING WINYFI.EXE")
    print("="*60)
    
    if not os.path.exists(exe_path):
        print(f"\n❌ EXE not found: {exe_path}")
        print("\nBuild it first with: python build.py")
        return False
    
    print(f"\n✅ Found: {exe_path}")
    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"   Size: {size_mb:.2f} MB")
    
    print("\n" + "="*60)
    print("  LAUNCHING EXE...")
    print("="*60)
    print("\n⚠️  Check if the application window opens correctly")
    print("⚠️  Close the application when you're done testing")
    print("\nPress Ctrl+C to cancel if needed\n")
    
    try:
        # Launch the EXE
        process = subprocess.Popen([exe_path])
        
        print("✅ EXE launched successfully!")
        print(f"   Process ID: {process.pid}")
        print("\n📝 Testing checklist:")
        print("   [ ] Application window opens")
        print("   [ ] Custom icon is visible")
        print("   [ ] Login screen displays")
        print("   [ ] No error messages appear")
        print("   [ ] Application closes cleanly")
        
        # Wait for process to complete
        print("\n⏳ Waiting for you to close the application...")
        process.wait()
        
        if process.returncode == 0:
            print("\n✅ Application closed successfully!")
            return True
        else:
            print(f"\n⚠️  Application closed with code: {process.returncode}")
            print("   Check for errors in winyfi_error.log")
            return False
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
        if 'process' in locals():
            process.terminate()
        return False
    except Exception as e:
        print(f"\n❌ Error testing EXE: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_exe()
    
    print("\n" + "="*60)
    if success:
        print("  TEST PASSED ✅")
    else:
        print("  TEST FAILED ❌")
    print("="*60)
    
    sys.exit(0 if success else 1)
