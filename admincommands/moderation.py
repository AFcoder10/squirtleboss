import discord
from discord.ext import commands, tasks
import re
import datetime
import time
import db

def get_connection():
    return db.get_connection()

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_temp_bans.start()

    def cog_unload(self):
        self.check_temp_bans.cancel()

    def parse_time(self, time_str):
        """Parses a time string like 1s, 2m, 3h, 4d into a timedelta."""
        regex = re.compile(r'^(\d+)([smhd])$')
        match = regex.match(time_str)
        
        if not match:
            return None
        
        amount, unit = match.groups()
        amount = int(amount)
        
        if unit == 's':
            return datetime.timedelta(seconds=amount)
        elif unit == 'm':
            return datetime.timedelta(minutes=amount)
        elif unit == 'h':
            return datetime.timedelta(hours=amount)
        elif unit == 'd':
            return datetime.timedelta(days=amount)
        return None

    async def send_dm(self, user, action, guild_name, reason, color):
        try:
            embed = discord.Embed(
                title=f"⚠️ You have been {action}",
                description=f"Server: **{guild_name}**",
                color=color,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await user.send(embed=embed)
            return True
        except discord.Forbidden:
            return False
        except Exception:
            return False

    @tasks.loop(seconds=60)
    async def check_temp_bans(self):
        conn = get_connection()
        if not conn:
            return

        try:
            cur = conn.cursor()
            now = time.time()
            
            # Find expired bans
            cur.execute("SELECT id, user_id, guild_id FROM tempbans WHERE end_time <= %s", (now,))
            expired_bans = cur.fetchall()
            
            for ban_id, user_id, guild_id in expired_bans:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        await guild.unban(user, reason="Temp ban expired")
                        print(f"Unbanned {user} in {guild.name} (Expired)")
                        
                        # Try DMing
                        await self.send_dm(user, "Unbanned (Expired)", guild.name, "Temp ban duration ended.", discord.Color.green())
                    except Exception as e:
                        print(f"Failed to unban user {user_id} in {guild.name}: {e}")
            
            # Delete expired bans
            if expired_bans:
                cur.execute("DELETE FROM tempbans WHERE end_time <= %s", (now,))
                conn.commit()

        except Exception as e:
            print(f"Error checking temp bans: {e}")
        finally:
            conn.close()

    @check_temp_bans.before_loop
    async def before_check_temp_bans(self):
        await self.bot.wait_until_ready()

    @commands.command(name='warn', hidden=True)
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """
        Warns a user via DM.
        Usage: !warn <member> [reason]
        """
        embed = discord.Embed(
            title="⚠️ Warning Received",
            description=f"You have been warned in **{ctx.guild.name}**.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.name, inline=True)
        
        try:
            await member.send(embed=embed)
            await ctx.send(f"✅ sent a warning to {member.mention} for: {reason}")
        except discord.Forbidden:
            await ctx.send(f"❌ Could not DM {member.mention}, but the warning has been noted.")

    @commands.command(name='mute', hidden=True)
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, time_str: str, *, reason: str = "No reason provided"):
        """
        Timeouts (mutes) a user for a specified duration.
        Usage: !mute <member> <time> [reason]
        Example: !mute @User 10m Spamming
        """
        duration = self.parse_time(time_str)
        if not duration:
            await ctx.send("❌ Invalid time format. Use something like `10s`, `1m`, `1h`, `1d`.")
            return
        
        # Max timeout is 28 days for Discord API
        if duration.days > 28:
            await ctx.send("❌ Cannot mute for more than 28 days.")
            return

        try:
            # DM before action
            dm_sent = await self.send_dm(member, "Muted", ctx.guild.name, reason, discord.Color.red())
            
            await member.timeout(duration, reason=reason)
            
            embed = discord.Embed(
                title="🔇 User Muted",
                description=f"{member.mention} has been muted.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Duration", value=time_str, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            if not dm_sent:
                embed.set_footer(text="User could not be DMed.")
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to mute this user.")
        except Exception as e:
            await ctx.send(f"❌ Failed to mute user: {e}")

    @commands.command(name='unmute', hidden=True)
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """
        Removes a timeout from a user.
        Usage: !unmute <member> [reason]
        """
        try:
            # DM before action (or after, doesn't matter much for unmute, but before is consistent)
            dm_sent = await self.send_dm(member, "Unmuted", ctx.guild.name, reason, discord.Color.green())
            
            await member.timeout(None, reason=reason)
            
            embed = discord.Embed(
                title="🔊 User Unmuted",
                description=f"{member.mention} has been unmuted.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            if not dm_sent:
                embed.set_footer(text="User could not be DMed.")
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to unmute this user.")
        except Exception as e:
            await ctx.send(f"❌ Failed to unmute user: {e}")

    @commands.group(name='slowmode', invoke_without_command=True, hidden=True)
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx):
        """
        Base command for slowmode.
        Usage: ?slowmode set <time>
        """
        await ctx.send_help(ctx.command)

    @slowmode.command(name='set')
    @commands.has_permissions(manage_channels=True)
    async def slowmode_set(self, ctx, time_str: str):
        """
        Sets the slowmode delay for the current channel.
        Usage: ?slowmode set <time>
        Example: ?slowmode set 10s
        """
        duration = self.parse_time(time_str)
        if not duration:
            # Handle "0" or "off"
            if time_str.lower() in ["0", "off", "none"]:
                seconds = 0
            else:
                await ctx.send("❌ Invalid time format. Use `10s`, `1m`, `1h` or `0`/`off`.")
                return
        else:
            seconds = int(duration.total_seconds())
        
        # Max slowmode is 6 hours (21600 seconds)
        if seconds > 21600:
            await ctx.send("❌ Slowmode cannot exceed 6 hours.")
            return

        try:
            await ctx.channel.edit(slowmode_delay=seconds)
            if seconds == 0:
                await ctx.send("✅ Slowmode disabled.")
            else:
                await ctx.send(f"✅ Slowmode set to **{time_str}**.")
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to manage this channel.")
        except Exception as e:
            await ctx.send(f"❌ Failed to set slowmode: {e}")

    @commands.command(name='kick', hidden=True)
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """
        Kicks a user from the server.
        Usage: !kick <member> [reason]
        """
        try:
            # DM before action
            dm_sent = await self.send_dm(member, "Kicked", ctx.guild.name, reason, discord.Color.orange())
            
            await member.kick(reason=reason)
            embed = discord.Embed(
                title="👢 User Kicked",
                description=f"{member.mention} has been kicked.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            if not dm_sent:
                embed.set_footer(text="User could not be DMed.")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to kick this user.")
        except Exception as e:
            await ctx.send(f"❌ Failed to kick user: {e}")

    @commands.command(name='ban', hidden=True)
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """
        Bans a user from the server.
        Usage: !ban <member> [reason]
        """
        try:
            # DM before action
            dm_sent = await self.send_dm(member, "Banned", ctx.guild.name, reason, discord.Color.dark_red())
            
            await member.ban(reason=reason)
            embed = discord.Embed(
                title="🔨 User Banned",
                description=f"{member.mention} has been banned.",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            if not dm_sent:
                embed.set_footer(text="User could not be DMed.")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to ban this user.")
        except Exception as e:
            await ctx.send(f"❌ Failed to ban user: {e}")

    @commands.command(name='temp_ban', hidden=True)
    @commands.has_permissions(ban_members=True)
    async def temp_ban(self, ctx, member: discord.Member, time_str: str, *, reason: str = "No reason provided"):
        """
        Temporarily bans a user from the server.
        Usage: !temp_ban <member> <time> [reason]
        Example: !temp_ban @User 7d Toxic behavior
        """
        duration = self.parse_time(time_str)
        if not duration:
            await ctx.send("❌ Invalid time format. Use something like `1d`, `7d`, `24h`.")
            return

        try:
            # DM before action
            dm_sent = await self.send_dm(member, "Temp Banned", ctx.guild.name, f"{reason} (Duration: {time_str})", discord.Color.dark_red())
            
            await member.ban(reason=reason)
            
            # Save to DB
            end_time = time.time() + duration.total_seconds()
            
            conn = get_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO tempbans (user_id, guild_id, end_time) VALUES (%s, %s, %s)", 
                            (member.id, ctx.guild.id, end_time))
                    conn.commit()
                except Exception as db_e:
                     print(f"Error saving temp ban: {db_e}")
                finally:
                    conn.close()

            embed = discord.Embed(
                title="⏳ User Temp Banned",
                description=f"{member.mention} has been temporarily banned.",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Duration", value=time_str, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            if not dm_sent:
                embed.set_footer(text="User could not be DMed.")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to ban this user.")
        except Exception as e:
            await ctx.send(f"❌ Failed to temp ban user: {e}")

    @commands.command(name='unban', hidden=True)
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int, *, reason: str = "No reason provided"):
        """
        Unbans a user by ID.
        Usage: !unban <user_id> [reason]
        """
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=reason)
            
            # Remove from tempbans if exists
            conn = get_connection()
            if conn:
                try:
                   cur = conn.cursor()
                   cur.execute("DELETE FROM tempbans WHERE user_id = %s AND guild_id = %s", (user_id, ctx.guild.id))
                   conn.commit()
                except Exception as db_e:
                    print(f"Error removing temp ban: {db_e}")
                finally:
                    conn.close()
            
            # DM after action (might fail if no shared servers)
            dm_sent = await self.send_dm(user, "Unbanned", ctx.guild.name, reason, discord.Color.green())

            embed = discord.Embed(
                title="🛡️ User Unbanned",
                description=f"{user.mention} (`{user.id}`) has been unbanned.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            if not dm_sent:
                embed.set_footer(text="User could not be DMed.")
            await ctx.send(embed=embed)
        except discord.NotFound:
            await ctx.send("❌ User not found.")
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to unban.")
        except Exception as e:
            await ctx.send(f"❌ Failed to unban user: {e}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
