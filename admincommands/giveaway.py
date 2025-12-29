import discord
from discord.ext import commands, tasks
import asyncio
import random
import time
from datetime import datetime, timedelta
import db
import string

def parse_duration(duration_str):
    time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    unit = duration_str[-1].lower()
    if unit not in time_units:
        return None
    try:
        amount = int(duration_str[:-1])
        return amount * time_units[unit]
    except ValueError:
        return None

def generate_gw_id():
    # Generate a random 6-character string like "GW-X7Z2"
    # Prefix "GW-" + 4 random alphanumeric chars
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=4))
    return f"GW-{suffix}"

class EnterGiveawayView(discord.ui.View):
    def __init__(self, message_id, channel_id):
        super().__init__(timeout=None) # Persistent view
        self.message_id = message_id 
        self.channel_id = channel_id

    @discord.ui.button(label="Enter Giveaway", style=discord.ButtonStyle.green, emoji="🎉", custom_id="enter_giveaway_button")
    async def enter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db.get_connection()
        if not conn:
            await interaction.response.send_message("Database error. Please try again later.", ephemeral=True)
            return

        try:
            with conn.cursor() as cur:
                # Check if giveaway exists and is active
                cur.execute("SELECT status, title, winners, gw_id FROM giveaways WHERE message_id = %s", (self.message_id,))
                gw = cur.fetchone()
                
                if not gw:
                    await interaction.response.send_message("This giveaway no longer exists.", ephemeral=True)
                    return
                
                if gw[0] != 'active':
                    await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
                    return

                user_id = interaction.user.id

                # Check if already entered
                cur.execute("SELECT 1 FROM giveaway_participants WHERE message_id = %s AND user_id = %s", (self.message_id, user_id))
                if cur.fetchone():
                    await interaction.response.send_message("You have already entered this giveaway!", ephemeral=True)
                    return

                # Add participant
                cur.execute("INSERT INTO giveaway_participants (message_id, user_id) VALUES (%s, %s)", (self.message_id, user_id))
                conn.commit()

                # Get count
                cur.execute("SELECT COUNT(*) FROM giveaway_participants WHERE message_id = %s", (self.message_id,))
                count = cur.fetchone()[0]

            # Update embed
            try:
                channel = interaction.guild.get_channel(self.channel_id)
                if channel:
                    msg = await channel.fetch_message(self.message_id)
                    embed = msg.embeds[0]
                    for index, field in enumerate(embed.fields):
                        if field.name == "Entries":
                            embed.set_field_at(index, name="Entries", value=str(count), inline=True)
                            break
                    await msg.edit(embed=embed)
            except Exception as e:
                print(f"Error updating entries count: {e}")

            await interaction.response.send_message("You have successfully entered the giveaway! 🎉", ephemeral=True)
        
        except Exception as e:
            print(f"DB Error in enter_button: {e}")
            await interaction.response.send_message("An error occurred.", ephemeral=True)
        finally:
            conn.close()

class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_db()
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    def setup_db(self):
        conn = db.get_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS giveaways (
                            message_id BIGINT PRIMARY KEY,
                            channel_id BIGINT,
                            guild_id BIGINT,
                            host_id BIGINT,
                            title TEXT,
                            prize TEXT,
                            winners INT,
                            end_time BIGINT,
                            status TEXT,
                            gw_id TEXT UNIQUE
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS giveaway_participants (
                            message_id BIGINT,
                            user_id BIGINT,
                            PRIMARY KEY (message_id, user_id)
                        )
                    """)
                conn.commit()
            except Exception as e:
                print(f"Error setting up giveaway tables: {e}")
            finally:
                conn.close()

    async def cog_load(self):
        # Re-register views
        conn = db.get_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT message_id, channel_id FROM giveaways WHERE status = 'active'")
                    rows = cur.fetchall()
                    for row in rows:
                        self.bot.add_view(EnterGiveawayView(message_id=row[0], channel_id=row[1]))
            except Exception as e:
                print(f"Error loading giveaways on startup: {e}")
            finally:
                conn.close()

    @commands.command(name='create_gw', hidden=True)
    @commands.has_permissions(administrator=True)
    async def create_gw(self, ctx):
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        # 1. Title
        await ctx.send("🎉 **Giveaway Setup**\nPlease enter the **Title** of the giveaway:")
        try:
            title_msg = await self.bot.wait_for('message', check=check, timeout=60)
            title = title_msg.content
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Setup cancelled.")
            return

        # 2. Prize
        await ctx.send(f"Title: **{title}**\nNow, please enter the **Prize**:")
        try:
            prize_msg = await self.bot.wait_for('message', check=check, timeout=60)
            prize = prize_msg.content
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Setup cancelled.")
            return

        # 3. Winners
        await ctx.send(f"Prize: **{prize}**\nHow many **Winners**?")
        try:
            winners_msg = await self.bot.wait_for('message', check=check, timeout=60)
            try:
                winners = int(winners_msg.content)
                if winners < 1: raise ValueError
            except ValueError:
                await ctx.send("Invalid number. Setup cancelled.")
                return
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Setup cancelled.")
            return

        # 4. Duration
        await ctx.send(f"Winners: **{winners}**\nEnter **Duration** (e.g., 10s, 1m, 2h, 1d):")
        try:
            duration_msg = await self.bot.wait_for('message', check=check, timeout=60)
            duration_seconds = parse_duration(duration_msg.content)
            if not duration_seconds:
                await ctx.send("Invalid duration format. Use 1s, 1m, 1h, 1d. Setup cancelled.")
                return
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Setup cancelled.")
            return

        # 5. Channel
        await ctx.send(f"Duration: **{duration_msg.content}**\nFinally, **mention the Channel** where the giveaway should be hosted:")
        try:
            channel_msg = await self.bot.wait_for('message', check=check, timeout=60)
            if not channel_msg.channel_mentions:
                await ctx.send("No channel mentioned. Setup cancelled.")
                return
            target_channel = channel_msg.channel_mentions[0]
        except asyncio.TimeoutError:
            await ctx.send("Timed out. Setup cancelled.")
            return

        gw_id = generate_gw_id()
        end_time = datetime.now() + timedelta(seconds=duration_seconds)
        end_timestamp = int(end_time.timestamp())

        embed = discord.Embed(title=title, description=f"**Prize**: {prize}", color=discord.Color.gold())
        embed.add_field(name="Winners", value=str(winners), inline=True)
        embed.add_field(name="Entries", value="0", inline=True)
        embed.add_field(name="Ends In", value=f"<t:{end_timestamp}:R> (<t:{end_timestamp}:f>)", inline=False)
        embed.add_field(name="Hosted By", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"ID: {gw_id}")
        embed.timestamp = end_time

        try:
            gw_message = await target_channel.send(content="🎉 **GIVEAWAY** 🎉", embed=embed)
            
            conn = db.get_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO giveaways (message_id, channel_id, guild_id, host_id, title, prize, winners, end_time, status, gw_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)
                    """, (gw_message.id, target_channel.id, ctx.guild.id, ctx.author.id, title, prize, winners, end_timestamp, gw_id))
                    conn.commit()
                conn.close()

            # Add View to message
            view = EnterGiveawayView(message_id=gw_message.id, channel_id=target_channel.id)
            await gw_message.edit(view=view)
            
            await ctx.send(f"✅ Giveaway created in {target_channel.mention}! ID: `{gw_id}`")

        except Exception as e:
            await ctx.send(f"Failed to create giveaway: {e}")
            print(f"Error creating giveaway: {e}")

    @commands.command(name='end', hidden=True)
    @commands.has_permissions(administrator=True)
    async def end_cmd(self, ctx, gw_id: str):
        conn = db.get_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT message_id, channel_id, status FROM giveaways WHERE gw_id = %s", (gw_id,))
                gw = cur.fetchone()
                
                if not gw:
                    await ctx.send(f"Giveaway with ID `{gw_id}` not found.")
                    return
                
                if gw[2] != 'active':
                    await ctx.send(f"Giveaway `{gw_id}` has already ended.")
                    return
                
                message_id = gw[0]

                # Mark as ended
                cur.execute("UPDATE giveaways SET status = 'ended' WHERE message_id = %s", (message_id,))
                conn.commit()
                
                await self.end_giveaway(message_id, gw[1])
                await ctx.send(f"Ended giveaway `{gw_id}`.")

        except Exception as e:
            print(f"Error in end command: {e}")
            await ctx.send("An error occurred.")
        finally:
            conn.close()

    @commands.command(name='reroll', hidden=True)
    @commands.has_permissions(administrator=True)
    async def reroll_cmd(self, ctx, gw_id: str):
        conn = db.get_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT message_id, channel_id, prize FROM giveaways WHERE gw_id = %s", (gw_id,))
                gw = cur.fetchone()
                
                if not gw:
                    await ctx.send(f"Giveaway with ID `{gw_id}` not found.")
                    return

                message_id = gw[0]
                channel_id = gw[1]
                prize = gw[2]

                # Get participants
                cur.execute("SELECT user_id FROM giveaway_participants WHERE message_id = %s", (message_id,))
                participants = [row[0] for row in cur.fetchall()]

                if not participants:
                    await ctx.send("No participants to reroll.")
                    return

                winner_id = random.choice(participants)
                channel = self.bot.get_channel(channel_id)
                
                if channel:
                    await channel.send(f"🎉 Reroll! New winner for **{prize}**: <@{winner_id}>!")
                    await ctx.send(f"Rerolled winner for `{gw_id}`.")
                else:
                    await ctx.send(f"Could not find channel to announce reroll.")

        except Exception as e:
            print(f"Error in reroll command: {e}")
        finally:
            conn.close()

    @tasks.loop(seconds=5)
    async def check_giveaways(self):
        conn = db.get_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cur:
                current_time = int(time.time())
                cur.execute("SELECT message_id, channel_id FROM giveaways WHERE status = 'active' AND end_time <= %s", (current_time,))
                ended_giveaways = cur.fetchall()

                for row in ended_giveaways:
                    message_id = row[0]
                    channel_id = row[1]
                    
                    cur.execute("UPDATE giveaways SET status = 'ended' WHERE message_id = %s", (message_id,))
                    await self.end_giveaway(message_id, channel_id)
                
                if ended_giveaways:
                    conn.commit()

        except Exception as e:
            print(f"Error in check_giveaways loop: {e}")
        finally:
            conn.close()

    async def end_giveaway(self, message_id, channel_id):
        conn = db.get_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cur:
                # Fetch details
                cur.execute("SELECT prize, winners FROM giveaways WHERE message_id = %s", (message_id,))
                gw = cur.fetchone()
                if not gw: return
                prize, winners_count = gw

                # Fetch participants
                cur.execute("SELECT user_id FROM giveaway_participants WHERE message_id = %s", (message_id,))
                participants = [row[0] for row in cur.fetchall()]

            channel = self.bot.get_channel(channel_id)
            if not channel: return

            try:
                msg = await channel.fetch_message(message_id)
            except discord.NotFound:
                return

            if not participants:
                winner_text = "No valid entries."
                winners_mentions = []
            else:
                if len(participants) <= winners_count:
                    winners = participants
                else:
                    winners = random.sample(participants, winners_count)
                
                winners_mentions = [f"<@{uid}>" for uid in winners]
                winner_text = ", ".join(winners_mentions)

            # Update Embed
            embed = msg.embeds[0]
            embed.color = discord.Color.greyple()
            embed.description = f"**Giveaway Ended!**\nPrize: {prize}\nWinners: {winner_text}"
            
            # Update View
            await msg.edit(embed=embed, view=None)

            if winners_mentions:
                await channel.send(f"🎉 Congratulations {winner_text}! You won **{prize}**!")
            else:
                await channel.send(f"Giveaway for **{prize}** ended with no entries.")

        except Exception as e:
            print(f"Error ending giveaway {message_id}: {e}")
        finally:
            conn.close()

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))
