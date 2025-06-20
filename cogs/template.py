import discord
from discord import app_commands
from discord.ext import commands
import importlib.util
import os
import sys

class Template(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.templates = {
            "анкета": "survey_template"
        }

    @app_commands.command(name="шаблон", description="Вызвать шаблонное сообщение")
    @app_commands.describe(имя="Название шаблона (например, анкета)")
    async def шаблон(self, interaction: discord.Interaction, имя: str):
        if имя not in self.templates:
            await interaction.response.send_message("❌ Такого шаблона не существует.", ephemeral=True)
            return

        template_name = self.templates[имя]
        
        # Абсолютный путь к файлу шаблона
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", f"{template_name}.py")
        template_path = os.path.normpath(template_path)

        if not os.path.exists(template_path):
            await interaction.response.send_message(f"❌ Файл шаблона не найден по пути: {template_path}", ephemeral=True)
            return

        try:
            # Динамическая загрузка модуля
            spec = importlib.util.spec_from_file_location(template_name, template_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[template_name] = module
            spec.loader.exec_module(module)
            
            embed, view = module.get_template()
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка загрузки шаблона: {type(e).__name__} - {str(e)}", ephemeral=True)

    @шаблон.autocomplete("имя")
    async def шаблон_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=name, value=name)
            for name in self.templates
            if current.lower() in name.lower()
        ]

async def setup(bot):
    await bot.add_cog(Template(bot))