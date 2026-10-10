from pydantic_settings import BaseSettings,SettingsConfigDict
class Settings(BaseSettings):
 database_url:str="postgresql+asyncpg://postgres:postgres@localhost:5432/memory";api_key:str="change-me";default_ttl_days:int=90
 model_config=SettingsConfigDict(env_file=".env",extra="ignore")
settings=Settings()
