#!/usr/bin/env python3
"""
Password Encryption Utility for Websoft9
Encrypts passwords using AES-256-CBC with a master key
"""

import os
import sys
import base64
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

def get_or_create_master_key(key_file="/websoft9/.secrets/master.key"):
    """Get existing master key or create a new one"""
    key_path = Path(key_file)
    
    # Ensure directory exists
    key_path.parent.mkdir(parents=True, exist_ok=True)
    
    if key_path.exists():
        # Read existing key
        with open(key_path, 'rb') as f:
            return f.read()
    else:
        # Generate new 32-byte key for AES-256
        key = os.urandom(32)
        with open(key_path, 'wb') as f:
            f.write(key)
        # Set restrictive permissions (only root can read)
        os.chmod(key_path, 0o600)
        return key

def encrypt_password(plaintext, key):
    """Encrypt password using AES-256-CBC"""
    # Generate random IV
    iv = os.urandom(16)
    
    # Pad plaintext to block size
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode()) + padder.finalize()
    
    # Encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    # Combine IV + ciphertext and encode to base64
    encrypted = base64.b64encode(iv + ciphertext).decode('utf-8')
    
    return f"AES256:{encrypted}"

def decrypt_password(encrypted_value, key):
    """Decrypt password (for verification)"""
    if not encrypted_value.startswith("AES256:"):
        return encrypted_value  # Not encrypted
    
    # Remove prefix and decode
    encrypted_data = base64.b64decode(encrypted_value[7:])
    
    # Extract IV and ciphertext
    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]
    
    # Decrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    
    # Unpad
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_data) + unpadder.finalize()
    
    return plaintext.decode('utf-8')

def main():
    if len(sys.argv) < 2:
        print("Usage: encrypt-password.py <password> [key_file]", file=sys.stderr)
        sys.exit(1)
    
    password = sys.argv[1]
    key_file = sys.argv[2] if len(sys.argv) > 2 else "/websoft9/.secrets/master.key"
    
    # Get or create master key
    key = get_or_create_master_key(key_file)
    
    # Encrypt password
    encrypted = encrypt_password(password, key)
    
    # Output encrypted value (without newline for easy capture)
    print(encrypted, end='')

if __name__ == "__main__":
    main()
