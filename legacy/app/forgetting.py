from sqlalchemy import select
from app.db import Session
from app.models import Memory,Audit,Outbox
async def forget(tenant,actor,id,reason):
 async with Session.begin() as s:
  m=(await s.execute(select(Memory).where(Memory.id==id,Memory.tenant_id==tenant))).scalar_one()
  m.status="FORGOTTEN";m.content="[FORGOTTEN]";s.add(Audit(tenant_id=tenant,actor=actor,action="FORGET",memory_id=m.id,data={"reason":reason}));s.add(Outbox(event_type="memory.forgotten",aggregate_id=str(m.id),payload={"tenant_id":tenant}))
 return {"status":"FORGOTTEN"}
