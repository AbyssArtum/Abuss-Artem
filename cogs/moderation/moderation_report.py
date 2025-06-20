import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime
import sqlite3  # или asyncpg для PostgreSQL

class ReportDB:
    def __init__(self, db_path="data/reports.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        # Таблица для хранения жалоб
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL,
                target_id BIGINT NOT NULL,
                reporter_id BIGINT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT DEFAULT 'pending',  -- pending/approved/rejected
                moderator_id BIGINT,
                action_taken TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Таблица для связи с другими системами (анкеты, уровень)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                warnings INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                voice_xp INTEGER DEFAULT 0
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
        view = ui.View()
        view.add_item(PunishmentSelect(self.target, self.reason, self))
        await interaction.response.send_message(
            "Выберите тип наказания:",
            view=view,
            ephemeral=True
        )

    @ui.button(label="Игнорировать", style=discord.ButtonStyle.gray, emoji="❌")
    async def ignore(self, interaction: discord.Interaction, button: ui.Button):
        report_cog = interaction.client.get_cog("ModerationReports")
        if report_cog:
            await report_cog.db.update_report(
                self.report_id,
                status="rejected",
                moderator_id=interaction.user.id,
                action_taken="ignored"
            )
        await interaction.message.edit(view=None)
        await interaction.response.send_message("Жалоба проигнорирована.", ephemeral=True)

class ModerationReports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect('data/main.db')

    async def report(self, interaction: discord.Interaction, участник: discord.Member, причина: str):
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO reports (target_id, reporter_id, guild_id, reason)
            VALUES (?, ?, ?, ?)
        """, (участник.id, interaction.user.id, interaction.guild.id, причина))
        self.db.commit()

    async def get_log_channel(self, guild_id: int) -> discord.TextChannel | None:
        moderation_cog = self.bot.get_cog("ModerationCog")
        if not moderation_cog:
            return None
        channel_id = await moderation_cog.get_log_channel(guild_id, "reports")
        return self.bot.get_channel(channel_id) if channel_id else None

    @app_commands.command(name="репорт", description="Отправить жалобу на участника")
    @app_commands.describe(участник="Участник для жалобы", причина="Причина жалобы")
    async def report(self, interaction: discord.Interaction, участник: discord.Member, причина: str):
        log_channel = await self.get_log_channel(interaction.guild.id)
        if not log_channel:
            return await interaction.response.send_message(
                "❌ Система жалоб не настроена администратором.",
                ephemeral=True
            )

        # Сохраняем жалобу в базу
        report_id = self.db.add_report(
            guild_id=interaction.guild.id,
            target_id=участник.id,
            reporter_id=interaction.user.id,
            reason=причина
        )

        # Отправляем жалобу в канал
        embed = discord.Embed(
            title=f"Жалоба на {участник.display_name}",
            color=discord.Color.red(),
            description=f"**Причина:** {причина}"
        )
        embed.add_field(name="От", value=interaction.user.mention, inline=True)
        embed.add_field(name="ID участника", value=участник.id, inline=True)
        embed.set_footer(text=f"ID жалобы: {report_id}")

        await log_channel.send(
            embed=embed,
            view=ReportActionView(участник, interaction.user, причина, report_id)
        )
        await interaction.response.send_message(
            "✅ Ваша жалоба отправлена модераторам.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(ModerationReports(bot))