from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"
AUDIT_CSV_PATH = DATA_DIR / "chroma" / "embedding_audit.csv"
ENV_FILE = PROJECT_ROOT / ".env"

COLLECTION_NAME = "tehran_hotels"
WELCOME_MESSAGE = (
    "سلام! من دستیار رزرو هتل تهران هستم. "
    "برای پیشنهاد بهترین هتل، چند سوال کوتاه ازت می‌پرسم "
    "(مثل منطقه، ستاره، امکانات و بودجه). "
    "هر وقت آماده بودی بگو چه نوع هتلی مدنظرته."
)

ZONE_OPTIONS = {"شمال", "جنوب", "شرق", "غرب", "مرکز"}

FIELD_SEARCH_MAP = {
    "hotel_name": "title_fa",
    "facilities_preferences": "facilitiesAggregate",
    "address": "address",
    "general_preferences": "description_fa",
}

TOP_K_PER_FIELD = 4
MAX_RECOMMENDATIONS = 5
