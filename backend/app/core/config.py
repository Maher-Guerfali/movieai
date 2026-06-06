from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./movieai.db"
    api_token: str = "change-me"
    frontend_origin: str = "http://localhost:3000"

    # --- Image backend ---
    comfyui_url: str = "http://localhost:8188"
    comfy_workflow: str = "txt2img-reference"
    comfy_timeout_s: int = 180

    # --- Orchestration ---
    tick_ms: int = 2000
    max_generation_retries: int = 3
    approval_min_brief_match: int = 7
    approval_min_style: int = 7

    # --- Providers (real APIs; required to run a phase) ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openai_model: str = "gpt-4.1"
    anthropic_model: str = "claude-3-7-sonnet-latest"
    google_model: str = "gemini-2.5-pro"

    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    google_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_timeout_s: int = 120
    llm_max_tokens: int = 4096

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
