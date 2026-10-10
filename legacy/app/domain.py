from pydantic import BaseModel,Field
from typing import Literal,Any
MemoryLayer=Literal["working","session","episodic","semantic","entity","procedural"]
class Principal(BaseModel):
 tenant_id:str;subject_id:str;agent_id:str;roles:list[str]=Field(default_factory=list)
class MemoryWrite(BaseModel):
 layer:MemoryLayer;scope:dict[str,str];content:str;source_type:str="agent";source_id:str;confidence:float=1.0
 classification:Literal["PUBLIC","INTERNAL","CONFIDENTIAL","RESTRICTED"]="INTERNAL";ttl_days:int|None=None
class RetrievalRequest(BaseModel):
 principal:Principal;query:str;layers:list[MemoryLayer]=Field(default_factory=lambda:["episodic","semantic","entity","procedural"]);scope:dict[str,str]=Field(default_factory=dict);purpose:str="context";limit:int=10
class ContextItem(BaseModel):
 memory_id:str;layer:MemoryLayer;content:str;score:float;provenance:dict[str,Any];classification:str
