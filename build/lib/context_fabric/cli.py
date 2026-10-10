"""`fabric` local-first command-line interface (no server required)."""
import argparse
import json
import os
import sys
from .core import Fabric, Principal, MemoryInput


def build_parser():
    p=argparse.ArgumentParser(prog="fabric",description="Persistent context fabric for AI agents")
    p.add_argument("--db",default=os.getenv("FABRIC_DB"),help="SQLite database path")
    p.add_argument("--tenant",default=os.getenv("FABRIC_TENANT","local"))
    p.add_argument("--agent",default=os.getenv("FABRIC_AGENT","cli"))
    p.add_argument("--subject",default=os.getenv("FABRIC_SUBJECT","local-user"))
    p.add_argument("--clearance",default=os.getenv("FABRIC_CLEARANCE","INTERNAL"))
    p.add_argument("--roles",default=os.getenv("FABRIC_ROLES","admin,procedure_approver"))
    sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("remember",help="Save memory");a.add_argument("content");a.add_argument("--layer",default="semantic");a.add_argument("--source",default="cli");a.add_argument("--project",default=None);a.add_argument("--ttl",type=int,default=90)
    a=sub.add_parser("recall",help="Hybrid retrieve");a.add_argument("query");a.add_argument("--project",default=None);a.add_argument("--limit",type=int,default=5)
    a=sub.add_parser("list",help="List visible memories");a.add_argument("--limit",type=int,default=50)
    a=sub.add_parser("forget",help="Forget memory and scrub revision content");a.add_argument("memory_id")
    a=sub.add_parser("revise",help="Optimistic revision");a.add_argument("memory_id");a.add_argument("content");a.add_argument("--version",type=int,required=True)
    a=sub.add_parser("grant",help="Allow another agent to read selected memory");a.add_argument("agent");a.add_argument("--layer",default="semantic");a.add_argument("--project",default=None)
    a=sub.add_parser("revoke",help="Revoke a share grant");a.add_argument("grant_id")
    a=sub.add_parser("profile-put",help="Update a structured profile");a.add_argument("name");a.add_argument("--fields",required=True,help="JSON object");a.add_argument("--schema",required=True,help="JSON field->type mapping");a.add_argument("--version",type=int)
    a=sub.add_parser("profile-get",help="Read a structured profile");a.add_argument("name")
    a=sub.add_parser("consolidate",help="Find duplicate candidates for human review");a.add_argument("--threshold",type=float,default=.85)
    a=sub.add_parser("audit",help="Read tenant audit metadata (admin only)")
    a=sub.add_parser("audit-verify",help="Verify tenant audit HMAC chain (admin only)")
    a=sub.add_parser("outbox",help="Read tenant change events (admin only)")
    a=sub.add_parser("link",help="Link memory graph nodes");a.add_argument("from_id");a.add_argument("to_id");a.add_argument("--relation",default="related_to")
    a=sub.add_parser("neighbors");a.add_argument("memory_id")
    a=sub.add_parser("conflicts");a.add_argument("content")
    a=sub.add_parser("sweep",help="Scrub expired memories owned by agent")
    a=sub.add_parser("verify",help="Check SQLite integrity and table counts")
    a=sub.add_parser("backup",help="Create a consistent backup without overwriting")
    a.add_argument("destination")
    a=sub.add_parser("restore-to-new",help="Restore verified backup to a NEW offline database path")
    a.add_argument("source");a.add_argument("destination")
    a=sub.add_parser("checkpoint",help="Checkpoint SQLite WAL (requires exclusive maintenance window)")
    a=sub.add_parser("key-hash",help="Interactively create PBKDF2 API-key verifier")
    a=sub.add_parser("benchmark",help="Run deterministic local retrieval benchmark")
    a=sub.add_parser("demo",help="Create two memories, retrieve one, then forget both")
    a=sub.add_parser("serve",help="Start HTTP API");a.add_argument("--host",default="127.0.0.1");a.add_argument("--port",type=int,default=8000)
    a=sub.add_parser("connect",help="Print MCP configuration for agent");a.add_argument("client",choices=["claude","cursor","codex","generic"])
    return p


def main(argv=None):
    parser=build_parser(); a=parser.parse_args(argv)
    if a.cmd=="key-hash":
        from getpass import getpass
        from .security import hash_api_key
        key = getpass("Paste API key (input hidden): ")
        print(hash_api_key(key));return
    if a.cmd=="restore-to-new":
        from .backup import restore_as_new
        print(json.dumps(restore_as_new(a.source,a.destination),indent=2));return
    if a.cmd=="serve":
        from .security import validate_security_config
        validate_security_config()
        if not any(os.getenv(k) for k in ("FABRIC_API_KEY", "FABRIC_CREDENTIALS_JSON", "FABRIC_HASHED_CREDENTIALS_JSON", "FABRIC_OIDC_ISSUER")):
            parser.error("configure API key, hashed service key or OIDC")
        import uvicorn
        uvicorn.run("context_fabric.api:app",host=a.host,port=a.port)
        return
    if a.cmd=="connect":
        import shutil
        binary=shutil.which("fabric-mcp") or "fabric-mcp"
        from pathlib import Path
        config={"command":binary,"args":[],"env":{"FABRIC_DB":str(Path(a.db or "~/.context-fabric/memory.db").expanduser().absolute()),"FABRIC_TENANT":a.tenant,"FABRIC_AGENT":a.agent}}
        if a.client=="codex":
            env=config["env"]
            print(f'[mcp_servers.fabric]\ncommand = "{binary}"\nenv = {{ FABRIC_DB = "{env["FABRIC_DB"]}", FABRIC_TENANT = "{env["FABRIC_TENANT"]}", FABRIC_AGENT = "{env["FABRIC_AGENT"]}" }}\n')
        else:
            print(json.dumps({"mcpServers":{"fabric":config}},indent=2))
        return
    if a.cmd=="benchmark":
        from .benchmark import run
        print(json.dumps(run(),indent=2));return
    p=Principal(tenant=a.tenant,agent=a.agent,subject=a.subject,clearance=a.clearance,roles=tuple(x for x in a.roles.split(",") if x))
    db=Fabric(a.db)
    try:
        if a.cmd=="remember":result=db.write(p,MemoryInput(content=a.content,layer=a.layer,source_id=a.source,scope={"project":a.project} if a.project else {},ttl_days=a.ttl,verified=a.layer=="procedural"))
        elif a.cmd=="recall":result=db.search(p,a.query,scope={"project":a.project} if a.project else None,limit=a.limit)
        elif a.cmd=="list":result=db.list_memories(p,limit=a.limit)
        elif a.cmd=="forget":result=db.forget(p,a.memory_id)
        elif a.cmd=="revise":result=db.update(p,a.memory_id,a.content,a.version)
        elif a.cmd=="grant":result=db.grant(p,a.agent,[a.layer],scope={"project":a.project} if a.project else None)
        elif a.cmd=="revoke":result=db.revoke(p,a.grant_id)
        elif a.cmd=="profile-put":result=db.profile_set(p,a.name,json.loads(a.fields),json.loads(a.schema),expected_version=a.version)
        elif a.cmd=="profile-get":result=db.profile_get(p,a.name)
        elif a.cmd=="consolidate":result=db.consolidate_candidates(p,a.threshold)
        elif a.cmd=="audit":result=db.audit_events(p)
        elif a.cmd=="audit-verify":result=db.verify_audit_chain(p)
        elif a.cmd=="outbox":result=db.outbox_events(p)
        elif a.cmd=="link":result=db.link(p,a.from_id,a.to_id,a.relation)
        elif a.cmd=="neighbors":result=db.neighbors(p,a.memory_id)
        elif a.cmd=="conflicts":result=db.conflicts(p,a.content)
        elif a.cmd=="sweep":result=db.sweep_expired(p)
        elif a.cmd=="verify":result=db.verify_integrity()
        elif a.cmd=="backup":result=db.backup(a.destination)
        elif a.cmd=="checkpoint":result=db.checkpoint()
        elif a.cmd=="demo":
            r1=db.write(p,MemoryInput(content="The payments API uses JWT with jose middleware",source_id="demo",scope={"project":"demo"}))
            r2=db.write(p,MemoryInput(content="Project decisions must be reviewed in a pull request",source_id="demo",scope={"project":"demo"}))
            result={"created":[r1,r2],"retrieval":db.search(p,"JWT middleware",scope={"project":"demo"}),
                    "cleanup":[db.forget(p,r1["memory_id"]),db.forget(p,r2["memory_id"])]}
        else:parser.error("unsupported command")
        print(json.dumps(result,indent=2,default=str))
    finally:db.close()


if __name__=="__main__":main()
