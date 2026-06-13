from functools import lru_cache
import os

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

from agent.config import CHROMA_DIR, COLLECTION_NAME, ENV_FILE


@lru_cache(maxsize=1)
def get_embedding_function() -> OpenAIEmbeddingFunction:
    load_dotenv(ENV_FILE)
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    return OpenAIEmbeddingFunction(model_name=model)


@lru_cache(maxsize=1)
def get_chroma_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
    )
