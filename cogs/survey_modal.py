import discord
from discord import ui
from discord.ui import Modal, TextInput
import json
import os
import logging
from pathlib import Path
from utils.user_data import get_user_data, save_user_data

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "data/survey_config.json"
USER_DATA_DIR = Path("data/users")

class SurveyModal(Modal, title="Расскажите нам о себе :3"):
    name = TextInput(
        label="Имя / Псевдоним",
        placeholder="Как к Вам обращаться?",
        required=True,
        max_length=100
    )
    age = TextInput(
        label="Возраст",
        placeholder="Можете также указать Ваш ДР",
        required=True,
        max_length=20
    )
    creativity = TextInput(
        label="Вид деятельности",
        placeholder="А чем занимаетесь Вы?",
        required=True,
        max_length=250
    )
    about = TextInput(
        label="Немного о себе",
        style=discord.TextStyle.paragraph,
        placeholder="При написании ведите себя корректно - без самоунижения и спамерства!",
        required=True,
        min_length=100,
        max_length=4000
    )
    socials = TextInput(
        label="Соц. сети",
        style=discord.TextStyle.paragraph,
        placeholder="Можете оставить несколько, каждую с нового абзаца.",
        required=False,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            logger.info(f"Начата обработка анкеты от {interaction.user}")

            # Получаем или создаем данные пользователя
            user_data = get_user_data(interaction.user.id)
            
            # Инициализируем структуру surveys, если её нет
            if "surveys" not in user_data:
                user_data["surveys"] = {
                    "current": None,
                    "history": []  # Явно инициализируем пустой список истории
                }
            elif "history" not in user_data["surveys"]:
                user_data["surveys"]["history"] = []  # Добавляем history, если его нет

            survey_data = {
                "name": self.name.value,
                "age": self.age.value,
                "creativity": self.creativity.value,
                "about": self.about.value,
                "socials": self.socials.value or "Не указано",
                "status": "pending",
                "timestamp": interaction.created_at.isoformat()
            }

            user_data["surveys"]["current"] = survey_data
            user_data["surveys"]["history"].append(survey_data)  # Теперь history точно существует
            
            save_user_data(interaction.user.id, user_data)

            # Получаем настройки каналов
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                mod_channel_id = config.get("модерация")
            except (FileNotFoundError, json.JSONDecodeError):
                mod_channel_id = None

            if not mod_channel_id:
                logger.warning("Канал модерации не настроен")
                return await interaction.followup.send(
                    "❌ Канал модерации не настроен. Обратитесь к администратору.",
                    ephemeral=True
                )

            mod_channel = interaction.client.get_channel(int(mod_channel_id))
            if not mod_channel:
                logger.warning(f"Канал модерации не найден: {mod_channel_id}")
                return await interaction.followup.send(
                    "❌ Не удалось найти канал модерации. Обратитесь к администратору.",
                    ephemeral=True
                )

            # Отправляем анкету на модерацию
            embed = self._build_embed(interaction.user, survey_data)
            view = SurveyModerationView(interaction.user.id)
            
            try:
                await mod_channel.send(embed=embed, view=view)
                logger.info(f"Анкета от {interaction.user} отправлена на модерацию")
                await interaction.followup.send(
                    "✅ Анкета успешно отправлена на модерацию!",
                    ephemeral=True
                )
            except discord.Forbidden:
                logger.error("Нет прав для отправки в канал модерации")
                await interaction.followup.send(
                    "❌ Ошибка доступа к каналу модерации. Обратитесь к администратору.",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API: {e}")
                await interaction.followup.send(
                    "❌ Техническая ошибка при отправке. Попробуйте позже.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
            await interaction.followup.send(
                "⚠️ Произошла непредвиденная ошибка. Администратор уже уведомлен.",
                ephemeral=True
            )

    def _build_embed(self, user: discord.User, data: dict) -> discord.Embed:
        """Создает embed для анкеты"""
        embed = discord.Embed(
            title=f"Анкета участника {user.display_name}", 
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        fields = [
            ("Имя / Псевдоним", data.get("name", "Не указано")),
            ("Возраст", data.get("age", "Не указано")),
            ("Вид деятельности", data.get("creativity", "Не указано")),
            ("Немного о себе", data.get("about", "Не указано")),
            ("Соц. сети", data.get("socials", "Не указано"))
        ]
        
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
            
        return embed

class SurveyModerationView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Одобрить", style=discord.ButtonStyle.success, custom_id="approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Получаем данные пользователя
            user_data = get_user_data(self.user_id)
            if not user_data or "surveys" not in user_data or not user_data["surveys"]["current"]:
                logger.warning(f"Анкета не найдена для user_id: {self.user_id}")
                return await interaction.response.send_message(
                    "❌ Анкета не найдена в системе.",
                    ephemeral=True
                )

            # Обновляем статус анкеты
            user_data["surveys"]["current"]["status"] = "approved"
            save_user_data(self.user_id, user_data)

            # Получаем настройки канала публикации
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                pub_channel_id = config.get("публикация")
            except (FileNotFoundError, json.JSONDecodeError):
                pub_channel_id = None

            if not pub_channel_id:
                logger.warning("Канал публикации не настроен")
                return await interaction.response.send_message(
                    "❌ Канал публикации не настроен. Обратитесь к администратору.",
                    ephemeral=True
                )

            pub_channel = interaction.client.get_channel(int(pub_channel_id))
            if not pub_channel:
                logger.warning(f"Канал публикации не найден: {pub_channel_id}")
                return await interaction.response.send_message(
                    "❌ Не удалось найти канал публикации. Обратитесь к администратору.",
                    ephemeral=True
                )

            # Публикуем анкету
            embed = self._build_embed(interaction.client.get_user(self.user_id), 
                             user_data["surveys"]["current"])
            try:
                message = await pub_channel.send(embed=embed)
                await message.add_reaction("❤️")
                logger.info(f"Анкета {self.user_id} опубликована в {pub_channel.id}")
                await interaction.response.send_message(
                    "✅ Анкета одобрена и успешно опубликована!",
                    ephemeral=True
                )
            except discord.Forbidden:
                logger.error("Нет прав для публикации анкеты")
                await interaction.response.send_message(
                    "❌ Нет прав для публикации в указанном канале.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Ошибка при публикации анкеты: {e}", exc_info=True)
            await interaction.response.send_message(
                "⚠️ Произошла ошибка при публикации. Администратор уведомлен.",
                ephemeral=True
            )

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, custom_id="reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(RejectionReasonModal(self.user_id))
        except Exception as e:
            logger.error(f"Ошибка при открытии модального окна отклонения: {e}")
            await interaction.response.send_message(
                "⚠️ Не удалось открыть форму отклонения. Попробуйте снова.",
                ephemeral=True
            )

    def _build_embed(self, user: discord.User, data: dict) -> discord.Embed:
        """Создает embed для анкеты"""
        embed = discord.Embed(
            title=f"Анкета участника {user.display_name}", 
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        fields = [
            ("Имя / Псевдоним", data.get("name", "Не указано")),
            ("Возраст", data.get("age", "Не указано")),
            ("Вид деятельности", data.get("creativity", "Не указано")),
            ("Немного о себе", data.get("about", "Не указано")),
            ("Соц. сети", data.get("socials", "Не указано"))
        ]
        
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
            
        return embed

class RejectionReasonModal(Modal, title="Причина отклонения анкеты"):
    reason = TextInput(
        label="Причина",
        style=discord.TextStyle.paragraph,
        placeholder="Укажите причину отклонения",
        required=True,
        max_length=1000
    )

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Получаем данные пользователя
            user_data = get_user_data(self.user_id)
            if not user_data or "surveys" not in user_data or not user_data["surveys"]["current"]:
                logger.warning(f"Анкета не найдена для user_id: {self.user_id}")
                return await interaction.response.send_message(
                    "❌ Не удалось найти анкету.",
                    ephemeral=True
                )

            # Обновляем статус анкеты
            user_data["surveys"]["current"]["status"] = "rejected"
            user_data["surveys"]["current"]["rejection_reason"] = self.reason.value
            save_user_data(self.user_id, user_data)

            # Отправляем уведомление пользователю
            user = await interaction.client.fetch_user(self.user_id)
            if user:
                embed = self._build_embed(user, user_data["surveys"]["current"])
                try:
                    await user.send(
                        content=f"❌ Ваша анкета была отклонена. Причина: {self.reason.value}",
                        embed=embed
                    )
                    logger.info(f"Уведомление об отклонении отправлено пользователю {self.user_id}")
                    await interaction.response.send_message(
                        "✅ Пользователь уведомлен об отклонении анкеты.",
                        ephemeral=True
                    )
                except discord.Forbidden:
                    logger.warning(f"Не удалось отправить ЛС пользователю {self.user_id}")
                    await interaction.response.send_message(
                        "⚠️ Не удалось отправить сообщение пользователю. Возможно, у него закрыты ЛС.",
                        ephemeral=True
                    )
            else:
                logger.warning(f"Не удалось найти пользователя: {self.user_id}")
                await interaction.response.send_message(
                    "⚠️ Не удалось найти пользователя для отправки уведомления.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Ошибка при обработке отклонения: {e}", exc_info=True)
            await interaction.response.send_message(
                "⚠️ Произошла ошибка при обработке отклонения. Администратор уведомлен.",
                ephemeral=True
            )

    def _build_embed(self, user: discord.User, data: dict) -> discord.Embed:
        """Создает embed для отклоненной анкеты"""
        embed = discord.Embed(
            title=f"Ваша анкета была отклонена",
            color=discord.Color.red(),
            description=f"Причина: {data.get('rejection_reason', 'Не указана')}"
        )
        
        fields = [
            ("Имя / Псевдоним", data.get("name", "Не указано")),
            ("Возраст", data.get("age", "Не указано")),
            ("Вид деятельности", data.get("creativity", "Не указано"))
        ]
        
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
            
        return embed