from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def exploration_now_iso() -> str:
    try:
        tz = ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat()
