import asyncio
import traceback
from backend.enhanced_main import app, startup_event

async def test_startup():
    try:
        with open('debug_output.txt', 'w') as f:
            f.write("Testing startup...\n")
        await startup_event()
        with open('debug_output.txt', 'a') as f:
            f.write("Startup entered successfully!\n")
    except Exception as e:
        with open('debug_output.txt', 'a') as f:
            f.write("Startup failed with exception:\n")
            f.write(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_startup())
