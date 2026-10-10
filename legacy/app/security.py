import hmac
from fastapi import Header,HTTPException
from app.config import settings
async def api_auth(x_api_key:str=Header(...)):
 if not hmac.compare_digest(x_api_key,settings.api_key):raise HTTPException(401,"invalid credential")
R={"PUBLIC":0,"INTERNAL":1,"CONFIDENTIAL":2,"RESTRICTED":3}
def clearance(roles):return 3 if "memory.restricted" in roles else 2 if "memory.confidential" in roles else 1
