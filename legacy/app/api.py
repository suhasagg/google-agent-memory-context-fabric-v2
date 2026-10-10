from fastapi import APIRouter,Depends
from pydantic import BaseModel
from uuid import UUID
from app.security import api_auth
from app.domain import Principal,MemoryWrite,RetrievalRequest
from app.memory_store import write
from app.context_manager import build
from app.forgetting import forget
router=APIRouter(prefix="/v1",dependencies=[Depends(api_auth)])
class W(BaseModel):principal:Principal;memory:MemoryWrite
class F(BaseModel):principal:Principal;reason:str
@router.post("/memories")
async def create(x:W):return {"memory_id":await write(x.principal,x.memory)}
@router.post("/context")
async def context(x:RetrievalRequest):return await build(x)
@router.post("/memories/{id}/forget")
async def remove(id:UUID,x:F):return await forget(x.principal.tenant_id,x.principal.agent_id,id,x.reason)
