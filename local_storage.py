"""Stores chat elements (Plotly charts) on local disk so they survive reopening a chat.
Chainlit's SQLAlchemy data layer only persists elements when given a storage client."""
import base64
from pathlib import Path
from typing import Any, Dict, Union

from chainlit.data.storage_clients.base import BaseStorageClient


class LocalStorageClient(BaseStorageClient):
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, object_key: str) -> Path:
        p = (self.root / object_key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("Invalid object key")
        return p

    async def upload_file(
        self, object_key: str, data: Union[bytes, str], mime: str = "application/octet-stream",
        overwrite: bool = True, content_disposition: str | None = None,
    ) -> Dict[str, Any]:
        p = self._path(object_key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data.encode() if isinstance(data, str) else data)
        (p.parent / (p.name + ".mime")).write_text(mime)
        return {"object_key": object_key, "url": await self.get_read_url(object_key)}

    async def get_read_url(self, object_key: str) -> str:
        # Charts are small JSON, so a data: URL avoids needing a file-serving route.
        p = self._path(object_key)
        mime_file = p.parent / (p.name + ".mime")
        mime = mime_file.read_text() if mime_file.exists() else "application/octet-stream"
        return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"

    async def delete_file(self, object_key: str) -> bool:
        p = self._path(object_key)
        for f in (p, p.parent / (p.name + ".mime")):
            f.unlink(missing_ok=True)
        return True

    async def close(self) -> None:
        pass
