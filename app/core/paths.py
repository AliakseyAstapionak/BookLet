import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR') or BASE_DIR / 'uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)