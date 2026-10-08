"""OpenRouter clients for chat and embeddings.

OpenRouter exposes an OpenAI-compatible API, so LangChain and Chroma keep
using their OpenAI clients with a different base URL and key.
"""

from __future__ import annotations

import os
import warnings

from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from agent.config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_GENERATION_MODEL,
    ENV_FILE,
    OPENROUTER_BASE_URL,
)


def load_env() -> None:
    load_dotenv(ENV_FILE)


def openrouter_api_key() -> str:
    load_env()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Add it to .env in the project root."
        )
    return api_key


def openrouter_headers() -> dict[str, str]:
    load_env()
    return {
        "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:8501"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "Tehran Hotel Assistant"),
    }


def generation_model() -> str:
    load_env()
    return os.getenv("GENERATION_MODEL", DEFAULT_GENERATION_MODEL).strip()


def embedding_model() -> str:
    load_env()
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()


def canonical_embedding_model(name: str) -> str:
    """Compare `text-embedding-3-large` with `openai/text-embedding-3-large`."""
    return name.strip().split("/")[-1]


def build_chat_model(temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=generation_model(),
        temperature=temperature,
        api_key=openrouter_api_key(),
        base_url=OPENROUTER_BASE_URL,
        default_headers=openrouter_headers(),
    )


def build_embedding_function() -> OpenAIEmbeddingFunction:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Direct api_key configuration will not be persisted.",
            category=DeprecationWarning,
        )
        return OpenAIEmbeddingFunction(
            api_key=openrouter_api_key(),
            model_name=embedding_model(),
            api_base=OPENROUTER_BASE_URL,
            default_headers=openrouter_headers(),
            api_key_env_var="OPENROUTER_API_KEY",
        )
