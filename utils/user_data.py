import json
import os
from pathlib import Path

DATA_PATH = Path("data/users")

def get_user_data(user_id: int):
    """Загружает данные пользователя или создаёт новый файл."""
    file = DATA_PATH / f"{user_id}.json"
    if not file.exists():
        return {
            "user_id": user_id,
            "surveys": {
                "current": None,
                "history": []
            },
            "leveling": {"text_xp": 0, "voice_xp": 0, "total_xp": 0, "level": 1},
            "moderation": {"warns": [], "reports": []}
        }
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_user_data(user_id: int, data: dict):
    """Сохраняет данные пользователя."""
    DATA_PATH.mkdir(exist_ok=True)
    file = DATA_PATH / f"{user_id}.json"
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)