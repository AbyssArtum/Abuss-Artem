import discord
from discord import app_commands, ui
from discord.ext import commands
import time
from datetime import datetime
from utils.user_data import get_user_data, save_user_data
from typing import Optional

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
        user_data = get_user_data(self.target.id)
        
        if "moderation" not in user_data:
            user_data["moderation"] = {"warns": []}
        
        warn_data = {
            "moderator_id": interaction.user.id,
            "reason": self.reason_input.value,
            "timestamp": datetime.now().isoformat()
        }
        
        user_data["moderation"]["warns"].append(warn_data)
        save_user_data(self.target.id, user_data)
        
        embed = discord.Embed(
            title="✅ Предупреждение выдано",
            description=f"Участник {self.target.mention} получил предупреждение.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Причина", value=self.reason_input.value)
        embed.add_field(name="Всего предупреждений", value=len(user_data["moderation"]["warns"]))
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Отправка уведомления
        await self.send_warn_notification(self.target, interaction.user, self.reason_input.value)
        
        # Логирование
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
        log_cog = interaction.client.get_cog("ModerationBase")
        if not log_cog or not log_cog.punishments_log_channel:
            return
            
        embed = discord.Embed(
            title=f"Действие модерации: {action.upper()}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Модератор", value=interaction.user.mention)
        embed.add_field(name="Участник", value=target.mention)
        embed.add_field(name="Причина", value=reason)
        
        await log_cog.punishments_log_channel.send(embed=embed)

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
        
        user_data = get_user_data(участник.id)
        
        if "moderation" not in user_data:
            user_data["moderation"] = {"warns": []}
        
        warn_data = {
            "moderator_id": interaction.user.id,
            "reason": причина,
            "timestamp": datetime.now().isoformat()
        }
        
        user_data["moderation"]["warns"].append(warn_data)
        save_user_data(участник.id, user_data)
        
        embed = discord.Embed(
            title="✅ Предупреждение выдано",
            description=f"Участник {участник.mention} получил предупреждение.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Причина", value=причина)
        embed.add_field(name="Всего предупреждений", value=len(user_data["moderation"]["warns"]))
        
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
        log_cog = interaction.client.get_cog("ModerationBase")
        if not log_cog or not log_cog.punishments_log_channel:
            return
            
        embed = discord.Embed(
            title=f"Действие модерации: {action.upper()}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Модератор", value=interaction.user.mention)
        embed.add_field(name="Участник", value=target.mention)
        embed.add_field(name="Причина", value=reason)
        
        await log_cog.punishments_log_channel.send(embed=embed)

    @app_commands.command(name="предлист", description="Посмотреть предупреждения участника")
    @app_commands.describe(участник="Участник для проверки")
    async def warns(self, interaction: discord.Interaction, участник: discord.Member):
        user_data = get_user_data(участник.id)
        
        if "moderation" not in user_data or not user_data["moderation"].get("warns"):
            return await interaction.response.send_message(
                f"У {участник.mention} нет предупреждений.",
                ephemeral=True
            )
            
        embed = discord.Embed(
            title=f"Предупреждения {участник.display_name}",
            color=discord.Color.orange()
        )
        
        for i, warn in enumerate(user_data["moderation"]["warns"], 1):
            moderator = await self.bot.fetch_user(warn["moderator_id"])
            timestamp = discord.utils.format_dt(discord.utils.utcfromtimestamp(warn["timestamp"]), "f")
            embed.add_field(
                name=f"Предупреждение #{i}",
                value=f"**Модератор:** {moderator.mention}\n**Причина:** {warn['reason']}\n**Дата:** {timestamp}",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="снятьпред", description="Снять предупреждение с участника")
    @app_commands.describe(участник="Участник для снятия предупреждения", номер="Номер предупреждения для снятия (по умолчанию последнее)")
    @commands.has_permissions(manage_messages=True)
    async def unwarn(self, interaction: discord.Interaction, участник: discord.Member, номер: Optional[int] = None):
        user_data = get_user_data(участник.id)
        
        if "moderation" not in user_data or not user_data["moderation"].get("warns"):
            return await interaction.response.send_message(
                f"У {участник.mention} нет предупреждений.",
                ephemeral=True
            )
            
        warns = user_data["moderation"]["warns"]
        
        if номер is None:
            # Снимаем последнее предупреждение
            removed_warn = warns.pop()
        else:
            # Снимаем конкретное предупреждение
            if номер < 1 or номер > len(warns):
                return await interaction.response.send_message(
                    f"Неверный номер предупреждения. Допустимый диапазон: 1-{len(warns)}",
                    ephemeral=True
                )
            removed_warn = warns.pop(номер - 1)
        
        # Если предупреждений не осталось, удаляем пустой список
        if not warns:
            user_data["moderation"].pop("warns")
            if not user_data["moderation"]:
                user_data.pop("moderation")
        
        save_user_data(участник.id, user_data)
        
        embed = discord.Embed(
            title="✅ Предупреждение снято",
            description=f"С участника {участник.mention} снято предупреждение.",
            color=discord.Color.green()
        )
        embed.add_field(name="Причина", value=removed_warn["reason"])
        embed.add_field(name="Осталось предупреждений", value=len(warns) if "moderation" in user_data and "warns" in user_data["moderation"] else 0)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Отправка уведомления
        embed = discord.Embed(
            title="С вас снято предупреждение",
            description=f"На сервере {interaction.guild.name} с вас снято предупреждение.",
            color=discord.Color.green()
        )
        embed.add_field(name="Модератор", value=interaction.user.mention)
        embed.add_field(name="Причина", value=removed_warn["reason"])
        try:
            await участник.send(embed=embed)
        except:
            pass
        
        # Логирование
        await self.log_punishment(interaction, участник, "снятие предупреждения", removed_warn["reason"])

async def setup(bot):
    await bot.add_cog(ModerationWarns(bot))