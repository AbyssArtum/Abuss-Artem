import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path
from typing import Optional

class LevelingCommands(commands.Cog):
    """Команды для управления системой уровней"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_path = Path("data/users")
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Настройки опыта (совместимость с leveling.py)
        self.xp_settings = {
            'voice_xp_per_min': 20,
            'min_xp': 0,
            'max_level': 100
        }

    def _load_user_data(self, user_id: int) -> dict:
        """Загружает данные пользователя из файла"""
        file_path = self.data_path / f"{user_id}.json"
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"user_id": user_id}
        except (json.JSONDecodeError, IOError):
            return {"user_id": user_id}

    def _save_user_data(self, user_id: int, data: dict):
        """Сохраняет данные пользователя в файл"""
        file_path = self.data_path / f"{user_id}.json"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except IOError:
            return False

    def _init_leveling_data(self, user_data: dict) -> dict:
        """Инициализирует данные уровня, если их нет"""
        if "leveling" not in user_data:
            user_data["leveling"] = {
                "text_xp": 0,
                "voice_xp": 0,
                "total_xp": 0,
                "level": 1,
                "voice_time": 0
            }
        return user_data

    def _calculate_level(self, total_xp: int) -> int:
        """Рассчитывает уровень на основе общего опыта"""
        level = 1
        while total_xp >= self._get_level_requirement(level) and level < self.xp_settings['max_level']:
            level += 1
        return min(level, self.xp_settings['max_level'])

    def _get_level_requirement(self, level: int) -> int:
        """Возвращает необходимый опыт для уровня"""
        return 100 * (level ** 2)  # Базовый расчет (можно адаптировать)

    async def _update_user_stats(self, user_id: int, xp_change: int, voice_minutes: int = 0) -> tuple:
        """Обновляет статистику пользователя и возвращает (старый_уровень, новый_уровень)"""
        user_data = self._load_user_data(user_id)
        user_data = self._init_leveling_data(user_data)
        
        old_level = user_data["leveling"]["level"]
        
        # Обновляем опыт
        user_data["leveling"]["total_xp"] = max(
            self.xp_settings['min_xp'],
            user_data["leveling"]["total_xp"] + xp_change
        )
        
        # Обновляем голосовое время (если указано)
        if voice_minutes:
            user_data["leveling"]["voice_time"] = max(
                0,
                user_data["leveling"]["voice_time"] + voice_minutes
            )
            user_data["leveling"]["voice_xp"] = max(
                0,
                user_data["leveling"]["voice_xp"] + int(voice_minutes * self.xp_settings['voice_xp_per_min'])
            )
        else:
            user_data["leveling"]["text_xp"] = max(
                0,
                user_data["leveling"]["text_xp"] + xp_change
            )
        
        # Пересчитываем уровень
        user_data["leveling"]["level"] = self._calculate_level(user_data["leveling"]["total_xp"])
        new_level = user_data["leveling"]["level"]
        
        # Сохраняем изменения
        if not self._save_user_data(user_id, user_data):
            raise IOError("Не удалось сохранить данные пользователя")
        
        return old_level, new_level

    @app_commands.command(name="опыт", description="Управление опытом участников")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        действие="Начислить или снять опыт",
        тип="Тип опыта: общий или голосовой",
        количество="Количество (число для общего, минуты для голосового)",
        участник="Участник, которому начисляем/снимаем"
    )
    @app_commands.choices(
        действие=[
            app_commands.Choice(name="начислить", value="add"),
            app_commands.Choice(name="снять", value="remove")
        ],
        тип=[
            app_commands.Choice(name="общий", value="general"),
            app_commands.Choice(name="голосовой", value="voice")
        ]
    )
    async def manage_xp(
        self,
        interaction: discord.Interaction,
        действие: app_commands.Choice[str],
        тип: app_commands.Choice[str],
        количество: int,
        участник: discord.Member
    ):
        """Основная команда для управления опытом"""
        if количество <= 0:
            return await interaction.response.send_message(
                "❌ Количество должно быть положительным числом!",
                ephemeral=True
            )
        
        if участник.bot:
            return await interaction.response.send_message(
                "❌ Нельзя изменять опыт ботов!",
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Определяем множитель и абсолютное значение
            multiplier = 1 if действие.value == "add" else -1
            amount = количество * multiplier
            
            if тип.value == "general":
                # Общий опыт
                old_level, new_level = await self._update_user_stats(участник.id, amount)
                
                action_word = "начислен" if действие.value == "add" else "снят"
                message = f"✅ {участник.mention}: {action_word} {количество} общего опыта"
                
                if new_level != old_level:
                    message += f" (Уровень {'повышен' if действие.value == 'add' else 'понижен'} до {new_level})"
            
            elif тип.value == "voice":
                # Голосовой опыт
                voice_xp = int(amount * self.xp_settings['voice_xp_per_min'])
                old_level, new_level = await self._update_user_stats(
                    участник.id, 
                    voice_xp,
                    voice_minutes=amount
                )
                
                action_word = "начислено" if действие.value == "add" else "снято"
                message = f"✅ {участник.mention}: {action_word} {количество} минут голосовой активности"
                
                if new_level != old_level:
                    message += f" (Уровень {'повышен' if действие.value == 'add' else 'понижен'} до {new_level})"
            
            await interaction.followup.send(message, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Произошла ошибка: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LevelingCommands(bot))