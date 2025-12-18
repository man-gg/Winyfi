"""
Convert PNG to ICO for Windows application icon
Run this script to create icon.ico from your logo
"""
from PIL import Image
import os

def create_icon(png_path, ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]):
    """
    Convert PNG to ICO with multiple sizes
    
    Args:
        png_path: Path to source PNG file
        ico_path: Path to output ICO file
        sizes: List of (width, height) tuples for icon sizes
    """
    try:
        img = Image.open(png_path)
        
        # Convert RGBA if needed
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Create icon with multiple sizes
        img.save(ico_path, format='ICO', sizes=sizes)
        print(f"✅ Successfully created {ico_path}")
        print(f"   Sizes: {', '.join([f'{w}x{h}' for w, h in sizes])}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating icon: {e}")
        return False

if __name__ == "__main__":
    # Default: use logo1.png from assets/images
    source_png = os.path.join("assets", "images", "logo1.png")
    output_ico = "icon.ico"
    
    if not os.path.exists(source_png):
        print(f"❌ Source file not found: {source_png}")
        print("\nAvailable images:")
        for root, dirs, files in os.walk("assets"):
            for file in files:
                if file.endswith('.png'):
                    print(f"  - {os.path.join(root, file)}")
        print("\nEdit this script to use a different image.")
    else:
        create_icon(source_png, output_ico)
        print(f"\n📍 Icon created at: {os.path.abspath(output_ico)}")
