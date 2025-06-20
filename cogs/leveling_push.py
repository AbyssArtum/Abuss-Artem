import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import datetime
import asyncio
from typing import Optional
from .leveling import LeaderboardPaginator  # Добавляем этот импорт

class LevelingPush(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schedule = {}
        self.load_config()
        self.daily_post.start()

    def load_config(self):
        """Загружает конфигурацию из базы данных"""
        conn = sqlite3.connect('data/levels.db')
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS leaderboard_config (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            post_time TEXT
        )''')
        
        cursor.execute('SELECT guild_id, channel_id, post_time FROM leaderboard_config')
        for guild_id, channel_id, post_time in cursor.fetchall():
            self.schedule[guild_id] = {
                'channel_id': channel_id,
                'post_time': post_time
            }
        
        conn.close()

    def save_config(self, guild_id, channel_id=None, post_time=None):
        """Сохраняет конфигурацию в базу данных"""
        conn = sqlite3.connect('data/levels.db')
        cursor = conn.cursor()
        
        if guild_id in self.schedule:
            # Обновляем существующую запись
            current = self.schedule[guild_id]
            channel_id = channel_id if channel_id is not None else current['channel_id']
            post_time = post_time if post_time is not None else current['post_time']
            
            cursor.execute('''
                UPDATE leaderboard_config 
                SET channel_id=?, post_time=?
                WHERE guild_id=?
            ''', (channel_id, post_time, guild_id))
        else:
            # Создаем новую запись
            if channel_id is None or post_time is None:
                return
            cursor.execute('''
                INSERT INTO leaderboard_config (guild_id, channel_id, post_time)
                VALUES (?, ?, ?)
            ''', (guild_id, channel_id, post_time))
        
        conn.commit()
        conn.close()
        
        # Обновляем кеш
        if guild_id not in self.schedule:
            self.schedule[guild_id] = {}
        if channel_id is not None:
            self.schedule[guild_id]['channel_id'] = channel_id
        if post_time is not None:
            self.schedule[guild_id]['post_time'] = post_time

    @tasks.loop(minutes=1)
    async def daily_post(self):
        """Ежедневная публикация таблицы лидеров"""
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")
        
        for guild_id, config in self.schedule.items():
            if config.get('post_time') == current_time and config.get('channel_id'):
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                        
                    channel = guild.get_channel(config['channel_id'])
                    if not channel:
                        continue
                        
                    # Получаем ког системы уровней
                    leveling_cog = self.bot.get_cog("LevelingSystem")
                    if not leveling_cog:
                        continue
                    
                    # Создаем и отправляем таблицу лидеров
                    embed = await LeaderboardPaginator.create_leaderboard_embed(
                        self.bot, guild_id, 1
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
    async def setup_leaderboard(
        self,
        interaction: discord.Interaction,
        канал: discord.TextChannel,
        время: str
    ):
        """Настройка автоматической публикации таблицы лидеров"""
        try:
            # Проверяем формат времени
            datetime.datetime.strptime(время, "%H:%M")
        except ValueError:
            return await interaction.response.send_message(
                "❌ Неверный формат времени! Используйте ЧЧ:ММ (например 21:00)",
                ephemeral=True
            )
        
        # Сохраняем настройки
        self.save_config(interaction.guild_id, канал.id, время)
        
        await interaction.response.send_message(
            f"✅ Таблица лидеров будет публиковаться ежедневно в {время} в канале {канал.mention}",
            ephemeral=True
        )

    def cog_unload(self):
        self.daily_post.cancel()

async def setup(bot):
    await bot.add_cog(LevelingPush(bot))