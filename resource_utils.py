"""
Resource path utility for handling paths in both development and frozen (PyInstaller) environments.
Use this for loading assets, configuration files, and other resources.
"""

import os
import sys


def get_base_path():
    """
    Get the base application directory.
    Works correctly in both development and frozen (PyInstaller) executables.
    
    Returns:
        str: Base directory path where resources are located
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller temp folder with bundled files
            return sys._MEIPASS
        else:
            # Fallback to executable directory
            return os.path.dirname(sys.executable)
    else:
        # Running as script in development
        return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
    """
    Get the full path to a resource file.
    Automatically detects if running as frozen executable or script.
    
    Args:
        relative_path (str): Path relative to base directory
        
    Returns:
        str: Full absolute path to the resource
        
    Example:
        icon_path = get_resource_path('icon.ico')
        logo_path = get_resource_path('assets/images/logo1.png')
    """
    base_path = get_base_path()
    full_path = os.path.join(base_path, relative_path)
    return full_path


def ensure_directory(relative_path):
    """
    Ensure a directory exists relative to base path.
    Creates it if it doesn't exist.
    
    Args:
        relative_path (str): Directory path relative to base directory
        
    Returns:
        str: Full absolute path to directory
    """
    full_path = get_resource_path(relative_path)
    os.makedirs(full_path, exist_ok=True)
    return full_path


def resource_exists(relative_path):
    """
    Check if a resource file exists.
    
    Args:
        relative_path (str): Path relative to base directory
        
    Returns:
        bool: True if resource exists, False otherwise
    """
    full_path = get_resource_path(relative_path)
    return os.path.exists(full_path)


def list_resources(relative_dir):
    """
    List all files in a resource directory.
    
    Args:
        relative_dir (str): Directory path relative to base
        
    Returns:
        list: List of filenames in the directory
    """
    full_path = get_resource_path(relative_dir)
    if os.path.exists(full_path):
        return os.listdir(full_path)
    return []
