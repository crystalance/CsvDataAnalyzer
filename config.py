"""Configuration management for CSV Data Analyzer."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # API Keys
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

    # Model configurations
    QWEN_MODEL: str = "qwen-plus"
    OPENAI_MODEL: str = "gpt-4o"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # DeepSeek API base URL
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # Execution settings
    MAX_RETRIES: int = 3

    # Output directory for figures
    OUTPUT_DIR: Path = Path("outputs")

    @classmethod
    def ensure_output_dir(cls) -> Path:
        """Ensure output directory exists and return its path."""
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        return cls.OUTPUT_DIR

    @classmethod
    def get_api_key(cls, model: str) -> str:
        """Get API key for the specified model."""
        keys = {
            "qwen": cls.DASHSCOPE_API_KEY,
            "openai": cls.OPENAI_API_KEY,
            "deepseek": cls.DEEPSEEK_API_KEY,
        }
        return keys.get(model, "")
