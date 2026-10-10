"""MCP stdio transport. Client process inherits a fixed agent identity from env.

Enable via `pip install -e '.[mcp]'` then configure your MCP client to execute
`fabric-mcp`. No network listener is started by this module.
"""
import json
import os
from .core import Fabric, Principal, MemoryInput


def make_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError('Install MCP support: pip install -e ".[mcp]"') from exc
    s=FastMCP("context-fabric")
    p=Principal(tenant=os.getenv("FABRIC_TENANT","local"),agent=os.getenv("FABRIC_AGENT","mcp"),
                subject=os.getenv("FABRIC_SUBJECT","local-user"),clearance=os.getenv("FABRIC_CLEARANCE","INTERNAL"),
                roles=tuple(x.strip() for x in os.getenv("FABRIC_ROLES","").split(",") if x.strip()))
    db=Fabric()

    @s.tool()
    def memory_remember(content:str,layer:str="semantic",project:str="",source_id:str="mcp") -> str:
        """Remember project-specific context with provenance."""
        return json.dumps(db.write(p,MemoryInput(content=content,layer=layer,scope={"project":project} if project else {},source_id=source_id)))

    @s.tool()
    def memory_recall(query:str,project:str="",limit:int=5,token_budget:int=1200,
                      mode:str="hybrid",graph_depth:int=0) -> str:
        """Retrieve authorized, provenance-rich UNTRUSTED context within a token budget."""
        return json.dumps(db.search(p,query,scope={"project":project} if project else None,
                                    limit=limit,token_budget=token_budget,retrieval_mode=mode,graph_depth=graph_depth))

    @s.tool()
    def memory_list(limit:int=20) -> str:
        """List visible memories for this agent."""
        return json.dumps(db.list_memories(p,limit=limit))

    @s.tool()
    def memory_forget(memory_id:str) -> str:
        """Scrub owned memory (including historical versions)."""
        return json.dumps(db.forget(p,memory_id))

    @s.tool()
    def memory_revise(memory_id:str,content:str,expected_version:int) -> str:
        """Update with an expected version to prevent lost updates."""
        return json.dumps(db.update(p,memory_id,content,expected_version))

    @s.tool()
    def memory_conflicts(content:str) -> str:
        """Find potentially overlapping memories for human review."""
        return json.dumps(db.conflicts(p,content))

    @s.tool()
    def memory_neighbors(memory_id:str,depth:int=1) -> str:
        """Traverse explicit relations while preserving ACL filtering."""
        return json.dumps(db.neighbors(p,memory_id,depth=depth))

    @s.tool()
    def memory_history(memory_id:str) -> str:
        """Read owned memory revision trail, preserving provenance."""
        return json.dumps(db.history(p,memory_id))

    @s.tool()
    def memory_grant(to_agent:str,layer:str="semantic",project:str="",ttl_days:int=7) -> str:
        """Explicitly share selected memory layer/scope with another tenant-local agent."""
        return json.dumps(db.grant(p,to_agent,[layer],scope={"project":project} if project else None,ttl_days=ttl_days))

    @s.tool()
    def memory_revoke(grant_id:str) -> str:
        """Immediately revoke an owned share grant."""
        return json.dumps(db.revoke(p,grant_id))

    @s.tool()
    def memory_link(from_id:str,to_id:str,relation:str="related_to") -> str:
        """Create explicit memory-graph edge if both nodes are accessible."""
        return json.dumps(db.link(p,from_id,to_id,relation))

    @s.tool()
    def memory_profile_get(name:str) -> str:
        """Load owned typed profile by name."""
        return json.dumps(db.profile_get(p,name))

    @s.tool()
    def memory_profile_set(name:str,fields_json:str,schema_json:str,expected_version:int=0) -> str:
        """Save a typed versioned agent profile; fields_json and schema_json are JSON objects."""
        return json.dumps(db.profile_set(p,name,json.loads(fields_json),json.loads(schema_json),expected_version))

    @s.tool()
    def memory_consolidation_candidates(threshold:float=.85,limit:int=20) -> str:
        """Identify possible duplicates; a human must approve any merge."""
        return json.dumps(db.consolidate_candidates(p,threshold,limit))

    @s.tool()
    def memory_integrity() -> str:
        """Check local SQLite file integrity. Only metadata, no content."""
        if not p.can("admin"):
            return json.dumps({"error":"admin role required"})
        return json.dumps(db.verify_integrity())

    return s


def main():
    make_server().run(transport="stdio")


if __name__=="__main__":main()
