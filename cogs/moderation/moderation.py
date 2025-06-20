import discord
from discord import app_commands
from discord.ext import commands
import sqlite3  # или другой драйвер (asyncpg для PostgreSQL)

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect("data/moderation.db")  # Путь к вашей SQL-базе
        self._init_db()

    def _init_db(self):
        cursor = self.db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_channels (
                guild_id BIGINT PRIMARY KEY,
                punishments_channel_id BIGINT,
                reports_channel_id BIGINT
            )
        """)
        self.db.commit()

    async def get_log_channel(self, guild_id: int, log_type: str) -> int | None:
        """Возвращает ID канала для логов (наказания/жалобы)."""
        cursor = self.db.cursor()
        cursor.execute(
            f"SELECT {log_type}_channel_id FROM log_channels WHERE guild_id = ?",
            (guild_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    async def set_log_channel(self, guild_id: int, log_type: str, channel_id: int):
        """Устанавливает канал для логов (наказания/жалобы)."""
        cursor = self.db.cursor()
        # Проверяем, есть ли уже запись для этого сервера
        cursor.execute(
            "SELECT guild_id FROM log_channels WHERE guild_id = ?",
            (guild_id,)
        )
        exists = cursor.fetchone()

        if exists:
            # Обновляем существующую запись
            cursor.execute(
                f"UPDATE log_channels SET {log_type}_channel_id = ? WHERE guild_id = ?",
                (channel_id, guild_id)
            )
        else:
            # Создаём новую запись
            cursor.execute(
                "INSERT INTO log_channels (guild_id, punishments_channel_id, reports_channel_id) "
                "VALUES (?, ?, ?)",
                (guild_id, None, None)
            )
            # Теперь обновляем нужный канал
            await self.set_log_channel(guild_id, log_type, channel_id)
        self.db.commit()

    @app_commands.command(name="лог_канал", description="Настройка каналов для логов")
    @app_commands.describe(
        настройка="Тип логов",
        канал="Канал для отправки логов"
    )
    @app_commands.choices(
        настройка=[
            app_commands.Choice(name="наказания", value="punishments"),
            app_commands.Choice(name="жалобы", value="reports"),
        ]
    )
    async def log_channel(
        self,
        interaction: discord.Interaction,
        настройка: app_commands.Choice[str],
        канал: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Требуются права администратора!", ephemeral=True)
            return

        await self.set_log_channel(interaction.guild.id, настройка.value, канал.id)

        await interaction.response.send_message(
            f"✅ Канал {канал.mention} установлен для логов типа **{настройка.name}**!",
            ephemeral=True
        )

    async def send_to_log(self, guild_id: int, log_type: str, embed: discord.Embed) -> bool:
        """Отправляет сообщение в сохранённый канал логов."""
        channel_id = await self.get_log_channel(guild_id, log_type)
        if not channel_id:
            return False

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return False

        await channel.send(embed=embed)
        return True

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))