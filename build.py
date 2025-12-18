"""
Build script for creating Winyfi EXE and installer
Run: python build.py
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def print_step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")

def check_required_files():
    """Check if all required files exist"""
    print_step("STEP 1: Verifying required files")
    
    required_files = [
        'main.py',
        'winyfi.spec',
        'db_config.json',
        'icon.ico',
        'resource_utils.py',
        'dashboard.py',
        'login.py',
        'db.py',
    ]
    
    required_dirs = [
        'assets',
        'assets/images',
        'routerLocImg',
        'client_window',
        'client_window/tabs',
        'migrations',
    ]
    
    all_good = True
    
    # Check files
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - MISSING!")
            all_good = False
    
    # Check directories
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path}/")
        else:
            print(f"❌ {dir_path}/ - MISSING!")
            all_good = False
    
    if not all_good:
        print("\n⚠️  Some required files/directories are missing!")
        print("Please ensure all project files are present.")
        return False
    
    return True

def clean_build():
    """Remove old build artifacts"""
    print_step("STEP 2: Cleaning previous builds")
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for d in dirs_to_clean:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f"✅ Cleaned {d}/")
            except Exception as e:
                print(f"⚠️  Could not clean {d}/: {e}")
    
    # Clean pycache recursively
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            try:
                shutil.rmtree(os.path.join(root, '__pycache__'))
            except:
                pass
    
    print("✅ Cleaned all build artifacts")

def check_icon():
    """Check if icon.ico exists"""
    print_step("STEP 3: Verifying icon file")
    
    if not os.path.exists('icon.ico'):
        print("❌ icon.ico not found!")
        print("\nTo create an icon:")
        print("1. Run: python create_icon.py")
        print("2. Or provide your own icon.ico file")
        
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            return False
    else:
        size_kb = os.path.getsize('icon.ico') / 1024
        print(f"✅ icon.ico found ({size_kb:.1f} KB)")
    
    return True

def verify_dependencies():
    """Verify all Python dependencies are installed"""
    print_step("STEP 4: Verifying Python dependencies")
    
    required_packages = [
        'ttkbootstrap',
        'mysql-connector-python',
        'requests',
        'matplotlib',
        'PIL',
        'psutil',
        'scapy',
        'pandas',
        'openpyxl',
        'reportlab',
        'zeroconf',
    ]
    
    missing = []
    for package in required_packages:
        try:
            # Handle special cases
            if package == 'PIL':
                __import__('PIL')
            elif package == 'mysql-connector-python':
                __import__('mysql.connector')
            else:
                __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NOT INSTALLED")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing {len(missing)} package(s)")
        print("Installing missing packages...")
        try:
            for package in missing:
                subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                             check=True, capture_output=True)
                print(f"✅ Installed {package}")
        except Exception as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    
    return True

def check_pyinstaller():
    """Check if PyInstaller is installed"""
    print_step("STEP 5: Checking PyInstaller")
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', 'pyinstaller'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    version = line.split(':', 1)[1].strip()
                    print(f"✅ PyInstaller {version} is installed")
                    return True
        
        raise ImportError("PyInstaller not found")
            
    except (subprocess.SubprocessError, ImportError):
        print("⚠️  PyInstaller not found, installing...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], 
                         check=True, capture_output=True)
            print("✅ PyInstaller installed successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to install PyInstaller: {e}")
            return False

def build_exe():
    """Build EXE using PyInstaller"""
    print_step("STEP 6: Building EXE with PyInstaller")
    
    try:
        if os.path.exists('winyfi.spec'):
            print("📄 Using winyfi.spec configuration...")
            result = subprocess.run(
                ['pyinstaller', 'winyfi.spec', '--clean', '--noconfirm'],
                capture_output=True, 
                text=True
            )
        else:
            print("❌ winyfi.spec not found!")
            return False
        
        if result.returncode != 0:
            print("❌ Build failed!")
            print("\n--- Build Output ---")
            print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
            if result.stderr:
                print("\n--- Error Output ---")
                print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
            return False
        
        # Verify EXE was created
        exe_path = os.path.join('dist', 'Winyfi.exe')
        if not os.path.exists(exe_path):
            print(f"❌ EXE not found at {exe_path}")
            return False
        
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"✅ EXE built successfully!")
        print(f"   Location: {os.path.abspath(exe_path)}")
        print(f"   Size: {size_mb:.2f} MB")
        
        # Copy necessary files to dist folder
        print("\n📋 Copying configuration and resource files...")
        files_to_copy = [
            'db_config.json',
            'README_SETUP.txt',
            'winyfi.sql',
            'check_database.bat',
            'check_mysql_before_launch.bat',
            'README.md',
            'icon.ico',
        ]
        
        for file in files_to_copy:
            if os.path.exists(file):
                try:
                    shutil.copy2(file, 'dist')
                    print(f"   ✅ {file}")
                except Exception as e:
                    print(f"   ⚠️  Could not copy {file}: {e}")
        
        # Copy entire directories
        dirs_to_copy = [
            ('assets', 'dist/assets'),
            ('routerLocImg', 'dist/routerLocImg'),
            ('migrations', 'dist/migrations'),
        ]
        
        for src, dst in dirs_to_copy:
            if os.path.exists(src):
                try:
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    print(f"   ✅ {src}/")
                except Exception as e:
                    print(f"   ⚠️  Could not copy {src}/: {e}")
        
        return True
            
    except Exception as e:
        print(f"❌ Error during build: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_installer():
    """Create installer using Inno Setup"""
    print_step("STEP 7: Creating installer (optional)")
    
    # Common Inno Setup locations
    inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    ]
    
    inno_compiler = None
    for path in inno_paths:
        if os.path.exists(path):
            inno_compiler = path
            break
    
    if not inno_compiler:
        print("⚠️  Inno Setup not found")
        print("\nTo create an installer:")
        print("1. Download: https://jrsoftware.org/isinfo.php")
        print("2. Install Inno Setup 6")
        print("3. Run: python build.py")
        print("\nFor now, you can distribute the standalone EXE from dist/Winyfi.exe")
        return False
    
    if not os.path.exists('installer.iss'):
        print("⚠️  installer.iss not found! Skipping installer creation.")
        return False
    
    try:
        print(f"Using Inno Setup: {inno_compiler}")
        result = subprocess.run([inno_compiler, 'installer.iss'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Installer created successfully!")
            output_dir = 'installer_output'
            if os.path.exists(output_dir):
                for file in os.listdir(output_dir):
                    if file.endswith('.exe'):
                        installer_path = os.path.join(output_dir, file)
                        size_mb = os.path.getsize(installer_path) / (1024 * 1024)
                        print(f"   Location: {os.path.abspath(installer_path)}")
                        print(f"   Size: {size_mb:.2f} MB")
            return True
        else:
            print("❌ Installer creation failed!")
            if result.stderr:
                print(result.stderr[:500])
            return False
            
    except Exception as e:
        print(f"❌ Error creating installer: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("  WINYFI BUILD SCRIPT")
    print("  Compile to Windows .EXE with PyInstaller")
    print("="*60)
    
    # Step 1: Verify files
    if not check_required_files():
        print("\n❌ Build aborted: Missing files")
        return
    
    # Step 2: Clean
    clean_build()
    
    # Step 3: Check icon
    if not check_icon():
        print("\n❌ Build aborted")
        return
    
    # Step 4: Verify dependencies
    if not verify_dependencies():
        print("\n❌ Build aborted: Dependency check failed")
        return
    
    # Step 5: Check PyInstaller
    if not check_pyinstaller():
        print("\n❌ Build aborted: PyInstaller not available")
        return
    
    # Step 6: Build EXE
    if not build_exe():
        print("\n❌ Build failed!")
        return
    
    # Step 7: Create installer (optional)
    create_installer()
    
    # Summary
    print_step("BUILD COMPLETE! ✅")
    print("\n📦 OUTPUT FILES:")
    exe_path = os.path.abspath('dist/Winyfi.exe')
    if os.path.exists(exe_path):
        print(f"   EXE: {exe_path}")
        print(f"   Size: {os.path.getsize(exe_path) / (1024*1024):.2f} MB")
    
    if os.path.exists('installer_output'):
        for file in os.listdir('installer_output'):
            if file.endswith('.exe'):
                installer_path = os.path.abspath(os.path.join('installer_output', file))
                print(f"   Installer: {installer_path}")
    
    print("\n🚀 NEXT STEPS:")
    print("   1. Test the EXE: dist/Winyfi.exe")
    print("   2. Ensure MySQL is running (XAMPP/WAMP)")
    print("   3. Create 'winyfi' database")
    print("   4. Import db schema: winyfi.sql")
    print("\n✅ Ready to distribute!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
