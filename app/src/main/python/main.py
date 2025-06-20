import uvicorn
from fastapi import FastAPI
from .api import router as api_router
from .session_manager import session_manager

app = FastAPI(
    title="pwncatharsis",
    description="A graphical interface for the `pwncat` post-exploitation toolkit.",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initializes the session manager on startup."""
    session_manager.initialize()


def start():
    """Function to be called from Kotlin to start the server."""
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    server.run()
