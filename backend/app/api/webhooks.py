"""
Webhook endpoints for external AI service callbacks.
GeminiGen AI sends video generation results here.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# In-memory store for webhook results (Redis in production)
_webhook_results: dict[str, dict] = {}


@router.post("/geminigen")
async def geminigen_webhook(request: Request):
    """
    Receive video generation completion events from GeminiGen AI.
    
    Expected payload:
    {
        "event_name": "VIDEO_GENERATION_COMPLETED",
        "event_uuid": "...",
        "data": {
            "uuid": "...",
            "media_url": "https://...",
            "status": 2,
            "status_percentage": 100
        }
    }
    """
    try:
        payload = await request.json()
        event_name = payload.get("event_name", "")
        data = payload.get("data", {})
        uuid = data.get("uuid", "")

        logger.info(f"📥 [WEBHOOK] GeminiGen event: {event_name} | UUID: {uuid}")

        if not uuid:
            raise HTTPException(status_code=400, detail="Missing UUID in webhook data")

        # Store the result keyed by UUID
        _webhook_results[uuid] = {
            "event": event_name,
            "media_url": data.get("media_url"),
            "status": data.get("status"),
            "error_message": data.get("error_message", ""),
        }

        logger.info(f"✅ [WEBHOOK] Stored result for UUID: {uuid}")
        return {"status": "ok", "uuid": uuid}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Error processing GeminiGen webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


def get_webhook_result(uuid: str) -> dict | None:
    """Check if a webhook result is available for the given UUID."""
    return _webhook_results.pop(uuid, None)
