from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.config import settings
class Base(DeclarativeBase):pass
engine=create_async_engine(settings.database_url,pool_pre_ping=True)
Session=async_sessionmaker(engine,expire_on_commit=False)
