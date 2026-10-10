from types import SimpleNamespace
from app.domain import Principal
from app.policy import can_read
def test_isolation():
 p=Principal(tenant_id="a",subject_id="u",agent_id="x")
 m=SimpleNamespace(tenant_id="b",classification="INTERNAL",scope={})
 assert not can_read(p,m,{})
