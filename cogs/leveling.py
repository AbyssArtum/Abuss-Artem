import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import random
import json
from pathlib import Path
from typing import Optional

class LevelingSystem(commands.Cog):
    """Система уровней с текстовой и голосовой активностью"""
    
    LEVEL_SETTINGS = {
        'text_xp_min': 10,
        'text_xp_max': 25,
        'voice_xp_per_min': 20,
        'xp_cooldown': 60,
        'base_xp': 100,
        'xp_multiplier': 50,
        'voice_multiplier': 1.5,
        'save_interval': 300,
        'leaderboard_users_per_page': 10
    }

    def __init__(self, bot):
        self.bot = bot
        self.voice_users = {}
        self.last_message = {}
        self.voice_task = self.bot.loop.create_task(self.voice_activity_task())
        self.user_data_path = Path("data/users")
        self.user_data_path.mkdir(parents=True, exist_ok=True)

    def cog_unload(self):
        if self.voice_task:
            self.voice_task.cancel()

    def _get_user_data(self, user_id):
        """Загружает данные пользователя"""
        file_path = self.user_data_path / f"{user_id}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"user_id": user_id}
        return {"user_id": user_id}

    def _save_user_data(self, user_id, data):
        """Сохраняет данные пользователя"""
        file_path = self.user_data_path / f"{user_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_level_xp(self, level):
        """Рассчитывает необходимый опыт для уровня"""
        return int((level ** 2) * self.LEVEL_SETTINGS['xp_multiplier'] + self.LEVEL_SETTINGS['base_xp'])

    def get_level_from_xp(self, xp):
        """Определяет уровень на основе опыта"""
        level = 1
        while xp >= self.get_level_xp(level):
            level += 1
        return level

    async def voice_activity_task(self):
        """Фоновая задача для обработки голосовой активности"""
        while True:
            await asyncio.sleep(self.LEVEL_SETTINGS['save_interval'])
            for user_id, (channel_id, join_time) in list(self.voice_users.items()):
                if channel := self.bot.get_channel(channel_id):
                    minutes = (datetime.datetime.now() - join_time).total_seconds() / 60
                    await self._update_user_xp(
                        user_id=user_id,
                        guild_id=channel.guild.id,
                        xp_earned=minutes * self.LEVEL_SETTINGS['voice_xp_per_min'],
                        is_voice=True,
                        voice_minutes=minutes
                    )
                    self.voice_users[user_id] = (channel_id, datetime.datetime.now())

    async def _update_user_xp(self, user_id, guild_id, xp_earned=0, is_voice=False, voice_minutes=0):
        """Обновляет опыт пользователя"""
        user_data = self._get_user_data(user_id)
        
        if "leveling" not in user_data:
            user_data["leveling"] = self._get_default_leveling_data()
        
        xp_earned = int(xp_earned * (self.LEVEL_SETTINGS['voice_multiplier'] if is_voice else 1))
        
        if is_voice:
            user_data["leveling"]["voice_xp"] += xp_earned
            user_data["leveling"]["voice_time"] += voice_minutes
        else:
            user_data["leveling"]["text_xp"] += xp_earned
        
        user_data["leveling"]["total_xp"] += xp_earned
        
        old_level = user_data["leveling"]["level"]
        new_level = max(1, self.get_level_from_xp(user_data["leveling"]["total_xp"]))
        user_data["leveling"]["level"] = new_level
        
        self._save_user_data(user_id, user_data)
        
        if new_level > old_level:
            return new_level
        return None

    def _get_default_leveling_data(self):
        """Возвращает стандартные данные для нового пользователя"""
        return {
            "text_xp": 0,
            "voice_xp": 0,
            "total_xp": 0,
            "level": 1,
            "voice_time": 0
        }

    def _create_progress_bar(self, progress):
        """Создает строку прогресс-бара"""
        filled = '⬜'
        empty = '⬛'
        bar_length = 20
        filled_length = min(bar_length, int(progress * bar_length / 100))
        return filled * filled_length + empty * (bar_length - filled_length)

    @staticmethod
    def format_voice_time(minutes):
        """Форматирует время в голосовом канале"""
        total_seconds = int(minutes * 60)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}ч {minutes:02d}м"

    @commands.Cog.listener()
    async def on_message(self, message):
        """Обработчик сообщений для начисления опыта"""
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        now = datetime.datetime.now().timestamp()

        if user_id in self.last_message:
            if now - self.last_message[user_id] < self.LEVEL_SETTINGS['xp_cooldown']:
                return

        self.last_message[user_id] = now
        xp = random.randint(self.LEVEL_SETTINGS['text_xp_min'], self.LEVEL_SETTINGS['text_xp_max'])
        if new_level := await self._update_user_xp(user_id, message.guild.id, xp):
            await message.channel.send(
                f"🎉 {message.author.mention} достиг {new_level} уровня!",
                delete_after=10
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Обработчик голосовой активности"""
        if member.bot or not member.guild:
            return

        user_id = member.id
        now = datetime.datetime.now()

        if before.channel is None and after.channel is not None:
            self.voice_users[user_id] = (after.channel.id, now)
        elif before.channel is not None and after.channel is None and user_id in self.voice_users:
            channel_id, join_time = self.voice_users.pop(user_id)
            minutes = (now - join_time).total_seconds() / 60
            xp_earned = int(minutes * self.LEVEL_SETTINGS['voice_xp_per_min'])
            
            if xp_earned > 0 and (new_level := await self._update_user_xp(
                user_id, member.guild.id, xp_earned, True, minutes
            )):
                if channel := self.bot.get_channel(channel_id):
                    await channel.send(
                        f"🎉 {member.mention} достиг {new_level} уровня в голосовом канале!",
                        delete_after=10
                    )

    def _get_user_rank(self, user_id):
        """Определяет ранг пользователя"""
        all_users = []
        for file in self.user_data_path.glob("*.json"):
            if data := self._get_user_data(file.stem):
                if "leveling" in data:
                    all_users.append((data["user_id"], data["leveling"]["total_xp"]))
        
        all_users.sort(key=lambda x: x[1], reverse=True)
        return next((i+1 for i, (uid, _) in enumerate(all_users) if uid == user_id), None)

    @app_commands.command(name="ранг", description="Показать ваш уровень и статистику")
    @app_commands.describe(участник="Участник, чей уровень хотите проверить")
    async def rank(self, interaction: discord.Interaction, участник: Optional[discord.Member] = None):
        """Команда для отображения ранга пользователя"""
        target = участник or interaction.user
        user_data = self._get_user_data(target.id)
        
        if "leveling" not in user_data:
            return await interaction.response.send_message(
                f"{target.display_name} ещё не имеет уровня.",
                ephemeral=True
            )

        leveling_data = user_data["leveling"]
        xp = leveling_data["total_xp"]
        level = leveling_data["level"]
        voice_time = leveling_data["voice_time"]
        rank, _ = self._get_user_rank(target.id)
        
        current_level_xp = self.get_level_xp(level-1)
        next_level_xp = self.get_level_xp(level)
        progress = min(100, int((xp - current_level_xp) / (next_level_xp - current_level_xp) * 100))
        
        embed = discord.Embed(title=f"Статистика {target.display_name}", color=discord.Color.gold())
        embed.add_field(name="🔢 Ранг", value=f"#{rank}" if rank else "Н/Д", inline=True)
        embed.add_field(name="📊 Уровень", value=str(level), inline=True)
        embed.add_field(name="🎙️ Время в войсе", value=self.format_voice_time(voice_time), inline=False)
        embed.add_field(
            name="📈 Прогресс", 
            value=f"{self._create_progress_bar(progress)} {progress}%\n"
                  f"{xp - current_level_xp}/{next_level_xp - current_level_xp} XP",
            inline=False
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="лидеры", description="Топ активных участников сервера")
    async def top(self, interaction: discord.Interaction):
        """Команда для отображения таблицы лидеров"""
        all_users = []
        for file in self.user_data_path.glob("*.json"):
            if data := self._get_user_data(file.stem):
                if "leveling" in data:
                    all_users.append((data["user_id"], data["leveling"]))
        
        all_users.sort(key=lambda x: x[1]["total_xp"], reverse=True)
        total_pages = len(all_users) // self.LEVEL_SETTINGS['leaderboard_users_per_page']  # Округление вверх
        
        view = LeaderboardView(self.bot, interaction.guild_id, total_pages)
        embed = await view.create_leaderboard_embed(page=1)
        await interaction.response.send_message(embed=embed, view=view)

class LeaderboardView(discord.ui.View):
    """Представление для пагинации таблицы лидеров"""
    
    def __init__(self, bot, guild_id, total_pages):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.current_page = 1
        self.total_pages = total_pages
        self.message = None

    async def create_leaderboard_embed(self, page):
        """Создает embed для текущей страницы"""
        offset = (page - 1) * 10
        user_files = Path("data/users").glob("*.json")
        all_users = []
        
        for file in user_files:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "leveling" in data:
                    all_users.append(data)
        
        all_users.sort(key=lambda x: x["leveling"]["total_xp"], reverse=True)
        top_users = all_users[offset:offset+10]
        guild = self.bot.get_guild(self.guild_id)
        
        leaderboard = []
        for i, user in enumerate(top_users, start=offset+1):
            member = guild.get_member(user["user_id"]) if guild else None
            name = member.display_name if member else f"Неизвестный ({user['user_id']})"
            voice_time = LevelingSystem.format_voice_time(user["leveling"]["voice_time"])
            
            if i == 1:
                entry = f"🏆 **#{i}. {name}**\nУровень: {user['leveling']['level']} | Опыт: {user['leveling']['total_xp']} | 🔊 {voice_time}"
            elif i in (2, 3):
                entry = f"🎖️ **#{i}. {name}**\nУровень: {user['leveling']['level']} | Опыт: {user['leveling']['total_xp']} | 🔊 {voice_time}"
            else:
                entry = f"**#{i}. {name}**\nУровень: {user['leveling']['level']} | Опыт: {user['leveling']['total_xp']}" + (f" | 🔊 {voice_time}" if user["leveling"]["voice_time"] > 0 else "")
            
            leaderboard.append(entry)

        embed = discord.Embed(
            title=f"Топ рейтинга участников (Страница {page}/{self.total_pages})",
            description="\n\n".join(leaderboard) if leaderboard else "Нет данных",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Всего участников: {len(all_users)}")
        return embed
    
    @discord.ui.button(label="◀", style=discord.ButtonStyle.gray, disabled=True)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(1, self.current_page - 1)
        self.next_page.disabled = self.current_page >= self.total_pages
        self.prev_page.disabled = self.current_page <= 1
        await interaction.response.edit_message(
            embed=await self.create_leaderboard_embed(self.current_page),
            view=self
        )
    
    @discord.ui.button(label="▶", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.total_pages, self.current_page + 1)
        self.next_page.disabled = self.current_page >= self.total_pages
        self.prev_page.disabled = self.current_page <= 1
        await interaction.response.edit_message(
            embed=await self.create_leaderboard_embed(self.current_page),
            view=self
        )
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))