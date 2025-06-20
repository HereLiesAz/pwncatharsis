from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile
from typing import List
from pydantic import BaseModel
from .session_manager import session_manager
from starlette.responses import FileResponse

router = APIRouter()


class ListenerRequest(BaseModel):
    listener_uri: str


@router.post("/listeners")
async def create_listener(request: ListenerRequest):
    """Creates a new listener."""
    try:
        listener_id = await session_manager.create_listener(request.listener_uri)
        return {"listener_id": listener_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/listeners")
async def get_listeners():
    """Returns a list of active listeners."""
    return await session_manager.get_listeners()


@router.delete("/listeners/{listener_id}")
async def remove_listener(listener_id: int):
    """Removes a listener."""
    try:
        await session_manager.remove_listener(listener_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions")
async def get_sessions():
    """Returns a list of active sessions."""
    return await session_manager.get_sessions()


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
        content, name = await session_manager.read_file(session_id, path)
        return {"name": name, "content": content}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/fs/upload")
async def upload_file(session_id: int, destination_path: str, file: UploadFile = File(...)):
    """Uploads a file to the target session."""
    try:
        return await session_manager.upload_file(session_id, file, destination_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/fs/download")
async def download_file(session_id: int, path: str):
    """Downloads a file from the target session."""
    try:
        return await session_manager.download_file(session_id, path)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found or error downloading: {e}")


@router.get("/sessions/{session_id}/ps")
async def list_processes(session_id: int):
    """Lists processes in a session."""
    try:
        return await session_manager.list_processes(session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/sessions/{session_id}/ps/{pid}")
async def kill_process(session_id: int, pid: int):
    """Kills a process by its PID."""
    try:
        await session_manager.kill_process(session_id, pid)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/net")
async def get_network_info(session_id: int):
    """Gets network interface information."""
    try:
        return await session_manager.get_network_info(session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/loot")
async def get_loot(session_id: int):
    """Finds and returns loot from the session."""
    try:
        return await session_manager.find_loot(session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/privesc")
async def get_privesc(session_id: int):
    """Gets cached privilege escalation vulnerabilities."""
    try:
        return await session_manager.get_privesc_facts(session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/privesc")
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
