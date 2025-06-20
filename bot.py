import discord
from discord.ext import commands
import asyncio
from cogs.survey_modal import SurveyModerationView
from templates.survey_template import SurveyButton
from utils.db import init_db

# Чтение токена из файла
with open('token.txt', 'r') as file:
    TOKEN = file.read().strip()  # .strip() удалит возможные пробелы и переносы строк

intents = discord.Intents.all()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

initial_extensions = [
    "options.general",
    "options.welcome",
    "cogs.survey_com",
    "cogs.template",
    "cogs.leveling",
    "cogs.leveling_com", 
    "cogs.leveling_push",
]

@bot.event
async def on_ready():
    bot.add_view(SurveyButton())
    bot.add_view(SurveyModerationView(user_id=0))
    
    print(f"✅ Бот {bot.user} запущен и готов к работе!")
    print(f"✅ Подключен к {len(bot.guilds)} серверам")
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Синхронизировано {len(synced)} слэш-команд.")
    except Exception as e:
        print(f"Ошибка синхронизации слэш-команд: {e}")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="ваши уровни активности"
        )
    )

async def main():
    init_db()
    
    async with bot:
        for ext in initial_extensions:
            try:
                await bot.load_extension(ext)
                print(f"Успешно загружен: {ext}")
            except Exception as e:
                print(f"Ошибка загрузки {ext}: {e}")
        
        await bot.start(TOKEN)  # Используем токен из переменной

if __name__ == "__main__":
    asyncio.run(main())