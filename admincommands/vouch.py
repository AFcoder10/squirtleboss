import discord
from discord.ext import commands
import db
import json
import os
import asyncio

CONFIG_FILE = 'data/vouch_config.json'

class VouchRequestView(discord.ui.View):
    def __init__(self, bot, user_id, target_id, action, reason, proof_urls):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.target_id = target_id
        self.action = action # 'vouch' or 'unvouch'
        self.reason = reason
        self.proof_urls = proof_urls

    async def update_score(self, guild_id, value):
        conn = db.get_connection()
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO vouches (user_id, score) 
                VALUES (%s, %s) 
                ON CONFLICT (user_id) 
                DO UPDATE SET score = vouches.score + %s 
                RETURNING score
            """, (self.target_id, value, value))
            new_score = cur.fetchone()[0]
            conn.commit()
            return new_score
        except Exception as e:
            print(f"DB Error: {e}")
            return None
        finally:
            conn.close()

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="vouch_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        value = 1 if self.action == 'vouch' else -1
        new_score = await self.update_score(interaction.guild_id, value)
        
        if new_score is None:
            await interaction.response.send_message("Database error processing request.", ephemeral=True)
            return

        # Log via Cog method
        target_user = await self.bot.fetch_user(self.target_id)
        requester = await self.bot.fetch_user(self.user_id)
        await Vouches.log_action(self.bot, interaction.guild, target_user, requester, self.action, new_score, self.reason, self.proof_urls, interaction.user)
        
        # Notify Requester
        try:
            await requester.send(f"✅ Your {self.action} request for user ID {self.target_id} has been approved.")
        except:
            pass

        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(content=f"✅ Request APPROVED by {interaction.user.mention}", view=self)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="vouch_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Notify Requester
        try:
            user = await self.bot.fetch_user(self.user_id)
            await user.send(f"❌ Your {self.action} request for user ID {self.target_id} has been denied.")
        except:
            pass
            
        # Disable buttons
        for item in self.children:
            item.disabled = True
            
        await interaction.response.edit_message(content=f"❌ Request DENIED by {interaction.user.mention}", view=self)

class Vouches(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_connection(self):
        return db.get_connection()

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

    @staticmethod
    async def log_action(bot, guild, target_user, requester, action, new_score, reason, proof_urls, moderator):
        config = Vouches.load_config()
        guild_id_str = str(guild.id)
        if guild_id_str in config and 'log_channel' in config[guild_id_str]:
            channel_id = config[guild_id_str]['log_channel']
            channel = guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="Vouch Action Log",
                    description=f"**Action:** {action.capitalize()}\n**Target:** {target_user.mention}\n**Requester:** {requester.mention}\n**New Score:** {new_score}",
                    color=discord.Color.green() if action == 'vouch' else discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"Approved/Executed by {moderator.display_name}")
                if proof_urls:
                    embed.add_field(name="Proof", value="\n".join(proof_urls), inline=False)
                    if proof_urls[0].lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        embed.set_image(url=proof_urls[0])
                
                await channel.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def vouch_log(self, ctx, channel: discord.TextChannel):
        """Sets the log channel for approved vouches."""
        config = self.load_config()
        guild_id = str(ctx.guild.id)
        
        if guild_id not in config:
            config[guild_id] = {}
        
        config[guild_id]['log_channel'] = channel.id
        self.save_config(config)
        await ctx.send(f"✅ Vouch logs will be sent to {channel.mention}")

    @commands.command(name='vouch')
    @commands.has_permissions(administrator=True)
    async def vouch(self, ctx, user: discord.User):
        """Vouches for a user (Admin)."""
        conn = self.get_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO vouches (user_id, score) VALUES (%s, 1) ON CONFLICT (user_id) DO UPDATE SET score = vouches.score + 1 RETURNING score", (user.id,))
            new_score = cur.fetchone()[0]
            conn.commit()
            
            await ctx.send(embed=discord.Embed(title="✅ User Vouched", description=f"Vouched for {user.mention}. Score: **{new_score}**", color=discord.Color.green()))
            
            # Log it
            await self.log_action(self.bot, ctx.guild, user, ctx.author, 'vouch', new_score, "Admin Command Usage", [], ctx.author)
            
        except Exception as e:
            await ctx.send(f"Error: {e}", delete_after=3)
        finally:
            conn.close()

    @commands.command(name='unvouch')
    @commands.has_permissions(administrator=True)
    async def unvouch(self, ctx, user: discord.User):
        """Unvouches a user (Admin)."""
        conn = self.get_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO vouches (user_id, score) VALUES (%s, -1) ON CONFLICT (user_id) DO UPDATE SET score = vouches.score - 1 RETURNING score", (user.id,))
            new_score = cur.fetchone()[0]
            conn.commit()
            
            await ctx.send(embed=discord.Embed(title="🔻 User Unvouched", description=f"Unvouched {user.mention}. Score: **{new_score}**", color=discord.Color.red()))
            
            # Log it
            await self.log_action(self.bot, ctx.guild, user, ctx.author, 'unvouch', new_score, "Admin Command Usage", [], ctx.author)

        except Exception as e:
            await ctx.send(f"Error: {e}", delete_after=3)
        finally:
            conn.close()

    @commands.command(name='vouch_status', aliases=['v_st'])
    async def vouch_status(self, ctx, user: discord.User = None):
        """Check vouch score."""
        if user is None: user = ctx.author
        conn = self.get_connection()
        if not conn: return
        try:
            cur = conn.cursor()
            cur.execute("SELECT score FROM vouches WHERE user_id = %s", (user.id,))
            row = cur.fetchone()
            score = row[0] if row else 0
            color = discord.Color.green() if score > 0 else discord.Color.red() if score < 0 else discord.Color.blue()
            embed = discord.Embed(title="Vouch Status", description=f"{user.mention} has **{score}** vouches.", color=color)
            embed.set_thumbnail(url=user.display_avatar.url)
            await ctx.send(embed=embed)
        except Exception:
            pass
        finally:
            conn.close()

    async def handle_request_flow(self, ctx, target_user, link_channel_key, action_name):
        # 1. Check if self
        if target_user.id == ctx.author.id:
            await ctx.send("❌ You cannot request a vouch/unvouch for yourself.", delete_after=3)
            return

        # 2. Check config
        config = self.load_config()
        guild_id = str(ctx.guild.id)
        if guild_id not in config or link_channel_key not in config[guild_id]:
            await ctx.send("❌ Request channel not configured. Ask an admin to set it up.", delete_after=3)
            return

        req_channel_id = config[guild_id][link_channel_key]
        req_channel = ctx.guild.get_channel(req_channel_id)
        if not req_channel:
            await ctx.send("❌ Request channel configuration is invalid.", delete_after=3)
            return

        # 3. Start DM Sequence
        try:
            dm = await ctx.author.create_dm()
            await dm.send(f"You initiated a **{action_name}** request for **{target_user.name}** (`{target_user.id}`).\n\nPlease reply with your **REASON** and upload any **PROOF** (screenshots, etc.).\n\nType `done` when you are finished sending materials.")
        except discord.Forbidden:
            await ctx.send("❌ I cannot DM you. Please enable DMs.", delete_after=3)
            return

        await ctx.send(f"📩 Check your DMs to complete the request.")

        # 4. Collect Evidence
        evidence_msgs = []
        proof_urls = []
        
        def check(m):
            return m.author == ctx.author and m.channel == dm

        while True:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=300) # 5 mins
                if msg.content.lower() == 'done':
                    if not evidence_msgs and not proof_urls:
                        await dm.send("You haven't provided any info! Request cancelled.")
                        return
                    break
                
                if msg.content:
                    evidence_msgs.append(msg.content)
                for att in msg.attachments:
                    proof_urls.append(att.url)
                
                await msg.add_reaction('✅')
            except asyncio.TimeoutError:
                await dm.send("Time out. Request cancelled.")
                return

        reason_text = "\n".join(evidence_msgs) if evidence_msgs else "No text provided"
        
        # 5. Send to Admin Channel
        embed = discord.Embed(
            title=f"New {action_name.capitalize()} Request",
            description=f"**Requester:** {ctx.author.mention} (`{ctx.author.id}`)\n**Target:** {target_user.mention} (`{target_user.id}`)",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Reason", value=reason_text, inline=False)
        if proof_urls:
             embed.add_field(name="Proof", value="\n".join(proof_urls), inline=False)
             if proof_urls[0].lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                embed.set_image(url=proof_urls[0])
        
        view = VouchRequestView(self.bot, ctx.author.id, target_user.id, action_name, reason_text, proof_urls)
        await req_channel.send(embed=embed, view=view)
        await dm.send("✅ Request submitted successfully!")

    @commands.command(name='vouch_req')
    async def vouch_req(self, ctx, target):
        """
        Request a vouch for a user OR set the request channel (Admin).
        Usage: 
         - User: ?vouch_req @User
         - Admin: ?vouch_req #channel
        """
        # Try converting to Member
        try:
            target_user = await commands.MemberConverter().convert(ctx, target)
            await self.handle_request_flow(ctx, target_user, 'req_channel', 'vouch')
            return
        except commands.MemberNotFound:
            pass # Not a member
        
        # Try converting to Channel (Admin Config)
        if ctx.author.guild_permissions.administrator:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, target)
                config = self.load_config()
                guild_id = str(ctx.guild.id)
                if guild_id not in config: config[guild_id] = {}
                config[guild_id]['req_channel'] = channel.id
                self.save_config(config)
                await ctx.send(f"✅ Vouch/Unvouch requests will be sent to {channel.mention}")
                return
            except commands.ChannelNotFound:
                pass
        
        await ctx.send("Invalid usage. @Mention a user to request, or #Channel to configure (Admin only).", delete_after=3)

    @commands.command(name='unvouch_req')
    async def unvouch_req(self, ctx, target):
        """
        Request an unvouch for a user OR set the request channel (Admin).
        Usage: 
         - User: ?unvouch_req @User
         - Admin: ?unvouch_req #channel
        """
        # Try converting to Member
        try:
            target_user = await commands.MemberConverter().convert(ctx, target)
            await self.handle_request_flow(ctx, target_user, 'req_channel', 'unvouch')
            return
        except commands.MemberNotFound:
            pass
        
        # Try converting to Channel (Admin Config)
        if ctx.author.guild_permissions.administrator:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, target)
                config = self.load_config()
                guild_id = str(ctx.guild.id)
                if guild_id not in config: config[guild_id] = {}
                config[guild_id]['req_channel'] = channel.id
                self.save_config(config)
                await ctx.send(f"✅ Vouch/Unvouch requests will be sent to {channel.mention}")
                return
            except commands.ChannelNotFound:
                pass

        await ctx.send("Invalid usage. @Mention a user to request, or #Channel to configure (Admin only).", delete_after=3)

async def setup(bot):
    await bot.add_cog(Vouches(bot))
