"""Configuration management using Pydantic settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LinkedIn OAuth
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:8000/oauth/linkedin/callback"
    linkedin_scopes: str = "w_member_social r_liteprofile"
    linkedin_person_urn: str = ""  # Optional override

    # RSS Feeds
    feeds: str = ""  # Comma-separated URLs
    poll_seconds: int = 1800

    # Database
    db_path: str = "./data/agent.db"

    # Application
    base_url: str = "http://localhost:8000"

    # Ollama AI Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ai_enabled: bool = True

    # Groq AI Configuration
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Unsplash API Configuration
    unsplash_access_key: str = ""  # Get from https://unsplash.com/developers

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_feed_list(self) -> list[str]:
        """Parse comma-separated feeds into a list."""
        if not self.feeds:
            return []
        return [url.strip() for url in self.feeds.split(",") if url.strip()]

    def get_scope_list(self) -> list[str]:
        """Parse scopes into a list."""
        return [s.strip() for s in self.linkedin_scopes.split() if s.strip()]


# Global settings instance
settings = Settings()
