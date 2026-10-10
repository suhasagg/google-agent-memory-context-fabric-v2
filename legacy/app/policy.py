from app.security import R,clearance
def can_read(p,m,scope):
 if m.tenant_id!=p.tenant_id or R.get(m.classification,99)>clearance(p.roles):return False
 if any(m.scope.get(k)!=v for k,v in scope.items()):return False
 owner=m.scope.get("agent_id")
 return not owner or owner==p.agent_id or "memory.cross_agent" in p.roles
def can_write(p,w):return w.scope.get("tenant_id",p.tenant_id)==p.tenant_id
