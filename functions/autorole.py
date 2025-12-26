import discord
from discord.ext import commands

GUILD_ID = 1339192279470178375
ROLE_ID = 1354454986725003364

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == GUILD_ID:
            role = member.guild.get_role(ROLE_ID)
            if role:
                try:
                    await member.add_roles(role)
                    print(f"[AutoRole] SUCCESS: Assigned role '{role.name}' to {member.name} (ID: {member.id}) in {member.guild.name}")
                except discord.Forbidden:
                    print(f"[AutoRole] ERROR: Missing Permissions to assign role '{role.name}' in {member.guild.name}. Check Bot Role Hierarchy.")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[AutoRole] ERROR: {e}")
            else:
                 print(f"[AutoRole] ERROR: Role ID {ROLE_ID} not found in guild {member.guild.name}")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))
