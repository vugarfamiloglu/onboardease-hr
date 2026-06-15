"""Tiny mail abstraction. Default 'file' backend writes to data/outbox so the
reminder feature works with no SMTP configured; switch MAIL_BACKEND to 'smtp'
(or 'console') to deliver for real."""
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from flask import current_app


def send_mail(to, subject, body):
    cfg = current_app.config
    backend = cfg.get("MAIL_BACKEND", "file")
    sender = cfg.get("MAIL_FROM")

    if backend == "console":
        print(f"\n--- MAIL to {to} ---\nSubject: {subject}\n\n{body}\n--- end ---\n")
        return

    if backend == "smtp" and cfg.get("SMTP_HOST"):
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = sender, to, subject
        msg.set_content(body)
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"]) as s:
            s.starttls()
            if cfg.get("SMTP_USER"):
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            s.send_message(msg)
        return

    # default: write to data/outbox
    outbox = Path(cfg["SQLALCHEMY_DATABASE_URI"].split("///")[-1]).parent / "outbox"
    outbox.mkdir(exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
    safe = to.replace("@", "_at_")
    (outbox / f"{stamp}_{safe}.txt").write_text(
        f"From: {sender}\nTo: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8"
    )
