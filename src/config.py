from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    google_api_key: str = Field(..., alias='GOOGLE_API_KEY')
    tmdb_api_key: str = Field(..., alias='TMDB_API_KEY')
    admin_key: str = Field(default="", alias='ADMIN_KEY')
    base_parsing_model: str = Field(default="gemini-2.5-flash", alias='BASE_PARSING_MODEL')
    analysis_model: str = Field(default="gemini-2.5-flash", alias='ANALYSIS_MODEL')

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
