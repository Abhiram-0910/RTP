import sys
import traceback

def main():
    try:
        print("Importing backend.enhanced_main...")
        from backend.enhanced_main import app
        print("Import successful!")
    except Exception as e:
        print("Import failed with exception:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
