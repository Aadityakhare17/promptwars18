"""Application configuration using Pydantic Settings.

All API keys are hardcoded as placeholders per project requirements.
Replace placeholder values with actual keys before deployment.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class AIModelConfig(BaseSettings):
    """Configuration for AI model providers with fallback chain."""

    gemini_api_key: str = Field(
        default="YOUR_GEMINI_API_KEY_HERE",
        description="Google Gemini API key",
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model identifier",
    )
    gemini_api_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models",
        description="Gemini API base URL",
    )

    claude_api_key: str = Field(
        default="YOUR_CLAUDE_API_KEY_HERE",
        description="Anthropic Claude API key",
    )
    claude_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model identifier",
    )
    claude_api_url: str = Field(
        default="https://api.anthropic.com/v1/messages",
        description="Claude API URL",
    )

    chatgpt_api_key: str = Field(
        default="YOUR_CHATGPT_API_KEY_HERE",
        description="OpenAI ChatGPT API key",
    )
    chatgpt_model: str = Field(
        default="gpt-4o",
        description="ChatGPT model identifier",
    )
    chatgpt_api_url: str = Field(
        default="https://api.openai.com/v1/chat/completions",
        description="ChatGPT API URL",
    )

    perplexity_api_key: str = Field(
        default="YOUR_PERPLEXITY_API_KEY_HERE",
        description="Perplexity API key",
    )
    perplexity_model: str = Field(
        default="sonar-pro",
        description="Perplexity model identifier",
    )
    perplexity_api_url: str = Field(
        default="https://api.perplexity.ai/chat/completions",
        description="Perplexity API URL",
    )

    deepseek_api_key: str = Field(
        default="YOUR_DEEPSEEK_API_KEY_HERE",
        description="DeepSeek API key",
    )
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek model identifier",
    )
    deepseek_api_url: str = Field(
        default="https://api.deepseek.com/v1/chat/completions",
        description="DeepSeek API URL",
    )

    request_timeout_seconds: int = Field(
        default=15,
        description="Timeout per AI provider request in seconds",
    )


class RateLimitConfig(BaseSettings):
    """Rate limiting configuration."""

    requests_per_minute: int = Field(
        default=30,
        description="Maximum requests per minute per IP",
    )
    chat_requests_per_minute: int = Field(
        default=10,
        description="Maximum chat requests per minute per IP",
    )


class GoogleServicesConfig(BaseSettings):
    """Configuration for integrated Google Services (Auth, Storage, Analytics)."""

    google_client_id: str = Field(
        default="YOUR_GOOGLE_CLIENT_ID_HERE",
        description="Google OAuth2 Client ID",
    )
    google_client_secret: str = Field(
        default="YOUR_GOOGLE_CLIENT_SECRET_HERE",
        description="Google OAuth2 Client Secret",
    )
    gcs_bucket_name: str = Field(
        default="your-carbon-footprint-bucket",
        description="Google Cloud Storage Bucket Name",
    )
    ga_measurement_id: str = Field(
        default="G-MOCKMEASUREID",
        description="Google Analytics 4 Measurement ID",
    )
    auth_simulator_enabled: bool = Field(
        default=True,
        description=(
            "Enable Google Auth & GCS mock/simulation mode for easy local testing"
        ),
    )


class AppConfig(BaseSettings):
    """Root application configuration."""

    app_name: str = "Carbon Footprint Awareness Platform"
    app_version: str = "1.0.0"
    debug: bool = False

    allowed_origins: list[str] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:8000"],
        description="CORS allowed origins",
    )

    max_request_body_bytes: int = Field(
        default=1_048_576,
        description="Maximum request body size (1 MB)",
    )

    max_chat_message_length: int = Field(
        default=2000,
        description="Maximum characters in a chat message",
    )

    max_history_entries: int = Field(
        default=100,
        description="Maximum carbon tracking entries per session",
    )

    ai: AIModelConfig = AIModelConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    google: GoogleServicesConfig = GoogleServicesConfig()


# Singleton instance
settings = AppConfig()
