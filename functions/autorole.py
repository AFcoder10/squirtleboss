import discord
from discord.ext import commands
import json
import os
import traceback

CONFIG_FILE = 'data/autorole_config.json'

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def load_config():
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}

    @staticmethod
    def save_config(config):
        os.makedirs('data', exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = self.load_config()
        guild_id = str(member.guild.id)
        
        if guild_id in config:
            role_id = config[guild_id]
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                    print(f"[AutoRole] SUCCESS: Assigned role '{role.name}' to {member.name} (ID: {member.id}) in {member.guild.name}")
                except discord.Forbidden:
                    print(f"[AutoRole] ERROR: Missing Permissions to assign role '{role.name}' in {member.guild.name}. Check Bot Role Hierarchy.")
                except Exception as e:
                    traceback.print_exc()
                    print(f"[AutoRole] ERROR: {e}")
            else:
                 print(f"[AutoRole] ERROR: Configured Role ID {role_id} not found in guild {member.guild.name}")

    @commands.command(name='autorole')
    @commands.has_permissions(administrator=True)
    async def autorole(self, ctx, role: discord.Role):
        """Sets the role to be automatically assigned to new members."""
        config = self.load_config()
        config[str(ctx.guild.id)] = role.id
        self.save_config(config)
        await ctx.send(f"✅ AutoRole set to {role.name} ({role.id})")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))
