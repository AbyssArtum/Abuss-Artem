import discord
from discord import ui
from discord.ui import Modal, TextInput
import json
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "data/survey_config.json"
SURVEY_DATA_DIR = "data/surveys"

class SurveyModal(ui.Modal):
    async def on_submit(self, interaction: discord.Interaction):
        cursor = self.bot.db.cursor()
        cursor.execute("""
            INSERT INTO surveys (user_id, guild_id, content)
            VALUES (?, ?, ?)
        """, (interaction.user.id, interaction.guild.id, json.dumps(анкета_в_json)))
        self.bot.db.commit()

if not os.path.exists(SURVEY_DATA_DIR):
    os.makedirs(SURVEY_DATA_DIR)

def load_config():
    try:
        if not os.path.exists(CONFIG_FILE):
            logger.warning(f"Конфиг файл не найден: {CONFIG_FILE}")
            return {}
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка чтения конфига: {e}")
        return {}

def save_survey(user_id, data):
    try:
        with open(f"{SURVEY_DATA_DIR}/{user_id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка сохранения анкеты: {e}")
        raise

def build_embed(user: discord.User, data: dict):
    try:
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
    except Exception as e:
        logger.error(f"Ошибка создания embed: {e}")
        raise

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
        max_length=100
    )
    about = TextInput(
        label="Немного о себе",
        style=discord.TextStyle.paragraph,
        placeholder="Без самоунижения и спамерства!",
        required=True,
        min_length=100,
        max_length=2000
    )
    socials = TextInput(
        label="Соц. сети",
        placeholder="Ссылки на Ваши соцсети",
        required=False,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            logger.info(f"Начата обработка анкеты от {interaction.user}")
            
            data = {
                "name": self.name.value,
                "age": self.age.value,
                "creativity": self.creativity.value,
                "about": self.about.value,
                "socials": self.socials.value or "Не указано"
            }
            
            # Сохраняем анкету
            save_survey(interaction.user.id, data)
            
            # Получаем настройки
            config = load_config()
            mod_channel_id = config.get("модерация")
            
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

            # Подготавливаем и отправляем анкету
            embed = build_embed(interaction.user, data)
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
            try:
                await interaction.followup.send(
                    "⚠️ Произошла непредвиденная ошибка. Администратор уже уведомлен.",
                    ephemeral=True
                )
            except:
                pass

class SurveyModerationView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Одобрить", style=discord.ButtonStyle.success, custom_id="approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            from data.survey_storage import get_survey_embed
            from cogs.survey_com import load_config

            embed = get_survey_embed(self.user_id)
            if not embed:
                logger.warning(f"Анкета не найдена для user_id: {self.user_id}")
                return await interaction.response.send_message(
                    "❌ Анкета не найдена в системе.",
                    ephemeral=True
                )

            config = load_config()
            pub_channel_id = config.get("публикация")
            
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

class RejectionReasonModal(Modal, title="Причина отклонения анкеты"):
    reason = TextInput(
        label="Причина",
        style=discord.TextStyle.paragraph,
        placeholder="Укажите причину отклонения",
        required=True,
        max_length=1000
    )

    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            from data.survey_storage import get_survey_embed
            
            user = await interaction.client.fetch_user(self.user_id)
            embed = get_survey_embed(self.user_id)
            
            if not user or not embed:
                logger.warning(f"Не удалось найти пользователя или анкету: {self.user_id}")
                return await interaction.response.send_message(
                    "❌ Не удалось найти анкету или пользователя.",
                    ephemeral=True
                )

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
                
        except Exception as e:
            logger.error(f"Ошибка при обработке отклонения: {e}", exc_info=True)
            await interaction.response.send_message(
                "⚠️ Произошла ошибка при обработке отклонения. Администратор уведомлен.",
                ephemeral=True
            )