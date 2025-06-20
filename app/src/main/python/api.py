import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, UploadFile, File
from .session_manager import session_manager
from starlette.responses import FileResponse

router = APIRouter()


class ListenerRequest(BaseModel):
    uri: str


@router.post("/listeners")
async def create_listener(request: ListenerRequest):
    """Creates a new listener."""
    try:
        listener_id = await asyncio.to_thread(session_manager.create_listener, request.uri)
        return {"id": listener_id, "uri": request.uri}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/listeners")
async def get_listeners():
    """Returns a list of active listeners."""
    return await asyncio.to_thread(session_manager.get_listeners)


@router.delete("/listeners/{listener_id}")
async def remove_listener(listener_id: int):
    """Removes a listener."""
    try:
        await asyncio.to_thread(session_manager.remove_listener, listener_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions")
async def get_sessions():
    """Returns a list of active sessions."""
    return await asyncio.to_thread(session_manager.get_sessions)


@router.websocket("/sessions/{session_id}/ws")
async def session_websocket(websocket: WebSocket, session_id: int):
    """Establishes a WebSocket connection for a session."""
    await session_manager.handle_websocket(session_id, websocket)


@router.get("/sessions/{session_id}/fs")
async def list_files(session_id: int, path: str = "/"):
    """Lists files in a given directory of a session."""
    try:
        return await session_manager.list_files(session_id, path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/fs/cat")
async def read_file(session_id: int, path: str):
    """Reads the content of a file."""
    try:
        content = await session_manager.read_file(session_id, path)
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/fs/upload")
async def upload_file(session_id: int, destination_path: str, file: UploadFile = File(...)):
    """Uploads a file to the target session."""
    try:
        content = await file.read()
        return await session_manager.upload_file(session_id, content, destination_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/fs/download")
async def download_file(session_id: int, path: str):
    """Downloads a file from the target session."""
    try:
        file_path, filename = await session_manager.download_file(session_id, path)
        return FileResponse(path=file_path, filename=filename,
                            media_type='application/octet-stream')
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found or error downloading: {e}")


@router.get("/sessions/{session_id}/ps")
async def list_processes(session_id: int):
    """Lists processes in a session."""
    try:
        return await asyncio.to_thread(session_manager.list_processes, session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/privesc")
async def check_privesc(session_id: int):
    """Runs a new check for privilege escalation vulnerabilities."""
    try:
        return await session_manager.run_privesc_checks(session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/privesc/{exploit_id}")
async def run_exploit(session_id: int, exploit_id: str):
    """Runs a specific privilege escalation exploit."""
    try:
        return await session_manager.run_exploit(session_id, exploit_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))