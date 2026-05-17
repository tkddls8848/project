from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
CATALOG_DIR = DATA_DIR / "02_catalog"
SEMANTIC_DIR = DATA_DIR / "03_semantic"
SERVING_DIR = DATA_DIR / "04_serving"
CHROMA_DIR = DATA_DIR / "05_indexes" / "chroma"
MINIMAL_DIR = DATA_DIR / "minimal"

COLLECTION_NAME = "public_services"
DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
MODEL_LOCAL_FILES_ONLY = True
DEFAULT_TOP_K = 5
MAX_QUERY_LENGTH = 300
VECTOR_TOP_N_MIN = 20

# Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "nomic-embed-text"

# Minimal pipeline (FAISS)
FAISS_INDEX_PATH = MINIMAL_DIR / "faiss.index"
MINIMAL_META_PATH = MINIMAL_DIR / "meta.jsonl"
MINIMAL_DOCS_PATH = MINIMAL_DIR / "documents.jsonl"
