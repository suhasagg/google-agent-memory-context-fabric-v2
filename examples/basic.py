"""Run after `pip install -e .`: python examples/basic.py"""
from context_fabric import Fabric, Principal, MemoryInput

p=Principal(tenant="demo",agent="coding-assistant",subject="developer")
db=Fabric(":memory:")
try:
    a=db.write(p,MemoryInput(content="We use Go for distributed services and pytest for Python tests",
        source_type="example",source_id="docs/demo",scope={"project":"platform"}))
    b=db.write(p,MemoryInput(content="Architecture decisions are captured as ADRs",
        source_type="example",source_id="docs/demo",scope={"project":"platform"}))
    db.link(p,a["memory_id"],b["memory_id"],"related_to")
    print(db.search(p,"Python tests",scope={"project":"platform"},graph_depth=1))
finally:
    db.close()
