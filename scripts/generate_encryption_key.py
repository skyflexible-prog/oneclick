
"""
Generate encryption key for API credentials
Run this once and save the key to .env file
"""

from cryptography.fernet import Fernet

def generate_key():
    """Generate a new Fernet encryption key"""
    key = Fernet.generate_key()
    print("\n" + "="*60)
    print("ENCRYPTION KEY GENERATED")
    print("="*60)
    print(f"\n{key.decode()}\n")
    print("Copy this key to your .env file as ENCRYPTION_KEY")
    print("KEEP THIS KEY SECURE AND NEVER SHARE IT!")
    print("="*60 + "\n")
    
    return key.decode()

if __name__ == "__main__":
    generate_key()
  
