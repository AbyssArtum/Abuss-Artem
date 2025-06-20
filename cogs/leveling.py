import discord
from discord.ext import commands
from discord import app_commands
import os
import datetime
import asyncio
from typing import Optional
import random
import sqlite3

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect('data/main.db')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Добавляем опыт
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, guild_id) 
            VALUES (?, ?)
        """, (message.author.id, message.guild.id))

        cursor.execute("""
            UPDATE levels 
            SET xp = xp + ?, last_active = CURRENT_TIMESTAMP
            WHERE user_id = ? AND guild_id = ?
        """, (10, message.author.id, message.guild.id))
        self.db.commit()

LEVEL_SETTINGS = {
    'text_xp_min': 10,
    'text_xp_max': 25,
    'voice_xp_per_min': 20,
    'xp_cooldown': 60,
    'base_xp': 100,
    'xp_multiplier': 50,
    'voice_multiplier': 1.5,
    'save_interval': 300
}

class LeaderboardPaginator(discord.ui.View):
    def __init__(self, bot, guild_id, total_pages):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.current_page = 1
        self.total_pages = total_pages
    
    async def update_embed(self, interaction: discord.Interaction):
        embed = await self.create_leaderboard_embed(self.bot, self.guild_id, self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @staticmethod
    async def create_leaderboard_embed(bot, guild_id, page):
        conn = sqlite3.connect('data/levels.db')
        cursor = conn.cursor()
        
        # Получаем общее количество участников
        cursor.execute('SELECT COUNT(*) FROM levels WHERE guild_id=?', (guild_id,))
        total_users = cursor.fetchone()[0]
        
        # Получаем топ для текущей страницы
        offset = (page - 1) * 10
        cursor.execute('''
            SELECT user_id, xp, level, voice_time FROM levels 
            WHERE guild_id=? 
            ORDER BY xp DESC 
            LIMIT 10 OFFSET ?
        ''', (guild_id, offset))
        top_users = cursor.fetchall()
        conn.close()
        
        # Создаем список лидеров
        leaderboard = []
        for rank, (user_id, xp, level, voice_time) in enumerate(top_users, start=offset+1):
            guild = bot.get_guild(guild_id)
            member = guild.get_member(user_id) if guild else None
            name = member.display_name if member else f"Неизвестный ({user_id})"
            voice_time_str = LevelingSystem.format_voice_time(voice_time)
            
            if rank == 1:
                entry = f"🏆 **#{rank}. {name}**\nУровень: {level} | Опыт: {xp} | 🔊 {voice_time_str}"
            elif rank in (2, 3):
                entry = f"🎖️ **#{rank}. {name}**\nУровень: {level} | Опыт: {xp} | 🔊 {voice_time_str}"
            else:
                entry = f"**#{rank}. {name}**\nУровень: {level} | Опыт: {xp}" + (f" | 🔊 {voice_time_str}" if voice_time > 0 else "")
            
            leaderboard.append(entry)

        embed = discord.Embed(
            title=f"Топ рейтинга участников (Страница {page}/{max(1, (total_users // 10) + 1)})",
            description="\n\n".join(leaderboard) if leaderboard else "Нет данных",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Всего участников: {total_users}")
        return embed
    
    @discord.ui.button(label="◀", style=discord.ButtonStyle.gray, disabled=True)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(1, self.current_page - 1)
        self.next_page.disabled = self.current_page >= self.total_pages
        self.prev_page.disabled = self.current_page <= 1
        await self.update_embed(interaction)
    
    @discord.ui.button(label="▶", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.total_pages, self.current_page + 1)
        self.next_page.disabled = self.current_page >= self.total_pages
        self.prev_page.disabled = self.current_page <= 1
        await self.update_embed(interaction)
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class LevelingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_users = {}
        self.last_message = {}
        self.voice_xp_per_min = LEVEL_SETTINGS['voice_xp_per_min']
        self.setup_db()
        self.voice_task = self.bot.loop.create_task(self.voice_activity_task())

    def setup_db(self):
        os.makedirs('data', exist_ok=True)
        self.conn = sqlite3.connect('data/levels.db')
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                text_xp INTEGER DEFAULT 0,
                voice_xp INTEGER DEFAULT 0,
                voice_time INTEGER DEFAULT 0,
                last_update TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        self.conn.commit()

    def cog_unload(self):
        if self.voice_task:
            self.voice_task.cancel()

    def get_level_xp(self, level):
        if level <= 0:
            return 0
        return int((level ** 2) * LEVEL_SETTINGS['xp_multiplier'] + LEVEL_SETTINGS['base_xp'])

    def get_level_from_xp(self, xp):
        level = 1
        while xp >= self.get_level_xp(level):
            level += 1
        return level

    async def voice_activity_task(self):
        while True:
            await asyncio.sleep(LEVEL_SETTINGS['save_interval'])
            for user_id, (channel_id, join_time) in list(self.voice_users.items()):
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                
                minutes = (datetime.datetime.now() - join_time).total_seconds() / 60
                await self.update_level(
                    user_id, channel.guild.id, 
                    minutes * LEVEL_SETTINGS['voice_xp_per_min'],
                    is_voice=True,
                    voice_minutes=minutes
                )
                self.voice_users[user_id] = (channel_id, datetime.datetime.now())

    def get_user_stats(self, user_id, guild_id):
        """Получает текущий XP и уровень пользователя"""
        self.cursor.execute(
            'SELECT xp, level FROM levels WHERE user_id=? AND guild_id=?',
            (user_id, guild_id)
        )
        result = self.cursor.fetchone()
        return result if result else (0, 1)

    async def update_level(self, user_id, guild_id, xp_earned=0, is_voice=False, voice_minutes=0):
        xp_earned = int(xp_earned * (LEVEL_SETTINGS['voice_multiplier'] if is_voice else 1))
        
        self.cursor.execute(
            'SELECT xp, level FROM levels WHERE user_id=? AND guild_id=?',
            (user_id, guild_id)
        )
        result = self.cursor.fetchone()

        if not result:
            self.cursor.execute(
                '''INSERT INTO levels 
                (user_id, guild_id, xp, level, text_xp, voice_xp, voice_time, last_update) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (user_id, guild_id, max(0, xp_earned), 1, 
                 0 if is_voice else max(0, xp_earned),
                 max(0, xp_earned) if is_voice else 0,
                 max(0, voice_minutes), 
                 datetime.datetime.now().isoformat())
            )
            xp, level = max(0, xp_earned), 1
        else:
            xp, level = result
            xp = max(0, xp + xp_earned)  # Защита от отрицательного XP
            
            if is_voice:
                self.cursor.execute(
                    '''UPDATE levels SET 
                    xp=?, voice_xp=voice_xp+?, voice_time=voice_time+?,
                    last_update=? 
                    WHERE user_id=? AND guild_id=?''',
                    (xp, max(0, xp_earned), max(0, voice_minutes),
                     datetime.datetime.now().isoformat(), user_id, guild_id)
                )
            else:
                self.cursor.execute(
                    '''UPDATE levels SET 
                    xp=?, text_xp=text_xp+?, 
                    last_update=? 
                    WHERE user_id=? AND guild_id=?''',
                    (xp, max(0, xp_earned),
                     datetime.datetime.now().isoformat(), user_id, guild_id)
                )

        new_level = max(1, self.get_level_from_xp(xp))  # Минимальный уровень - 1
        leveled_up = new_level > level
        leveled_down = new_level < level

        if leveled_up or leveled_down:
            self.cursor.execute(
                'UPDATE levels SET level=? WHERE user_id=? AND guild_id=?',
                (new_level, user_id, guild_id)
            )
            self.conn.commit()
            return new_level
        
        self.conn.commit()
        return None
    
    def create_progress_bar(self, progress):
        filled = '⬜'
        empty = '⬛'
        bar_length = 20
        filled_length = min(bar_length, int(progress * bar_length / 100))
        return filled * filled_length + empty * (bar_length - filled_length)

    @staticmethod
    def format_voice_time(minutes):
        total_seconds = int(minutes * 60)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        now = datetime.datetime.now().timestamp()

        if user_id in self.last_message:
            if now - self.last_message[user_id] < LEVEL_SETTINGS['xp_cooldown']:
                return

        self.last_message[user_id] = now
        xp = random.randint(LEVEL_SETTINGS['text_xp_min'], LEVEL_SETTINGS['text_xp_max'])
        new_level = await self.update_level(user_id, guild_id, xp)

        if new_level:
            await message.channel.send(
                f"🎉 {message.author.mention} достиг {new_level} уровня!",
                delete_after=10
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or not member.guild:
            return

        user_id = member.id
        now = datetime.datetime.now()

        if before.channel is None and after.channel is not None:
            self.voice_users[user_id] = (after.channel.id, now)
        
        elif before.channel is not None and after.channel is None:
            if user_id in self.voice_users:
                channel_id, join_time = self.voice_users.pop(user_id)
                minutes = (now - join_time).total_seconds() / 60
                xp_earned = int(minutes * LEVEL_SETTINGS['voice_xp_per_min'])
                
                if xp_earned > 0:
                    new_level = await self.update_level(
                        user_id, member.guild.id, xp_earned,
                        is_voice=True, voice_minutes=minutes
                    )
                    if new_level:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            await channel.send(
                                f"🎉 {member.mention} достиг {new_level} уровня в голосовом канале!",
                                delete_after=10
                            )

    @app_commands.command(name="ранг", description="Показать ваш уровень и статистику")
    @app_commands.describe(участник="Участник, чей уровень хотите проверить")
    async def rank(self, interaction: discord.Interaction, участник: Optional[discord.Member] = None):
        target = участник or interaction.user
        self.cursor.execute(
            '''SELECT xp, level, text_xp, voice_xp, voice_time 
            FROM levels 
            WHERE user_id=? AND guild_id=?''',
            (target.id, interaction.guild_id)
        )
        result = self.cursor.fetchone()

        if not result:
            await interaction.response.send_message(
                f"{target.display_name} ещё не имеет уровня.",
                ephemeral=True
            )
            return

        xp, level, text_xp, voice_xp, voice_time = result
        current_level_xp = self.get_level_xp(level-1)
        next_level_xp = self.get_level_xp(level)
        progress = min(100, int((xp - current_level_xp) / (next_level_xp - current_level_xp) * 100))
        rank = self.get_rank(target.id, interaction.guild_id)
        
        embed = discord.Embed(
            title=f"Статистика {target.display_name}",
            color=discord.Color.gold()
        )
        embed.add_field(name="🔢 Ранг", value=f"#{rank}" if rank else "Н/Д", inline=True)
        embed.add_field(name="📊 Уровень", value=str(level), inline=True)
        embed.add_field(name="🎙️ Голосовая активность", value=self.format_voice_time(voice_time), inline=False)
        embed.add_field(
            name="📈 Прогресс", 
            value=f"{self.create_progress_bar(progress)} {progress}%\n"
                  f"{xp - current_level_xp}/{next_level_xp - current_level_xp} XP",
            inline=False
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)

    def get_rank(self, user_id, guild_id):
        self.cursor.execute('''
            SELECT user_id FROM levels 
            WHERE guild_id=? 
            ORDER BY xp DESC
        ''', (guild_id,))
        top_users = [row[0] for row in self.cursor.fetchall()]
        return top_users.index(user_id) + 1 if user_id in top_users else None

    @app_commands.command(name="лидеры", description="Топ активных участников сервера")
    async def top(self, interaction: discord.Interaction):
        self.cursor.execute('SELECT COUNT(*) FROM levels WHERE guild_id=?', (interaction.guild_id,))
        total_users = self.cursor.fetchone()[0]
        
        total_pages = max(1, (total_users // 10) + 1)
        view = LeaderboardPaginator(self.bot, interaction.guild_id, total_pages)
        view.message = await interaction.response.send_message(
            embed=await LeaderboardPaginator.create_leaderboard_embed(self.bot, interaction.guild_id, 1),
            view=view
        )

async def setup(bot):
    cog = LevelingSystem(bot)
    await bot.add_cog(cog)
    
    if not bot.tree.get_command("ранг"):
        bot.tree.add_command(cog.rank)
    if not bot.tree.get_command("лидеры"):
        bot.tree.add_command(cog.top)