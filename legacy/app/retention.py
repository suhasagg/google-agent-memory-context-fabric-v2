from datetime import datetime,timedelta,timezone
from app.config import settings
def expiry(days):return datetime.now(timezone.utc)+timedelta(days=settings.default_ttl_days if days is None else days)
