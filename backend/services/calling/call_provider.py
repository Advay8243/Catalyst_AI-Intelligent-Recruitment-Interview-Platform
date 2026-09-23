from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


CallStatus = Literal["not_started", "connecting", "connected", "completed", "failed"]


@dataclass(frozen=True)
class ProviderCall:
    provider_call_id: str
    status: CallStatus


class CallProvider(ABC):
    """Boundary for telephony providers.

    Providers control call connectivity only. Transcripts and screening analysis
    are persisted by the application service so changing providers does not
    change the recruitment workflow.
    """

    @property
    def supports_realtime_transcription(self) -> bool:
        """True when the provider streams live STT events into the app."""
        return False

    @abstractmethod
    def start_call(self, phone: str) -> ProviderCall:
        raise NotImplementedError

    @abstractmethod
    def end_call(self, provider_call_id: str) -> ProviderCall:
        raise NotImplementedError

    @abstractmethod
    def get_call_status(self, provider_call_id: str) -> ProviderCall:
        raise NotImplementedError
