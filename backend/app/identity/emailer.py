from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings


@dataclass(frozen=True)
class OutboundEmail:
    recipient: str
    subject: str
    body: str


class EmailSender:
    async def send(self, message: OutboundEmail) -> str:
        raise NotImplementedError


class UnavailableEmailSender(EmailSender):
    async def send(self, message: OutboundEmail) -> str:
        raise RuntimeError("Email delivery is not configured.")


class CaptureEmailSender(EmailSender):
    """Test double. Rows are not exposed by the API. This is not a mailbox."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def send(self, message: OutboundEmail) -> str:
        await self._session.execute(
            text(
                "INSERT INTO mail_outbox (recipient, subject, body) "
                "VALUES (:recipient, :subject, :body)"
            ),
            {
                "recipient": message.recipient,
                "subject": message.subject,
                "body": message.body,
            },
        )
        return "captured"


class SmtpEmailSender(EmailSender):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: OutboundEmail) -> str:
        await asyncio.to_thread(self._send, message)
        return "sent"

    def _send(self, message: OutboundEmail) -> None:
        settings = self._settings
        email = EmailMessage()
        email["From"] = settings.smtp_from or settings.smtp_username
        email["To"] = message.recipient
        email["Subject"] = message.subject
        email.set_content(message.body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(email)


def build_email_sender(settings: Settings, session: AsyncSession) -> EmailSender:
    if settings.email_mode == "capture":
        return CaptureEmailSender(session)
    if settings.email_mode == "smtp":
        return SmtpEmailSender(settings)
    return UnavailableEmailSender()
