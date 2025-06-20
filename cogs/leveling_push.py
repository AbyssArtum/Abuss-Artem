import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import asyncio
import json
from pathlib import Path
from typing import Optional
from .leveling import LeaderboardPaginator

class LevelingPush(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schedule = {}
        self.load_config()
        self.daily_post.start()

    def load_config(self):
        """Загружает конфигурацию из JSON файла"""
        config_path = Path("data/leveling_config.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self.schedule = json.load(f)

    def save_config(self):
        """Сохраняет конфигурацию в JSON файл"""
        config_path = Path("data/leveling_config.json")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.schedule, f, ensure_ascii=False, indent=4)

    def update_guild_config(self, guild_id, channel_id=None, post_time=None):
        """Обновляет конфигурацию для гильдии"""
        if guild_id not in self.schedule:
            self.schedule[guild_id] = {}
        if channel_id is not None:
            self.schedule[guild_id]['channel_id'] = channel_id
        if post_time is not None:
            self.schedule[guild_id]['post_time'] = post_time
        self.save_config()

    @tasks.loop(minutes=1)
    async def daily_post(self):
        """Ежедневная публикация таблицы лидеров"""
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")
        
        for guild_id, config in self.schedule.items():
            if config.get('post_time') == current_time and config.get('channel_id'):
                try:
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue
                        
                    channel = guild.get_channel(int(config['channel_id']))
                    if not channel:
                        continue
                        
                    embed = await LeaderboardPaginator.create_leaderboard_embed(
                        self.bot, guild.id, 1
                    )
                    await channel.send(
                        f"**Ежедневный топ сервера ({now.strftime('%d.%m.%Y')})**",
                        embed=embed
                    )
                    
                except Exception as e:
                    print(f"Ошибка при публикации таблицы лидеров: {e}")

    @daily_post.before_loop
    async def before_daily_post(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="таблица", description="Настройка автоматической публикации таблицы лидеров")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        канал="Канал для публикации таблицы",
        время="Время публикации в формате ЧЧ:ММ (например 21:00)"
    )
    async def setup_leaderboard(self, interaction: discord.Interaction,
                              канал: discord.TextChannel, время: str):
        """Настройка автоматической публикации таблицы лидеров"""
        try:
            datetime.datetime.strptime(время, "%H:%M")
        except ValueError:
            return await interaction.response.send_message(
                "❌ Неверный формат времени! Используйте ЧЧ:ММ (например 21:00)",
                ephemeral=True
            )
        
        self.update_guild_config(str(interaction.guild_id), канал.id, время)
        await interaction.response.send_message(
            f"✅ Таблица лидеров будет публиковаться ежедневно в {время} в канале {канал.mention}",
            ephemeral=True
        )

    def cog_unload(self):
        self.daily_post.cancel()

async def setup(bot):
    await bot.add_cog(LevelingPush(bot))