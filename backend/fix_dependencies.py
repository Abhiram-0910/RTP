import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def uninstall(package):
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", package])

print("Fixing dependencies...")

# Uninstall conflicting packages
try:
    uninstall("huggingface_hub")
    uninstall("sentence-transformers")
except:
    pass

# Install compatible versions
# Using older compatible versions that are known to work together
install("huggingface_hub==0.19.4")
install("sentence-transformers==2.2.2")

print("Dependencies fixed! You can now run the backend.")
