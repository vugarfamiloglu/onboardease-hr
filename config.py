"""Application configuration, driven by environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'onboardease.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB per document
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "txt"}

    # Document storage backend: "local" (encrypted filesystem) or "s3" (AWS S3 + KMS)
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
    S3_BUCKET = os.environ.get("S3_BUCKET")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    KMS_KEY_ID = os.environ.get("KMS_KEY_ID")  # AWS KMS CMK used to wrap data keys
    # Local envelope-encryption master key (base64, 32 bytes). Auto-generated if unset.
    MASTER_KEY = os.environ.get("MASTER_KEY")

    # Reminders / mail. "file" writes emails to data/outbox, "console" prints, "smtp" sends.
    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "file")
    MAIL_FROM = os.environ.get("MAIL_FROM", "hr@onboardease.test")
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

    # Default seeded HR admin
    SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "hr@onboardease.test")
    SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "onboard123")

    APP_NAME = "OnboardEase HR"
