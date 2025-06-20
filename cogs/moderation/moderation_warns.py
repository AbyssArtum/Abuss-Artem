import discord
from discord import app_commands, ui
from discord.ext import commands
import time

class WarnModal(ui.Modal, title="Выдать предупреждение"):
    def __init__(self, target: discord.Member, reason: str, cog):
        super().__init__()
        self.target = target
        self.original_reason = reason
        self.cog = cog
        
        self.reason = ui.TextInput(
            label="Причина",
            style=discord.TextStyle.long,
            placeholder=reason,
            default=reason,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        base_cog = self.cog.bot.get_cog("ModerationBase")
        if not base_cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        if self.target.id not in base_cog.warns:
            base_cog.warns[self.target.id] = []
            
        warn_data = {
            "moderator": interaction.user.id,
            "reason": self.reason.value,
            "timestamp": time.time()
        }
        base_cog.warns[self.target.id].append(warn_data)
        base_cog.save_data()
        
        embed = discord.Embed(
            title="✅ Предупреждение выдано",
            description=f"Участник {self.target.mention} получил предупреждение.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Причина", value=self.reason.value)
        embed.add_field(name="Всего предупреждений", value=len(base_cog.warns[self.target.id]))
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Отправка уведомления
        await self.send_warn_notification(self.target, interaction.user, self.reason.value)
        
        # Обновление сообщения жалобы
        if hasattr(self.cog, 'log_report_action'):
            await self.cog.log_report_action(interaction.message, "предупреждение")

    async def send_warn_notification(self, member: discord.Member, moderator: discord.Member, reason: str):
        embed = discord.Embed(
            title="Вы получили предупреждение",
            description=f"На сервере {moderator.guild.name} вам выдали предупреждение.",
            color=discord.Color.red()
        )
        embed.add_field(name="Модератор", value=moderator.mention)
        base_cog = self.cog.bot.get_cog("ModerationBase")
        warn_count = len(base_cog.warns.get(member.id, [])) if base_cog else "?"
        embed.add_field(name="Всего предупреждений", value=str(warn_count))
        embed.add_field(name="Причина", value=reason)
        
        try:
            await member.send(embed=embed)
        except:
            pass

class ModerationWarns(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="пред", description="Выдать предупреждение участнику")
    @app_commands.describe(участник="Участник для предупреждения", причина="Причина предупреждения")
    async def warn(self, interaction: discord.Interaction, участник: discord.Member, причина: str = None):
        await interaction.response.send_modal(WarnModal(участник, причина or "Не указана", self))

    @app_commands.command(name="предлист", description="Посмотреть предупреждения участника")
    @app_commands.describe(участник="Участник для проверки")
    async def warns(self, interaction: discord.Interaction, участник: discord.Member):
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        if участник.id not in base_cog.warns or not base_cog.warns[участник.id]:
            return await interaction.response.send_message(
                f"У {участник.mention} нет предупреждений.",
                ephemeral=True
            )
            
        embed = discord.Embed(
            title=f"Предупреждения {участник.display_name}",
            color=discord.Color.orange()
        )
        
        for i, warn in enumerate(base_cog.warns[участник.id], 1):
            moderator = await self.bot.fetch_user(warn["moderator"])
            timestamp = discord.utils.format_dt(discord.utils.utcfromtimestamp(warn["timestamp"]), "f")
            embed.add_field(
                name=f"Предупреждение #{i}",
                value=f"**Модератор:** {moderator.mention}\n**Причина:** {warn['reason']}\n**Дата:** {timestamp}",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="снятьпред", description="Снять предупреждение с участника")
    @app_commands.describe(участник="Участник для снятия предупреждения")
    async def unwarn(self, interaction: discord.Interaction, участник: discord.Member):
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        if участник.id not in base_cog.warns or not base_cog.warns[участник.id]:
            return await interaction.response.send_message(
                f"У {участник.mention} нет предупреждений.",
                ephemeral=True
            )
            
        base_cog.warns[участник.id].pop()
        if not base_cog.warns[участник.id]:
            base_cog.warns.pop(участник.id)
        base_cog.save_data()
        
        embed = discord.Embed(
            title="✅ Предупреждение снято",
            description=f"С участника {участник.mention} снято последнее предупреждение.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Отправка уведомления
        embed = discord.Embed(
            title="С вас снято предупреждение",
            description=f"На сервере {interaction.guild.name} с вас снято предупреждение.",
            color=discord.Color.green()
        )
        embed.add_field(name="Модератор", value=interaction.user.mention)
        try:
            await участник.send(embed=embed)
        except:
            pass

async def setup(bot):
    await bot.add_cog(ModerationWarns(bot))