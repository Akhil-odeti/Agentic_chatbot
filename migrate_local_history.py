"""One-off: give the chats saved under the old shared "local" user to the user of one OpenAI key.

Before key sign-in, every chat belonged to a single user called "local". Those chats are not shown
to key users, so run this once to hand them to the key that should own them:

    1. Stop the app (SQLite must not be in use).
    2. python migrate_local_history.py
    3. Paste the OpenAI key when asked (the key is not shown or saved).

Safe to run again: it only moves chats that still belong to "local".
"""
import datetime
import getpass
import sqlite3
import uuid

import config
import key_auth


def migrate(db_path: str, key: str) -> int:
    """Move every chat of the old "local" user to the user for `key`. Returns how many moved."""
    new_identifier = key_auth.identity_for(key)
    with sqlite3.connect(db_path) as con:
        old = con.execute("SELECT id FROM users WHERE identifier = 'local'").fetchone()
        if not old:
            return 0
        row = con.execute("SELECT id FROM users WHERE identifier = ?", (new_identifier,)).fetchone()
        if row:
            new_id = row[0]
        else:
            new_id = str(uuid.uuid4())
            con.execute(
                'INSERT INTO users ("id", "identifier", "metadata", "createdAt") VALUES (?, ?, ?, ?)',
                (new_id, new_identifier, '{"role": "user"}',
                 datetime.datetime.now(datetime.timezone.utc).isoformat()),
            )
        cur = con.execute(
            'UPDATE threads SET "userId" = ?, "userIdentifier" = ? WHERE "userId" = ?',
            (new_id, new_identifier, old[0]),
        )
        return cur.rowcount


if __name__ == "__main__":
    key = getpass.getpass("OpenAI API key that should own the old chats: ").strip()
    if not key_auth.looks_like_key(key):
        raise SystemExit("That does not look like an OpenAI API key (it should start with sk-).")
    print(f"Moved {migrate(config.CHAT_DB, key)} chat(s) to that key's history.")
