from src.config import settings
from src.services.imessage_service import send_imessage


def send_sms(body: str, to: str | None = None) -> bool:
    """Send a message. Tries iMessage first; falls back to Twilio if iMessage fails."""
    if send_imessage(body, to):
        return True

    # Twilio fallback
    if not all([
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_phone_number,
    ]):
        return False

    to_number = to or settings.user_phone_number
    if not to_number:
        return False

    from twilio.rest import Client
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    client.messages.create(
        body=body,
        from_=settings.twilio_phone_number,
        to=to_number,
    )
    return True
