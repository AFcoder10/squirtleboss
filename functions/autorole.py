import discord
from discord.ext import commands
import traceback
import db

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_role_id(self, guild_id):
        conn = db.get_connection()
        if not conn:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT role_id FROM autoroles WHERE guild_id = %s", (guild_id,))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as e:
            print(f"DB Error getting autorole: {e}")
            return None
        finally:
            conn.close()

    def set_role_id(self, guild_id, role_id):
        conn = db.get_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO autoroles (guild_id, role_id) 
                    VALUES (%s, %s) 
                    ON CONFLICT (guild_id) 
                    DO UPDATE SET role_id = %s
                """, (guild_id, role_id, role_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"DB Error setting autorole: {e}")
            return False
        finally:
            conn.close()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        role_id = self.get_role_id(member.guild.id)
        
        if role_id:
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

    @commands.command(name='autorole', hidden=True)
    @commands.has_permissions(administrator=True)
    async def autorole(self, ctx, role: discord.Role):
        """Sets the role to be automatically assigned to new members."""
        success = self.set_role_id(ctx.guild.id, role.id)
        if success:
            await ctx.send(f"✅ AutoRole set to {role.name} ({role.id})")
        else:
            await ctx.send("❌ Failed to save to database.")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))
