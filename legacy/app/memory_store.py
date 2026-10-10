import hashlib
from sqlalchemy import select
from app.db import Session
from app.models import Memory,Revision,Provenance,Audit,Outbox
from app.retention import expiry
async def write(p,w):
 async with Session.begin() as s:
  m=Memory(tenant_id=p.tenant_id,layer=w.layer,scope={**w.scope,"tenant_id":p.tenant_id},content=w.content,content_hash=hashlib.sha256(w.content.encode()).hexdigest(),classification=w.classification,confidence=w.confidence,expire_at=expiry(w.ttl_days))
  s.add(m);await s.flush();s.add(Revision(memory_id=m.id,version=1,content=w.content,reason="initial",source_ids=[w.source_id]));s.add(Provenance(memory_id=m.id,source_type=w.source_type,source_id=w.source_id,agent_id=p.agent_id));s.add(Audit(tenant_id=p.tenant_id,actor=p.agent_id,action="CREATE",memory_id=m.id));s.add(Outbox(event_type="memory.created",aggregate_id=str(m.id),payload={"tenant_id":p.tenant_id}))
  return str(m.id)
async def active(tenant,layers):
 async with Session() as s:
  r=await s.execute(select(Memory).where(Memory.tenant_id==tenant,Memory.layer.in_(layers),Memory.status=="ACTIVE"))
  return list(r.scalars())
