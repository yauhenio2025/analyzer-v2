"""Model backend factory.

Resolves model IDs to the appropriate backend implementation.
"""

import logging
from typing import Union

from src.llm.backends import AnthropicBackend, GeminiBackend, OpenRouterBackend, ModelBackend

logger = logging.getLogger(__name__)


def get_backend(model_id: str) -> Union[AnthropicBackend, GeminiBackend, OpenRouterBackend]:
    """Get the appropriate backend for a model ID.

    Args:
        model_id: Full model identifier (e.g. 'claude-sonnet-4-6',
                  'gemini-3.1-pro-preview', 'openrouter/deepseek/deepseek-r1')

    Returns:
        Backend instance for the model

    Raises:
        ValueError: If model_id is not recognized
    """
    if model_id.startswith("claude-"):
        return AnthropicBackend(model_id=model_id)
    elif model_id.startswith("gemini-"):
        return GeminiBackend(model_id=model_id)
    elif model_id.startswith("openrouter/"):
        return OpenRouterBackend(model_id=model_id)
    else:
        raise ValueError(
            f"Unknown model: '{model_id}'. "
            f"Expected a model ID starting with 'claude-', 'gemini-', or 'openrouter/'."
        )
