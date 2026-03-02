import email
import email.policy
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

router = APIRouter(tags=["upload"])

UPLOAD_DIR = "/home/user/organizer-api/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload/eml")
async def upload_eml(file: UploadFile = File(...)):
    if not file.filename.endswith(".eml"):
        raise HTTPException(status_code=400, detail="Only .eml files are supported")

    raw = await file.read()
    msg = email.message_from_bytes(raw, policy=email.policy.default)

    subject = msg.get("subject", "(no subject)")
    sender = msg.get("from", "(unknown)")
    date = msg.get("date", "(unknown)")

    attachments = []
    body_text = ""

    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = part.get_content_disposition()

        if disposition == "attachment":
            filename = part.get_filename() or f"attachment-{uuid.uuid4().hex[:8]}"
            safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
            save_path = os.path.join(UPLOAD_DIR, safe_name)
            payload = part.get_payload(decode=True)
            if payload:
                with open(save_path, "wb") as f:
                    f.write(payload)
                attachments.append({
                    "original_filename": filename,
                    "saved_as": safe_name,
                    "download_url": f"/api/v1/upload/files/{safe_name}",
                    "size_bytes": len(payload),
                })
        elif content_type == "text/plain" and disposition != "attachment" and not body_text:
            body_text = part.get_content()

    return {
        "success": True,
        "data": {
            "subject": subject,
            "from": sender,
            "date": date,
            "body_preview": body_text[:500] if body_text else None,
            "attachments": attachments,
        },
        "message": f"Parsed email with {len(attachments)} attachment(s)",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/upload/files/{filename}")
def download_file(filename: str):
    # Prevent path traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename.split("_", 1)[-1])
