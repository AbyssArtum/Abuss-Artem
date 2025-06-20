import json
import os
import discord

SURVEY_DATA_DIR = "data/surveys"

if not os.path.exists(SURVEY_DATA_DIR):
    os.makedirs(SURVEY_DATA_DIR)

def load_survey(user_id):
    file_path = f"{SURVEY_DATA_DIR}/{user_id}.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def get_survey_embed(user_id):
    data = load_survey(user_id)
    if data is None:
        return None

    embed = discord.Embed(title=f"Анкета участника", color=discord.Color.blurple())
    embed.add_field(name="Имя", value=data.get("name", "Не указано"), inline=False)
    embed.add_field(name="Возраст", value=data.get("age", "Не указано"), inline=False)
    embed.add_field(name="Творчество", value=data.get("creativity", "Не указано"), inline=False)
    embed.add_field(name="О себе", value=data.get("about", "Не указано"), inline=False)
    embed.add_field(name="Соцсети", value=data.get("socials", "Не указано"), inline=False)
    return embed
