from fastapi import FastAPI
from app.api import router
from app.db import Base,engine
app=FastAPI(title="Agent Memory + Context Fabric");app.include_router(router)
@app.on_event("startup")
async def startup():
 async with engine.begin() as c:await c.run_sync(Base.metadata.create_all)
@app.get("/health")
async def health():return {"status":"ok"}
