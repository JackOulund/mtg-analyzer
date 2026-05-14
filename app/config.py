from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    mock_external: bool = True
    apify_token: str = ""
    anthropic_api_key: str = ""
    claude_max_concurrency: int = 5  # max parallel Stage 2 Claude calls

    # API metadata
    app_title: str = "MTG Commander Analyzer"
    app_description: str = "Ingest YouTube Commander game videos and generate structured game analyses with Claude."
    app_version: str = "0.1.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Single instance used across the whole app
settings = Settings()
