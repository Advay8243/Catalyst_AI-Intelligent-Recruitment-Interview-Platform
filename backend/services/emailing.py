import uuid

from backend.services.providers import EmailProvider


class MockEmailProvider(EmailProvider):
    """Local provider that records a provider id without external delivery."""

    def send_email(self, recipient: str, subject: str, body: str) -> str:
        if not recipient or not subject.strip() or not body.strip():
            raise ValueError("Recipient, subject, and body are required")
        return f"mock-email-{uuid.uuid4()}"
