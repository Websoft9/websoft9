#!/usr/bin/env python3

import sys
import os

# Add the src directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.config import ConfigManager

def test_backup_config():
    """Test loading backup configuration"""
    try:
        config_manager = ConfigManager("system.ini")
        
        print("=== Backup Repository Configuration ===")
        path = config_manager.get_value("backup_repo", "path")
        hostname = config_manager.get_value("backup_repo", "hostname")
        image = config_manager.get_value("backup_repo", "image", "restic/restic:latest")
        
        print(f"Repository Path: {path}")
        print(f"Hostname: {hostname}")
        print(f"Docker Image: {image}")
        
        print("\n=== Configuration loaded successfully ===")
        
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_backup_config()
    sys.exit(0 if success else 1)
