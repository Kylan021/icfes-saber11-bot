import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-icfes")

ANTI_CAPTCHA_KEY = os.getenv("ANTI_CAPTCHA_KEY", "d057f1ebb8c4334baf6441dffb519a10")

ICFES_LOGIN_URL = "https://resultadossaber11.icfes.gov.co/login"

HEADLESS = False

DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = BASE_DIR / "exports"
SCREENSHOT_DIR = BASE_DIR / "screenshots"

for d in (DATA_DIR, EXPORT_DIR, SCREENSHOT_DIR):
    d.mkdir(parents=True, exist_ok=True)


class Config:
    SECRET_KEY = SECRET_KEY
    ANTI_CAPTCHA_KEY = ANTI_CAPTCHA_KEY
    ICFES_LOGIN_URL = ICFES_LOGIN_URL
    HEADLESS = HEADLESS

    BASE_DIR = BASE_DIR
    DATA_DIR = DATA_DIR
    EXPORT_DIR = EXPORT_DIR
    SCREENSHOT_DIR = SCREENSHOT_DIR