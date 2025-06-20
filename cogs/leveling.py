import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import random
import json
from pathlib import Path
from typing import Optional

# Настройки системы уровней
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

def get_user_data(user_id):
    """Загружает данные пользователя из файла"""
    path = Path(f"data/users/{user_id}.json")
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"user_id": user_id}

def save_user_data(user_id, data):
    """Сохраняет данные пользователя в файл"""
    Path("data/users").mkdir(parents=True, exist_ok=True)
    with open(f"data/users/{user_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class LeaderboardPaginator(discord.ui.View):
    def __init__(self, bot, guild_id, total_pages):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.current_page = 1
        self.total_pages = total_pages
        self.message = None

    async def update_embed(self, interaction: discord.Interaction):
        embed = await self.create_leaderboard_embed(self.bot, self.guild_id, self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @staticmethod
    async def create_leaderboard_embed(bot, guild_id, page):
        # Собираем данные всех пользователей
        user_data = []
        guild = bot.get_guild(guild_id)
        
        # Сканируем все файлы пользователей
        user_files = Path("data/users").glob("*.json")
        for file in user_files:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "leveling" in data:
                    user_data.append({
                        'user_id': data['user_id'],
                        'xp': data['leveling'].get('total_xp', 0),
                        'level': data['leveling'].get('level', 1),
                        'voice_time': data['leveling'].get('voice_time', 0)
                    })
        
        # Сортируем по XP
        user_data.sort(key=lambda x: x['xp'], reverse=True)
        
        # Получаем топ для текущей страницы
        offset = (page - 1) * 10
        top_users = user_data[offset:offset+10]
        total_users = len(user_data)
        
        # Создаем список лидеров
        leaderboard = []
        for rank, user in enumerate(top_users, start=offset+1):
            member = guild.get_member(user['user_id']) if guild else None
            name = member.display_name if member else f"Неизвестный ({user['user_id']})"
            voice_time_str = LevelingSystem.format_voice_time(user['voice_time'])
            
            if rank == 1:
                entry = f"🏆 **#{rank}. {name}**\nУровень: {user['level']} | Опыт: {user['xp']} | 🔊 {voice_time_str}"
            elif rank in (2, 3):
                entry = f"🎖️ **#{rank}. {name}**\nУровень: {user['level']} | Опыт: {user['xp']} | 🔊 {voice_time_str}"
            else:
                entry = f"**#{rank}. {name}**\nУровень: {user['level']} | Опыт: {user['xp']}" + (f" | 🔊 {voice_time_str}" if user['voice_time'] > 0 else "")
            
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
        self.voice_task = self.bot.loop.create_task(self.voice_activity_task())

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

    def get_user_stats(self, user_id, guild_id):
        """Возвращает текущий опыт и уровень пользователя"""
        user_data = get_user_data(user_id)
        if "leveling" not in user_data:
            return 0, 1
        return user_data["leveling"]["total_xp"], user_data["leveling"]["level"]

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

    async def update_level(self, user_id, guild_id, xp_earned=0, is_voice=False, voice_minutes=0):
        user_data = get_user_data(user_id)
        
        if "leveling" not in user_data:
            user_data["leveling"] = {
                "text_xp": 0,
                "voice_xp": 0,
                "total_xp": 0,
                "level": 1,
                "voice_time": 0
            }
        
        # Обновляем опыт
        xp_earned = int(xp_earned * (LEVEL_SETTINGS['voice_multiplier'] if is_voice else 1))
        
        if is_voice:
            user_data["leveling"]["voice_xp"] += xp_earned
            user_data["leveling"]["voice_time"] += voice_minutes
        else:
            user_data["leveling"]["text_xp"] += xp_earned
        
        user_data["leveling"]["total_xp"] += xp_earned
        
        # Проверяем уровень
        old_level = user_data["leveling"]["level"]
        new_level = max(1, self.get_level_from_xp(user_data["leveling"]["total_xp"]))
        user_data["leveling"]["level"] = new_level
        
        save_user_data(user_id, user_data)
        
        if new_level > old_level:
            return new_level
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
        now = datetime.datetime.now().timestamp()

        if user_id in self.last_message:
            if now - self.last_message[user_id] < LEVEL_SETTINGS['xp_cooldown']:
                return

        self.last_message[user_id] = now
        xp = random.randint(LEVEL_SETTINGS['text_xp_min'], LEVEL_SETTINGS['text_xp_max'])
        new_level = await self.update_level(user_id, message.guild.id, xp)

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

    def get_user_rank(self, user_id, guild_id):
        # Этот метод теперь работает с JSON данными
        user_data_list = []
        
        for file in Path("data/users").glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "leveling" in data:
                    user_data_list.append({
                        'user_id': data['user_id'],
                        'xp': data['leveling'].get('total_xp', 0)
                    })
        
        user_data_list.sort(key=lambda x: x['xp'], reverse=True)
        
        for rank, user in enumerate(user_data_list, start=1):
            if user['user_id'] == user_id:
                return rank
        
        return None

    @app_commands.command(name="ранг", description="Показать ваш уровень и статистику")
    @app_commands.describe(участник="Участник, чей уровень хотите проверить")
    async def rank(self, interaction: discord.Interaction, участник: Optional[discord.Member] = None):
        target = участник or interaction.user
        user_data = get_user_data(target.id)
        
        if "leveling" not in user_data:
            await interaction.response.send_message(
                f"{target.display_name} ещё не имеет уровня.",
                ephemeral=True
            )
            return

        leveling_data = user_data["leveling"]
        xp = leveling_data.get("total_xp", 0)
        level = leveling_data.get("level", 1)
        text_xp = leveling_data.get("text_xp", 0)
        voice_xp = leveling_data.get("voice_xp", 0)
        voice_time = leveling_data.get("voice_time", 0)
        
        current_level_xp = self.get_level_xp(level-1)
        next_level_xp = self.get_level_xp(level)
        progress = min(100, int((xp - current_level_xp) / (next_level_xp - current_level_xp) * 100))
        rank = self.get_user_rank(target.id, interaction.guild_id)
        
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

    @app_commands.command(name="лидеры", description="Топ активных участников сервера")
    async def top(self, interaction: discord.Interaction):
        # Считаем общее количество пользователей с данными об уровне
        user_count = sum(1 for _ in Path("data/users").glob("*.json") if "leveling" in json.load(open(_, "r", encoding="utf-8")))
        total_pages = max(1, (user_count // 10) + 1)
        
        view = LeaderboardPaginator(self.bot, interaction.guild_id, total_pages)
        view.message = await interaction.response.send_message(
            embed=await LeaderboardPaginator.create_leaderboard_embed(self.bot, interaction.guild_id, 1),
            view=view
        )

async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))