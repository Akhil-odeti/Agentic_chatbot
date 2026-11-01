"""Sign-in by OpenAI key: the key proves who you are, so chat history follows the key.

- identity_for:  the same key always gives the same user id (a one-way SHA-256 hash), so reopening
                 the app with that key shows that key's chats. The key itself cannot be recovered
                 from the id.
- remember/recall: the key is held in server memory only (never in the database, cookies or logs)
                 so the agent can use it while the user stays signed in. It is gone after a
                 server restart; the user then signs in again with the same key and sees the same
                 history.

No Chainlit imports here, so this can be tested on its own.
"""
import hashlib
import time

import config

_KEYS: dict[str, tuple[str, float]] = {}  # user id -> (key, expires at)


def looks_like_key(key: str) -> bool:
    return key.startswith("sk-") and len(key) >= 20 and not any(c.isspace() for c in key)


def identity_for(key: str) -> str:
    return "key-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def remember(user_id: str, key: str) -> None:
    now = time.time()
    for uid in [u for u, (_, exp) in _KEYS.items() if exp < now]:  # drop expired entries
        _KEYS.pop(uid, None)
    _KEYS[user_id] = (key, now + config.SESSION_SECONDS)


def recall(user_id: str | None) -> str:
    entry = _KEYS.get(user_id or "")
    if not entry or entry[1] < time.time():
        return ""
    return entry[0]
