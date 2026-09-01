"""Environment-only configuration for the standalone R20 backend."""
from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    root: Path = ROOT
    host: str = "0.0.0.0"
    port: int = 8080
    okx_base_url: str = "https://www.okx.com"
    okx_api_key: str = ""
    okx_secret_key: str = ""
    okx_passphrase: str = ""
    okx_simulated: bool = False
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gemini-3.7-flash-high"
    notification_webhook: str = ""
    setup_token: str = ""
    admin_token: str = ""
    manual_close_enabled: bool = False


def refresh_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    settings.host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    settings.port = int(os.getenv("DASHBOARD_PORT", "8080"))
    settings.okx_base_url = os.getenv("OKX_BASE_URL", "https://www.okx.com")
    settings.okx_api_key = os.getenv("OKX_API_KEY", "")
    settings.okx_secret_key = os.getenv("OKX_SECRET_KEY", "")
    settings.okx_passphrase = os.getenv("OKX_PASSPHRASE", "")
    settings.okx_simulated = os.getenv("OKX_IS_SIMULATED", "0") == "1"
    settings.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    settings.llm_api_key = os.getenv("LLM_API_KEY", "")
    settings.llm_model = os.getenv("LLM_MODEL", "gemini-3.7-flash-high")
    settings.notification_webhook = os.getenv("R20_NOTIFICATION_WEBHOOK", "")
    settings.setup_token = os.getenv("R20_SETUP_TOKEN", "")
    settings.admin_token = os.getenv("R20_ADMIN_TOKEN", "")
    settings.manual_close_enabled = os.getenv("R20_MANUAL_CLOSE_ENABLED", "0") == "1"
    return settings


settings = Settings()
refresh_settings()
