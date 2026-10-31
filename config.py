"""Central settings. Secrets live in .env; everything else is changed here."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# The OpenAI key is NOT read from the server. Every user enters their own key in the UI
# (Chainlit "user_env"). Drop any key left in .env or the shell so it can never be used silently.
os.environ.pop("OPENAI_API_KEY", None)

# Models: the user picks one in the UI. The list comes from OpenAI (what THEIR key can use);
# FALLBACK_MODELS is shown only if OpenAI cannot be asked. The same model runs the chat agent
# and the chart-selector.
DEFAULT_MODEL = "gpt-4.1-mini"
FALLBACK_MODELS = ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"]

MAX_CHARTS = 3
MAX_RETRIES = 3
EXEC_TIMEOUT_SECONDS = 15
SUMMARIZE_AFTER_TOKENS = 4000

# Where chat history, agent memory and charts are stored. Defaults to the project folder;
# the Docker image sets DATA_DIR=/app/data so it can be mounted from the host.
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR))

CHECKPOINT_DB = str(DATA_DIR / "agent_memory.sqlite")
CHAT_DB = str(DATA_DIR / "chat_history.sqlite")
CHART_STORE_DIR = str(DATA_DIR / ".chart_store")

SCRAPERAPI_API_KEY = os.getenv("SCRAPERAPI_API_KEY", "")
SCRAPE_MAX_CHARS = 12000
SCRAPE_TIMEOUT_SECONDS = 70

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
SEARCH_MAX_RESULTS = 5
SEARCH_DEPTHS = {
    "basic": "Balanced speed and relevance",
    "fast": "Quicker, still good relevance",
    "ultra-fast": "Lowest latency, shallower results",
    "advanced": "Most thorough, slowest, uses more credits",
}
