from functools import lru_cache

import chromadb

from agent.config import CHROMA_DIR, COLLECTION_NAME
from agent.llm import build_embedding_function


@lru_cache(maxsize=1)
def get_embedding_function():
    return build_embedding_function()


@lru_cache(maxsize=1)
def get_chroma_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
    )
