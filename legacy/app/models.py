import uuid
from datetime import datetime
from sqlalchemy import String,Text,Float,DateTime,Boolean,Integer
from sqlalchemy.dialects.postgresql import UUID,JSONB
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.sql import func
from app.db import Base
def uid():return uuid.uuid4()
class Memory(Base):
 __tablename__="memories";id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uid);tenant_id:Mapped[str]=mapped_column(String(128),index=True);layer:Mapped[str]=mapped_column(String(32),index=True);scope:Mapped[dict]=mapped_column(JSONB);content:Mapped[str]=mapped_column(Text);content_hash:Mapped[str]=mapped_column(String(64),index=True);classification:Mapped[str]=mapped_column(String(32));confidence:Mapped[float]=mapped_column(Float);status:Mapped[str]=mapped_column(String(32),default="ACTIVE",index=True);version:Mapped[int]=mapped_column(Integer,default=1);expire_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class Revision(Base):
 __tablename__="memory_revisions";id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uid);memory_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),index=True);version:Mapped[int]=mapped_column(Integer);content:Mapped[str]=mapped_column(Text);reason:Mapped[str]=mapped_column(Text);source_ids:Mapped[list]=mapped_column(JSONB)
class Provenance(Base):
 __tablename__="provenance";id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uid);memory_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),index=True);source_type:Mapped[str]=mapped_column(String(64));source_id:Mapped[str]=mapped_column(String(256));agent_id:Mapped[str]=mapped_column(String(256));evidence:Mapped[dict]=mapped_column(JSONB,default=dict)
class ACL(Base):
 __tablename__="memory_acl";id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uid);memory_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),index=True);subject_type:Mapped[str]=mapped_column(String(32));subject_id:Mapped[str]=mapped_column(String(256));permission:Mapped[str]=mapped_column(String(32));condition:Mapped[dict]=mapped_column(JSONB,default=dict)
class ShareGrant(Base):
 __tablename__="share_grants";id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uid);tenant_id:Mapped[str]=mapped_column(String(128));from_agent:Mapped[str]=mapped_column(String(256));to_agent:Mapped[str]=mapped_column(String(256));scope_filter:Mapped[dict]=mapped_column(JSONB);layers:Mapped[list]=mapped_column(JSONB);revoked:Mapped[bool]=mapped_column(Boolean,default=False)
class Audit(Base):
 __tablename__="audit";id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uid);tenant_id:Mapped[str]=mapped_column(String(128),index=True);actor:Mapped[str]=mapped_column(String(256));action:Mapped[str]=mapped_column(String(128));memory_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),nullable=True);data:Mapped[dict]=mapped_column(JSONB,default=dict);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class Outbox(Base):
 __tablename__="outbox";id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uid);event_type:Mapped[str]=mapped_column(String(128));aggregate_id:Mapped[str]=mapped_column(String(128));payload:Mapped[dict]=mapped_column(JSONB);published:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
