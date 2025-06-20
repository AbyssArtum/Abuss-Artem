import discord
from discord import app_commands, ui
from discord.ext import commands
import sqlite3
from typing import Optional

class ReportDB:
    def __init__(self, db_path="data/reports.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL,
                target_id BIGINT NOT NULL,
                reporter_id BIGINT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                moderator_id BIGINT,
                action_taken TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def add_report(self, guild_id, target_id, reporter_id, reason):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO reports (guild_id, target_id, reporter_id, reason)
            VALUES (?, ?, ?, ?)
        """, (guild_id, target_id, reporter_id, reason))
        self.conn.commit()
        return cursor.lastrowid

    def update_report(self, report_id, status, moderator_id, action_taken):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE reports 
            SET status = ?, moderator_id = ?, action_taken = ?
            WHERE id = ?
        """, (status, moderator_id, action_taken, report_id))
        self.conn.commit()

class ReportActionView(ui.View):
    def __init__(self, target: discord.Member, reporter: discord.Member, reason: str, report_id: int):
        super().__init__(timeout=None)
        self.target = target
        self.reporter = reporter
        self.reason = reason
        self.report_id = report_id

    @ui.button(label="Наказать", style=discord.ButtonStyle.red, emoji="🔨")
    async def punish(self, interaction: discord.Interaction, button: ui.Button):
        view = PunishmentSelectView(self.target, self.reason, self.report_id)
        await interaction.response.send_message(
            "Выберите тип наказания:",
            view=view,
            ephemeral=True
        )

    @ui.button(label="Игнорировать", style=discord.ButtonStyle.gray, emoji="❌")
    async def ignore(self, interaction: discord.Interaction, button: ui.Button):
        report_cog = interaction.client.get_cog("ModerationReports")
        if report_cog:
            report_cog.db.update_report(
                self.report_id,
                status="rejected",
                moderator_id=interaction.user.id,
                action_taken="ignored"
            )
        await interaction.message.edit(view=None)
        await interaction.response.send_message("Жалоба проигнорирована.", ephemeral=True)

class PunishmentSelectView(ui.View):
    def __init__(self, target: discord.Member, reason: str, report_id: int):
        super().__init__()
        self.target = target
        self.reason = reason
        self.report_id = report_id

    @ui.select(
        placeholder="Выберите наказание",
        options=[
            discord.SelectOption(label="Предупреждение", value="warn"),
            discord.SelectOption(label="Мут", value="mute"),
            discord.SelectOption(label="Кик", value="kick"),
            discord.SelectOption(label="Бан", value="ban")
        ]
    )
    async def select_punishment(self, interaction: discord.Interaction, select: ui.Select):
        report_cog = interaction.client.get_cog("ModerationReports")
        if not report_cog:
            return await interaction.response.send_message("Ошибка системы!", ephemeral=True)

        action = select.values[0]
        report_cog.db.update_report(
            self.report_id,
            status="approved",
            moderator_id=interaction.user.id,
            action_taken=action
        )

        # Здесь должна быть логика применения наказания
        # Например, через вызов соответствующих команд модерации
        
        await interaction.message.edit(view=None)
        await interaction.response.send_message(
            f"Наказание '{action}' применено к {self.target.mention}",
            ephemeral=True
        )

class ModerationReports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = ReportDB()  # Используем наш класс для работы с БД

    async def get_log_channel(self, guild_id: int) -> Optional[discord.TextChannel]:
        # Здесь должна быть логика получения канала для логов
        # Например, из другой системы или конфига
        return None  # Замените на реальную реализацию

    @app_commands.command(name="репорт", description="Отправить жалобу на участника")
    @app_commands.describe(участник="Участник для жалобы", причина="Причина жалобы")
    async def report_command(self, interaction: discord.Interaction, 
                           участник: discord.Member, 
                           причина: str):
        if участник.bot:
            return await interaction.response.send_message(
                "Нельзя пожаловаться на бота!", 
                ephemeral=True
            )

        if участник.id == interaction.user.id:
            return await interaction.response.send_message(
                "Нельзя пожаловаться на самого себя!",
                ephemeral=True
            )

        log_channel = await self.get_log_channel(interaction.guild.id)
        if not log_channel:
            return await interaction.response.send_message(
                "❌ Система жалоб не настроена администратором.",
                ephemeral=True
            )

        try:
            report_id = self.db.add_report(
                guild_id=interaction.guild.id,
                target_id=участник.id,
                reporter_id=interaction.user.id,
                reason=причина
            )

            embed = discord.Embed(
                title=f"Жалоба #{report_id} на {участник.display_name}",
                color=discord.Color.red(),
                description=f"**Причина:** {причина}"
            )
            embed.add_field(name="Отправитель", value=interaction.user.mention)
            embed.add_field(name="Участник", value=участник.mention)
            embed.set_footer(text=f"ID: {участник.id}")

            await log_channel.send(
                embed=embed,
                view=ReportActionView(участник, interaction.user, причина, report_id)
            )

            await interaction.response.send_message(
                "✅ Ваша жалоба отправлена модераторам.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ModerationReports(bot))