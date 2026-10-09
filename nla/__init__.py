"""Load settings from a .env file in the project root (if present) before anything reads env vars.
Real environment variables still win over .env values."""
import pathlib
try:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:  # python-dotenv not installed: fall back to plain environment variables
    pass
