from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./movieai.db"
    api_token: str = "change-me"
    frontend_origin: str = "http://localhost:3000"
    comfyui_url: str = "http://localhost:8188"
    use_mock_ai: bool = False
    default_llm_provider: str = "openai"
    tick_ms: int = 2000
    max_generation_retries: int = 3
    approval_min_brief_match: int = 7
    approval_min_style: int = 7

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openai_model: str = "gpt-4.1"
    anthropic_model: str = "claude-3-7-sonnet-latest"
    google_model: str = "gemini-2.5-pro"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
