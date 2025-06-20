import discord
from discord import app_commands, ui
from discord.ext import commands
import time
from datetime import datetime

class WarnModal(ui.Modal, title="Выдать предупреждение"):
    def __init__(self, target: discord.Member, reason: str, cog, parent_view=None):
        super().__init__()
        self.target = target
        self.reason = reason
        self.cog = cog
        self.parent_view = parent_view
        
        self.reason_input = ui.TextInput(
            label="Причина",
            style=discord.TextStyle.long,
            default=reason,
            required=True
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        base_cog = self.cog.bot.get_cog("ModerationBase")
        if not base_cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        if self.target.id not in base_cog.data["warns"]:
            base_cog.data["warns"][self.target.id] = []
            
        warn_data = {
            "moderator": interaction.user.id,
            "reason": self.reason_input.value,
            "timestamp": time.time()
        }
        base_cog.data["warns"][self.target.id].append(warn_data)
        base_cog.save_data()
        
        embed = discord.Embed(
            title="✅ Предупреждение выдано",
            description=f"Участник {self.target.mention} получил предупреждение.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Причина", value=self.reason_input.value)
        embed.add_field(name="Всего предупреждений", value=len(base_cog.data["warns"][self.target.id]))
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Отправка уведомления
        await self.send_warn_notification(self.target, interaction.user, self.reason_input.value)
        
        # Логирование и обновление сообщения жалобы
        if self.parent_view and hasattr(self.cog, 'log_report_action'):
            await self.cog.log_report_action(interaction.message, "предупреждение", interaction.user)
            
        # Логирование в канал наказаний
        await self.log_punishment(interaction, self.target, "предупреждение", self.reason_input.value)

    async def send_warn_notification(self, member: discord.Member, moderator: discord.Member, reason: str):
        embed = discord.Embed(
            title="Вы получили предупреждение",
            description=f"На сервере {moderator.guild.name} вам выдали предупреждение.",
            color=discord.Color.red()
        )
        embed.add_field(name="Модератор", value=moderator.mention)
        embed.add_field(name="Причина", value=reason)
        
        try:
            await member.send(embed=embed)
        except:
            pass

    async def log_punishment(self, interaction: discord.Interaction, target: discord.Member, action: str, reason: str):
        base_cog = self.cog.bot.get_cog("ModerationBase")
        if not base_cog or not base_cog.data["log_channels"]["punishments"]:
            return
            
        channel = self.bot.get_channel(base_cog.data["log_channels"]["punishments"])
        if not channel:
            return
            
        embed = discord.Embed(
            title=f"Действие модерации: {action.upper()}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Модератор", value=interaction.user.mention)
        embed.add_field(name="Участник", value=target.mention)
        embed.add_field(name="Причина", value=reason)
        
        await channel.send(embed=embed)

class ModerationWarns(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="пред", description="Выдать предупреждение участнику")
    @app_commands.describe(участник="Участник для предупреждения", причина="Причина предупреждения")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, участник: discord.Member, причина: str):
        if участник.id == interaction.user.id:
            return await interaction.response.send_message("Вы не можете выдать предупреждение себе!", ephemeral=True)
        
        if участник.guild_permissions.manage_messages:
            return await interaction.response.send_message("Вы не можете выдать предупреждение модератору!", ephemeral=True)
        
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        if участник.id not in base_cog.data["warns"]:
            base_cog.data["warns"][участник.id] = []
            
        warn_data = {
            "moderator": interaction.user.id,
            "reason": причина,
            "timestamp": time.time()
        }
        base_cog.data["warns"][участник.id].append(warn_data)
        base_cog.save_data()
        
        embed = discord.Embed(
            title="✅ Предупреждение выдано",
            description=f"Участник {участник.mention} получил предупреждение.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Причина", value=причина)
        embed.add_field(name="Всего предупреждений", value=len(base_cog.data["warns"][участник.id]))
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Отправка уведомления
        await self.send_warn_notification(участник, interaction.user, причина)
        
        # Логирование
        await self.log_punishment(interaction, участник, "предупреждение", причина)

    async def send_warn_notification(self, member: discord.Member, moderator: discord.Member, reason: str):
        embed = discord.Embed(
            title="Вы получили предупреждение",
            description=f"На сервере {moderator.guild.name} вам выдали предупреждение.",
            color=discord.Color.red()
        )
        embed.add_field(name="Модератор", value=moderator.mention)
        embed.add_field(name="Причина", value=reason)
        
        try:
            await member.send(embed=embed)
        except:
            pass

    async def log_punishment(self, interaction: discord.Interaction, target: discord.Member, action: str, reason: str):
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog or not base_cog.data["log_channels"]["punishments"]:
            return
            
        channel = self.bot.get_channel(base_cog.data["log_channels"]["punishments"])
        if not channel:
            return
            
        embed = discord.Embed(
            title=f"Действие модерации: {action.upper()}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Модератор", value=interaction.user.mention)
        embed.add_field(name="Участник", value=target.mention)
        embed.add_field(name="Причина", value=reason)
        
        await channel.send(embed=embed)

    @app_commands.command(name="предлист", description="Посмотреть предупреждения участника")
    @app_commands.describe(участник="Участник для проверки")
    async def warns(self, interaction: discord.Interaction, участник: discord.Member):
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        if участник.id not in base_cog.data["warns"] or not base_cog.data["warns"][участник.id]:
            return await interaction.response.send_message(
                f"У {участник.mention} нет предупреждений.",
                ephemeral=True
            )
            
        embed = discord.Embed(
            title=f"Предупреждения {участник.display_name}",
            color=discord.Color.orange()
        )
        
        for i, warn in enumerate(base_cog.data["warns"][участник.id], 1):
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
    @commands.has_permissions(manage_messages=True)
    async def unwarn(self, interaction: discord.Interaction, участник: discord.Member):
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        if участник.id not in base_cog.data["warns"] or not base_cog.data["warns"][участник.id]:
            return await interaction.response.send_message(
                f"У {участник.mention} нет предупреждений.",
                ephemeral=True
            )
            
        last_warn = base_cog.data["warns"][участник.id].pop()
        if not base_cog.data["warns"][участник.id]:
            base_cog.data["warns"].pop(участник.id)
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
        
        # Логирование
        await self.log_punishment(interaction, участник, "снятие предупреждения", "Снято последнее предупреждение")

    async def log_punishment(self, interaction: discord.Interaction, target: discord.Member, action: str, reason: str):
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog or not base_cog.data["log_channels"]["punishments"]:
            return
            
        channel = self.bot.get_channel(base_cog.data["log_channels"]["punishments"])
        if not channel:
            return
            
        embed = discord.Embed(
            title=f"Действие модерации: {action.upper()}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Модератор", value=interaction.user.mention)
        embed.add_field(name="Участник", value=target.mention)
        embed.add_field(name="Причина", value=reason)
        
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ModerationWarns(bot))