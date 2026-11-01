# """Helpers for the OpenAI key each user enters in the UI.

# - list_chat_models: asks OpenAI which chat models THIS key can use (this also checks the key).
# - friendly_error:   turns OpenAI errors into a plain message for the chat.
# - scrub_secrets:    makes sure a key never appears in text we show.

# No Chainlit imports here, so everything can be tested on its own.
# """
# import re
# from dataclasses import dataclass

# import openai
# from openai import AsyncOpenAI

# import config


# class KeyRejected(Exception):
#     """OpenAI said the API key is invalid."""


# @dataclass
# class ModelList:
#     models: list[str]
#     # "ok"          the key works and the list comes from OpenAI
#     # "restricted"  the key is valid but not allowed to list models (restricted key)
#     # "unreachable" OpenAI could not be reached, so the key is not verified yet
#     status: str


# # The /models endpoint also returns embeddings, audio, image, realtime and dated snapshot ids.
# # Only plain chat models that support tool calling are offered in the dropdown.
# _PREFIXES = ("gpt-", "o1", "o3", "o4")
# _SKIP = (
#     "embedding", "whisper", "tts", "audio", "realtime", "transcribe", "image", "dall-e",
#     "moderation", "instruct", "search", "codex", "computer-use", "davinci", "babbage", "sora",
#     "deep-research", "chatgpt", "-chat-latest", "-pro", "-preview", "-diarize",
# )
# _SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$|-\d{4}$")  # gpt-4.1-mini-2025-04-14, gpt-4-0613


# def _is_chat_model(model_id: str) -> bool:
#     if not model_id.startswith(_PREFIXES):
#         return False
#     if any(word in model_id for word in _SKIP):
#         return False
#     if _SNAPSHOT.search(model_id):
#         return False
#     # Older models too weak (or too small a context) for an agent that uses tools.
#     if model_id.startswith("gpt-3.5") or model_id == "gpt-4" or model_id.startswith("gpt-4-"):
#         return False
#     return True


# # Reasoning models (GPT-5 family, o-series) think by default, and OpenAI refuses function tools
# # together with reasoning on /v1/chat/completions ("use /v1/responses"). They are called through
# # the Responses API instead. GPT-4.x models stay on Chat Completions.
# _REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")


# def uses_responses_api(model_id: str) -> bool:
#     return model_id.startswith(_REASONING_PREFIXES)


# def filter_chat_models(ids) -> list[str]:
#     """Chat-capable model ids, default model first, the rest alphabetical."""
#     models = {i for i in ids if _is_chat_model(i)}
#     return sorted(models, key=lambda m: (m != config.DEFAULT_MODEL, m))


# def pick_model(models: list[str], wanted: str | None = None) -> str:
#     """The wanted model if this key can use it, else the default, else the first available."""
#     if wanted in models:
#         return wanted
#     if config.DEFAULT_MODEL in models:
#         return config.DEFAULT_MODEL
#     return models[0]


# async def list_chat_models(api_key: str) -> ModelList:
#     """Ask OpenAI which chat models this key can use. Raises KeyRejected for an invalid key."""
#     client = AsyncOpenAI(api_key=api_key, timeout=15.0, max_retries=1)
#     try:
#         page = await client.models.list()
#         models = filter_chat_models(m.id for m in page.data)
#         return ModelList(models or list(config.FALLBACK_MODELS), "ok")
#     except openai.AuthenticationError as e:
#         raise KeyRejected() from e
#     except openai.PermissionDeniedError:
#         return ModelList(list(config.FALLBACK_MODELS), "restricted")
#     except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError):
#         return ModelList(list(config.FALLBACK_MODELS), "unreachable")
#     finally:
#         await client.close()


# _KEYLIKE = re.compile(r"sk-[A-Za-z0-9_\-*]{6,}")


# def scrub_secrets(text: str, api_key: str = "") -> str:
#     """Remove the user's key (and anything shaped like an OpenAI key) from text."""
#     if api_key:
#         text = text.replace(api_key, "[hidden]")
#     return _KEYLIKE.sub("sk-[hidden]", text)


# def friendly_error(exc: Exception, api_key: str = "") -> str:
#     """A plain-language message for the chat. Never contains the key."""
#     if isinstance(exc, openai.AuthenticationError):
#         return (
#             "OpenAI rejected your API key. Open your profile menu, choose Logout and "
#             "sign in again with a valid key."
#         )
#     if isinstance(exc, (openai.NotFoundError, openai.PermissionDeniedError)):
#         return (
#             "Your OpenAI key cannot use this model. Choose another model in the settings "
#             "panel (the settings icon next to the message box) and ask again."
#         )
#     if isinstance(exc, openai.RateLimitError):
#         return (
#             "OpenAI reports a rate limit or no remaining credit on your key. Check your usage "
#             "and billing at platform.openai.com, then try again."
#         )
#     if isinstance(exc, openai.APIConnectionError):
#         return "Could not reach OpenAI. Check your internet connection and try again."
#     return f"Sorry, something went wrong: {type(exc).__name__}: {scrub_secrets(str(exc), api_key)}"
"""Helpers for the OpenAI key each user enters in the UI.

- list_chat_models: asks OpenAI which chat models THIS key can use (this also checks the key).
- friendly_error:   turns OpenAI errors into a plain message for the chat.
- scrub_secrets:    makes sure a key never appears in text we show.

No Chainlit imports here, so everything can be tested on its own.
"""
import re
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI

import config


class KeyRejected(Exception):
    """OpenAI said the API key is invalid."""


@dataclass
class ModelList:
    models: list[str]
    # "ok"          the key works and the list comes from OpenAI
    # "restricted"  the key is valid but not allowed to list models (restricted key)
    # "unreachable" OpenAI could not be reached, so the key is not verified yet
    status: str


# The /models endpoint also returns embeddings, audio, image, realtime and dated snapshot ids.
# Only plain chat models that support tool calling are offered in the dropdown.
_PREFIXES = ("gpt-",)
_O_SERIES = re.compile(r"^o\d")  # o1, o3, o4-mini and later
_SKIP = (
    "embedding", "whisper", "tts", "audio", "realtime", "transcribe", "image", "dall-e",
    "moderation", "instruct", "search", "codex", "computer-use", "davinci", "babbage", "sora",
    "deep-research", "chatgpt", "-chat-latest", "-pro", "-preview", "-diarize",
)
_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$|-\d{4}$")  # gpt-4.1-mini-2025-04-14, gpt-4-0613


def _is_chat_model(model_id: str) -> bool:
    if not (model_id.startswith(_PREFIXES) or _O_SERIES.match(model_id)):
        return False
    if any(word in model_id for word in _SKIP):
        return False
    if _SNAPSHOT.search(model_id):
        return False
    # Older models too weak (or too small a context) for an agent that uses tools.
    if model_id.startswith("gpt-3.5") or model_id == "gpt-4" or model_id.startswith("gpt-4-"):
        return False
    return True


# Newer models (GPT-5 and later, o-series) reason by default, and OpenAI refuses function tools
# together with reasoning on /v1/chat/completions ("use /v1/responses"). So only the older GPT-4.x
# and GPT-3.5 models use Chat Completions; every other model, including ones released later, is
# called through the Responses API. This avoids listing each new model name by hand.
_CHAT_COMPLETIONS_PREFIXES = ("gpt-4", "gpt-3")


def uses_responses_api(model_id: str) -> bool:
    return not model_id.startswith(_CHAT_COMPLETIONS_PREFIXES)


def filter_chat_models(ids) -> list[str]:
    """Chat-capable model ids, default model first, the rest alphabetical."""
    models = {i for i in ids if _is_chat_model(i)}
    return sorted(models, key=lambda m: (m != config.DEFAULT_MODEL, m))


def pick_model(models: list[str], wanted: str | None = None) -> str:
    """The wanted model if this key can use it, else the default, else the first available."""
    if wanted in models:
        return wanted
    if config.DEFAULT_MODEL in models:
        return config.DEFAULT_MODEL
    return models[0]


async def list_chat_models(api_key: str) -> ModelList:
    """Ask OpenAI which chat models this key can use. Raises KeyRejected for an invalid key."""
    client = AsyncOpenAI(api_key=api_key, timeout=15.0, max_retries=1)
    try:
        page = await client.models.list()
        models = filter_chat_models(m.id for m in page.data)
        return ModelList(models or list(config.FALLBACK_MODELS), "ok")
    except openai.AuthenticationError as e:
        raise KeyRejected() from e
    except openai.PermissionDeniedError:
        return ModelList(list(config.FALLBACK_MODELS), "restricted")
    except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError):
        return ModelList(list(config.FALLBACK_MODELS), "unreachable")
    finally:
        await client.close()


_KEYLIKE = re.compile(r"sk-[A-Za-z0-9_\-*]{6,}")


def scrub_secrets(text: str, api_key: str = "") -> str:
    """Remove the user's key (and anything shaped like an OpenAI key) from text."""
    if api_key:
        text = text.replace(api_key, "[hidden]")
    return _KEYLIKE.sub("sk-[hidden]", text)


def friendly_error(exc: Exception, api_key: str = "") -> str:
    """A plain-language message for the chat. Never contains the key."""
    if isinstance(exc, openai.AuthenticationError):
        return (
            "OpenAI rejected your API key. Open your profile menu, choose Logout and "
            "sign in again with a valid key."
        )
    if isinstance(exc, (openai.NotFoundError, openai.PermissionDeniedError)):
        return (
            "Your OpenAI key cannot use this model. Choose another model in the settings "
            "panel (the settings icon next to the message box) and ask again."
        )
    if isinstance(exc, openai.RateLimitError):
        return (
            "OpenAI reports a rate limit or no remaining credit on your key. Check your usage "
            "and billing at platform.openai.com, then try again."
        )
    if isinstance(exc, openai.APIConnectionError):
        return "Could not reach OpenAI. Check your internet connection and try again."
    return f"Sorry, something went wrong: {type(exc).__name__}: {scrub_secrets(str(exc), api_key)}"