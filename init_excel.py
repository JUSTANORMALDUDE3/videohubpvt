"""
Run once to create users.xlsx (with default admin) and videos.xlsx if they don't exist.
Default admin: username=admin, password=@admin, rank=top
"""
from pathlib import Path
import pandas as pd
from werkzeug.security import generate_password_hash

BASE = Path(__file__).resolve().parent
USERS_FILE = BASE / "users.xlsx"
VIDEOS_FILE = BASE / "videos.xlsx"

if not USERS_FILE.exists():
    df = pd.DataFrame([
        {"username": "admin", "password": generate_password_hash("@admin"), "rank": "top"}
    ])
    df.to_excel(USERS_FILE, index=False)
    print("Created users.xlsx with default admin (admin / @admin)")

if not VIDEOS_FILE.exists():
    df = pd.DataFrame(columns=["id", "title", "filename", "rank", "description", "thumbnail"])
    df.to_excel(VIDEOS_FILE, index=False)
    print("Created videos.xlsx")

print("Done. Run: python app.py")
