import discord
from discord.ext import commands
import asyncio
from cogs.survey_modal import SurveyModerationView
from templates.survey_template import SurveyButton
from utils.db import init_db

with open('token.txt', 'r') as file:
    TOKEN = file.read().strip()

intents = discord.Intents.all()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def load_extensions():
    extensions = [
        "cogs.guild",
        "cogs.general",
        "cogs.welcome",
        "cogs.template",
        "cogs.survey_com",
        "cogs.leveling",
        "cogs.leveling_com", 
        "cogs.leveling_push",
        "cogs.moderation.moderation",
        "cogs.moderation.moderation_report",
        "cogs.moderation.moderation_warns",
        "cogs.moderation.moderation_mute",
        "cogs.moderation.moderation_del",
    ]
    
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"✅ Успешно загружен: {ext}")
        except Exception as e:
            print(f"❌ Ошибка загрузки {ext}: {e}")

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
            name="Вам прямо в душу"
        )
    )

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Синхронизировать слэш-команды"""
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ Синхронизировано {len(synced)} команд", ephemeral=True)
        print(f"Синхронизировано {len(synced)} команд")
    except Exception as e:
        await ctx.send(f"❌ Ошибка синхронизации: {e}", ephemeral=True)
        print(f"Ошибка синхронизации: {e}")

async def main():
    init_db()
    
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())