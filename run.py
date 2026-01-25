"""
Startup script for the application.
Sets the Windows event loop policy before Uvicorn starts.
"""
import sys
import asyncio

# Fix for Playwright on Windows - must be set before any async operations
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
