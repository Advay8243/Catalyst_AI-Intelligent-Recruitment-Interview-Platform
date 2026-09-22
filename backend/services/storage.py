import uuid
from abc import ABC, abstractmethod
from pathlib import Path


class FileStorage(ABC):
    @abstractmethod
    def save(self, filename: str, content: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def read(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError


class LocalFileStorage(FileStorage):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        key = f"{uuid.uuid4()}{suffix}"
        (self.root / key).write_bytes(content)
        return key

    def read(self, key: str) -> bytes:
        safe_key = Path(key).name
        return (self.root / safe_key).read_bytes()

    def delete(self, key: str) -> None:
        path = self.root / Path(key).name
        if path.exists():
            path.unlink()
