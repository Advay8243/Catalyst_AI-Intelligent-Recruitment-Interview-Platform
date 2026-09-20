import uuid

from backend.services.calling.call_provider import CallProvider, CallStatus, ProviderCall


class MockCallProvider(CallProvider):
    """Deterministic local provider; no external call is placed."""

    def __init__(self) -> None:
        self._statuses: dict[str, CallStatus] = {}

    def start_call(self, phone: str) -> ProviderCall:
        if not phone.strip():
            raise ValueError("Candidate does not have a phone number")
        provider_call_id = f"mock-{uuid.uuid4()}"
        self._statuses[provider_call_id] = "connected"
        return ProviderCall(provider_call_id=provider_call_id, status="connected")

    def end_call(self, provider_call_id: str) -> ProviderCall:
        self._statuses[provider_call_id] = "completed"
        return ProviderCall(provider_call_id=provider_call_id, status="completed")

    def get_call_status(self, provider_call_id: str) -> ProviderCall:
        status = self._statuses.get(provider_call_id, "completed")
        return ProviderCall(provider_call_id=provider_call_id, status=status)
