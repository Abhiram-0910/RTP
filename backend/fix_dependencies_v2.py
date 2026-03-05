import subprocess
import sys

def install_with_constraints():
    # Install both packages in one go with specific versions
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", 
        "sentence-transformers==2.2.2", 
        "huggingface_hub==0.19.4"
    ])

print("Fixing dependencies (Second Attempt)...")

try:
    install_with_constraints()
    print("Dependencies fixed! huggingface_hub should be 0.19.4")
except Exception as e:
    print(f"Error: {e}")
