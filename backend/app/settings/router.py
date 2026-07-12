from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])

VALID_THEMES = {"light", "dark", "system"}

class SettingsUpdateRequest(BaseModel):
    telegram_chat_id: Optional[str] = None
    expo_push_token: Optional[str] = None
    timezone: Optional[str] = None
    theme: Optional[str] = None
    active_indicators: Optional[List[str]] = None

@router.get("")
def get_settings(user_id: str = Depends(get_current_user), conn = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()

    if not row:
        # First time this user hits settings — return defaults, don't force a manual "create" step
        return {
            "user_id": user_id,
            "telegram_chat_id": None,
            "expo_push_token": None,
            "timezone": "Asia/Manila",
            "theme": "system",
            "active_indicators": ["VWAP", "RSI", "BOLLINGER", "SMA", "OBV", "ATR", "GARMAN_KLASS", "ZSCORE"],
        }
    return row

@router.put("")
def update_settings(
    payload: SettingsUpdateRequest,
    user_id: str = Depends(get_current_user),
    conn = Depends(get_db)
):
    if payload.theme is not None and payload.theme not in VALID_THEMES:
        raise HTTPException(status_code=400, detail=f"theme must be one of {VALID_THEMES}")

    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO user_settings (user_id)
            VALUES (%s)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))

        # Only update fields that were actually provided — partial updates, not full overwrites
        fields, values = [], []
        for field in ("telegram_chat_id", "expo_push_token", "timezone", "theme"):
            value = getattr(payload, field)
            if value is not None:
                fields.append(f"{field} = %s")
                values.append(value)

        if payload.active_indicators is not None:
            import json
            fields.append("active_indicators = %s")
            values.append(json.dumps(payload.active_indicators))

        if fields:
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(user_id)
            cursor.execute(f"""
                UPDATE user_settings SET {', '.join(fields)}
                WHERE user_id = %s
            """, values)

        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Settings update failed: {str(e)}")
    finally:
        cursor.close()