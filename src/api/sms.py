from fastapi import APIRouter, Form, Response

from src.services.imessage_service import process_command

router = APIRouter(tags=["sms"])


def _twiml_response(message: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{message}</Message></Response>'
    return Response(content=xml, media_type="application/xml")


@router.post("/sms/webhook")
async def sms_webhook(
    Body: str = Form(""),
    From: str = Form(""),
):
    reply = process_command(Body.strip())
    return _twiml_response(reply)
