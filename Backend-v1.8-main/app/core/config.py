import os

# Frontend Connection Logic (Origins)
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://app.netlify.com",
    "https://logicum.de",
    "https://www.logicum.de",
]

# JWT Token Expiry
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# API Tokens & Secrets
AUTH_SECRET = os.environ.get("AUTH_SECRET", "change-this-in-production")
# Cookie & Session Security
IS_PROD = os.environ.get("RAILWAY_ENVIRONMENT_NAME") is not None or os.environ.get("NODE_ENV") == "production"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "True" if IS_PROD else "False").lower() == "true"
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "none" if IS_PROD else "lax")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()

# OpenAI Configuration (GPT-5.2 / 5.1)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.2")
OPENAI_GPT51_MODEL = os.environ.get("OPENAI_GPT51_MODEL", "gpt-5.1")

# Google Gemini Configuration (Flash / Nano)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Storage & Data Center
STORAGE_DIR = "storage"
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")

# S3 / Data Center Configuration
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "https://s3.amazonaws.com")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "logicum-datacenter")
