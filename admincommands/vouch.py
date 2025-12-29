import discord
from discord.ext import commands
import db
import asyncio
import os

class VouchRequestView(discord.ui.View):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(timeout=None)

    def get_info_from_embed(self, embed):
        if not embed or not embed.description:
            return None, None, None, None, []
        
        import re
        requester_match = re.search(r"Requester:\*\* .* \(`(\d+)`\)", embed.description)
        target_match = re.search(r"Target:\*\* .* \(`(\d+)`\)", embed.description)
        
        requester_id = int(requester_match.group(1)) if requester_match else None
        target_id = int(target_match.group(1)) if target_match else None
        
        action = 'vouch' if 'Vouch' in embed.title else 'unvouch'
        
        reason = "No reason provided"
        proof_urls = []
        
        for field in embed.fields:
            if field.name == "Reason":
                reason = field.value
            elif field.name == "Proof":
                proof_urls = field.value.split('\n')
                
        return requester_id, target_id, action, reason, proof_urls

    async def update_score(self, guild_id, target_id, value):
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
            """, (target_id, value, value))
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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(embed=discord.Embed(description="❌ Only admins can assume this action.", color=discord.Color.red()), ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        requester_id, target_id, action, reason, proof_urls = self.get_info_from_embed(embed)
        
        if not requester_id or not target_id:
            await interaction.response.send_message(embed=discord.Embed(description="❌ Error parsing request data.", color=discord.Color.red()), ephemeral=True)
            return

        value = 1 if action == 'vouch' else -1
        new_score = await self.update_score(interaction.guild_id, target_id, value)
        
        if new_score is None:
            await interaction.response.send_message(embed=discord.Embed(description="Database error processing request.", color=discord.Color.red()), ephemeral=True)
            return

        # Log via Cog method
        target_user = await self.bot.fetch_user(target_id)
        requester = await self.bot.fetch_user(requester_id)
        await Vouches.log_action(self.bot, interaction.guild, target_user, requester, action, new_score, reason, proof_urls, interaction.user)
        
        # Notify Requester
        try:
            await requester.send(embed=discord.Embed(description=f"✅ Your {action} request for user ID {target_id} has been approved.", color=discord.Color.green()))
        except:
            pass

        # Disable buttons
        view = VouchRequestView(self.bot)
        for item in view.children:
            item.disabled = True
        
        await interaction.response.edit_message(content=f"✅ Request APPROVED by {interaction.user.mention}", view=view)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="vouch_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(embed=discord.Embed(description="❌ Only admins can assume this action.", color=discord.Color.red()), ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        requester_id, target_id, action, _, _ = self.get_info_from_embed(embed)

        try:
            user = await self.bot.fetch_user(requester_id)
            await user.send(embed=discord.Embed(description=f"❌ Your {action} request for user ID {target_id} has been denied.", color=discord.Color.red()))
        except:
            pass
            
        view = VouchRequestView(self.bot)
        for item in view.children:
            item.disabled = True
            
        await interaction.response.edit_message(content=f"❌ Request DENIED by {interaction.user.mention}", view=view)

class Vouches(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VouchRequestView(bot))

    def get_config(self, guild_id):
        conn = db.get_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT log_channel, req_channel, vouch_log_channel, unvouch_log_channel FROM vouch_config WHERE guild_id = %s", (guild_id,))
                row = cur.fetchone()
                if row:
                    return {
                        'log_channel': row[0],
                        'req_channel': row[1],
                        'vouch_log_channel': row[2],
                        'unvouch_log_channel': row[3]
                    }
                return {}
        finally:
            conn.close()

    def update_config(self, guild_id, key, value):
        conn = db.get_connection()
        if not conn: return False
        try:
            with conn.cursor() as cur:
                # Upsert
                cur.execute(f"""
                    INSERT INTO vouch_config (guild_id, {key}) 
                    VALUES (%s, %s) 
                    ON CONFLICT (guild_id) 
                    DO UPDATE SET {key} = %s
                """, (guild_id, value, value))
            conn.commit()
            return True
        except Exception as e:
            print(f"DB Error setting vouch config: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    async def log_action(bot, guild, target_user, requester, action, new_score, reason, proof_urls, moderator):
        # We need an instance to access DB, but this is static.
        # Let's just create a quick DB connection here since it's cleaner than passing self everywhere if not available.
        conn = db.get_connection()
        config = {}
        if conn:
            try:
                with conn.cursor() as cur:
                     cur.execute("SELECT log_channel, req_channel, vouch_log_channel, unvouch_log_channel FROM vouch_config WHERE guild_id = %s", (guild.id,))
                     row = cur.fetchone()
                     if row:
                        config = {
                            'log_channel': row[0],
                            'req_channel': row[1],
                            'vouch_log_channel': row[2],
                            'unvouch_log_channel': row[3]
                        }
            finally:
                conn.close()

        # Determine channel key based on action
        channel_id = None
        if action == 'vouch':
            channel_id = config.get('vouch_log_channel')
        elif action == 'unvouch':
            channel_id = config.get('unvouch_log_channel')
        
        if not channel_id:
            channel_id = config.get('log_channel')

        if channel_id:
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

    @commands.command(name='vouch_log', hidden=True)
    @commands.has_permissions(administrator=True)
    async def vouch_log(self, ctx, channel: discord.TextChannel):
        """Sets the log channel for approved VOUCHES."""
        if self.update_config(ctx.guild.id, 'vouch_log_channel', channel.id):
            await ctx.send(f"✅ Vouch logs will be sent to {channel.mention}")
        else:
            await ctx.send("❌ DB Error.")

    @commands.command(name='unvouch_log', hidden=True)
    @commands.has_permissions(administrator=True)
    async def unvouch_log(self, ctx, channel: discord.TextChannel):
        """Sets the log channel for approved UNVOUCHES."""
        if self.update_config(ctx.guild.id, 'unvouch_log_channel', channel.id):
            await ctx.send(f"✅ Unvouch logs will be sent to {channel.mention}")
        else:
            await ctx.send("❌ DB Error.")

    @commands.command(name='vouch')
    async def vouch(self, ctx, user: discord.User):
        if ctx.author.guild_permissions.administrator:
            conn = db.get_connection()
            if not conn:
                await ctx.send(embed=discord.Embed(description="❌ Database Error.", color=discord.Color.red()))
                return
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO vouches (user_id, score) VALUES (%s, 1) ON CONFLICT (user_id) DO UPDATE SET score = vouches.score + 1 RETURNING score", (user.id,))
                new_score = cur.fetchone()[0]
                conn.commit()
                
                await ctx.send(embed=discord.Embed(title="✅ User Vouched", description=f"Vouched for {user.mention}. Score: **{new_score}**", color=discord.Color.green()))
                await self.log_action(self.bot, ctx.guild, user, ctx.author, 'vouch', new_score, "Admin Command Usage", [], ctx.author)
            finally:
                conn.close()
        else:
            await self.handle_request_flow(ctx, user, 'req_channel', 'vouch')

    @commands.command(name='unvouch')
    async def unvouch(self, ctx, user: discord.User):
        if ctx.author.guild_permissions.administrator:
            conn = db.get_connection()
            if not conn:
                await ctx.send(embed=discord.Embed(description="❌ Database Error.", color=discord.Color.red()))
                return
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO vouches (user_id, score) VALUES (%s, -1) ON CONFLICT (user_id) DO UPDATE SET score = vouches.score - 1 RETURNING score", (user.id,))
                new_score = cur.fetchone()[0]
                conn.commit()
                
                await ctx.send(embed=discord.Embed(title="🔻 User Unvouched", description=f"Unvouched {user.mention}. Score: **{new_score}**", color=discord.Color.red()))
                await self.log_action(self.bot, ctx.guild, user, ctx.author, 'unvouch', new_score, "Admin Command Usage", [], ctx.author)
            finally:
                conn.close()
        else:
            await self.handle_request_flow(ctx, user, 'req_channel', 'unvouch')

    @commands.command(name='vouch_status', aliases=['v_st'])
    async def vouch_status(self, ctx, user: discord.User = None):
        if user is None: user = ctx.author
        conn = db.get_connection()
        if not conn: return
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT score FROM vouches WHERE user_id = %s", (user.id,))
                row = cur.fetchone()
                score = row[0] if row else 0
                color = discord.Color.green() if score > 0 else discord.Color.red() if score < 0 else discord.Color.blue()
                embed = discord.Embed(title="Vouch Status", description=f"{user.mention} has **{score}** vouches.", color=color)
                embed.set_thumbnail(url=user.display_avatar.url)
                await ctx.send(embed=embed)
        finally:
            conn.close()

    async def handle_request_flow(self, ctx, target_user, link_channel_key, action_name):
        if target_user.id == ctx.author.id:
            await ctx.send(embed=discord.Embed(description="❌ You cannot request a vouch/unvouch for yourself.", color=discord.Color.red()), delete_after=3)
            return

        config = self.get_config(ctx.guild.id) or {}
        if link_channel_key not in config or not config[link_channel_key]:
            await ctx.send(embed=discord.Embed(description="❌ Request channel not configured.", color=discord.Color.red()), delete_after=3)
            return

        req_channel = ctx.guild.get_channel(config[link_channel_key])
        if not req_channel:
            await ctx.send(embed=discord.Embed(description="❌ Request channel invalid.", color=discord.Color.red()), delete_after=3)
            return

        try:
            dm = await ctx.author.create_dm()
            await dm.send(embed=discord.Embed(description=f"You initiated a **{action_name}** request for **{target_user.name}**.\nReply with REASON and PROOF.\nType `done` when finished.", color=discord.Color.blue()))
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(description="❌ I cannot DM you.", color=discord.Color.red()), delete_after=3)
            return

        await ctx.send(embed=discord.Embed(description=f"📩 Check your DMs.", color=discord.Color.blue()))

        evidence_msgs = []
        proof_urls = []
        
        def check(m): return m.author == ctx.author and m.channel == dm

        while True:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=300)
                if msg.content.lower() == 'done':
                    if not evidence_msgs and not proof_urls:
                        await dm.send(embed=discord.Embed(description="Request cancelled.", color=discord.Color.red()))
                        return
                    break
                if msg.content: evidence_msgs.append(msg.content)
                for att in msg.attachments: proof_urls.append(att.url)
                await msg.add_reaction('✅')
            except asyncio.TimeoutError:
                await dm.send(embed=discord.Embed(description="Timed out.", color=discord.Color.red()))
                return

        reason_text = "\n".join(evidence_msgs) if evidence_msgs else "No text provided"
        
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
        
        view = VouchRequestView(self.bot)
        await req_channel.send(embed=embed, view=view)
        await dm.send(embed=discord.Embed(description="✅ Request submitted successfully!", color=discord.Color.green()))

    @commands.command(name='vouch_req_log', hidden=True)
    @commands.has_permissions(administrator=True)
    async def vouch_req_log(self, ctx, channel: discord.TextChannel):
        """Sets the channel where vouch/unvouch REQUESTS will be sent."""
        if self.update_config(ctx.guild.id, 'req_channel', channel.id):
             await ctx.send(f"✅ Vouch/Unvouch requests will be sent to {channel.mention}")
        else:
            await ctx.send("❌ DB Error.")

async def setup(bot):
    await bot.add_cog(Vouches(bot))
