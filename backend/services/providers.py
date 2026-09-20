from abc import ABC, abstractmethod


class CallProvider(ABC):
    @abstractmethod
    def schedule_call(self, phone: str, context: dict) -> str:
        """Return the external call identifier."""
        raise NotImplementedError


class EmailProvider(ABC):
    @abstractmethod
    def send_email(self, recipient: str, subject: str, body: str) -> str:
        """Return the external message identifier."""
        raise NotImplementedError
