# backend/sos.py
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, List

router = APIRouter()

# In-memory store for demo; replace with DB in production
ACTIVE_SOS: Dict[str, Dict] = {}

class SosStart(BaseModel):
    user_id: str
    lat: float
    lon: float
    route_id: Optional[str] = None
    note: Optional[str] = None

class SosUpdate(BaseModel):
    user_id: str
    lat: float
    lon: float

class SosStop(BaseModel):
    user_id: str

@router.post("/sos/start")
def sos_start(payload: SosStart):
    ACTIVE_SOS[payload.user_id] = {
        "start_time": datetime.utcnow().isoformat(),
        "last_update": datetime.utcnow().isoformat(),
        "lat": payload.lat,
        "lon": payload.lon,
        "route_id": payload.route_id,
        "note": payload.note,
        "active": True,
    }
    return {"status": "started", "user_id": payload.user_id}

@router.post("/sos/update")
def sos_update(payload: SosUpdate):
    if payload.user_id not in ACTIVE_SOS:
        return {"status": "error", "message": "SOS session not found"}
    ACTIVE_SOS[payload.user_id].update(
        {
            "lat": payload.lat,
            "lon": payload.lon,
            "last_update": datetime.utcnow().isoformat(),
        }
    )
    return {"status": "updated"}

@router.post("/sos/stop")
def sos_stop(payload: SosStop):
    data = ACTIVE_SOS.pop(payload.user_id, None)
    return {"status": "stopped", "previous": data}

@router.get("/sos/active")
def sos_active() -> List[Dict]:
    return [
        {"user_id": uid, **info}
        for uid, info in ACTIVE_SOS.items()
        if info.get("active")
    ]