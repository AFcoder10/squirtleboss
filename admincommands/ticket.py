import discord
from discord.ext import commands
import db
import asyncio

# Helper to get DB connection
def get_connection():
    return db.get_connection()

def load_tickets_config():
    conn = get_connection()
    if not conn:
        return {}
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT category_id, log_channel_id, support_role_id FROM ticket_config WHERE uniq_id = 1")
        row = cur.fetchone()
        if row:
            return {
                "category_id": row[0],
                "log_channel_id": row[1],
                "support_role_id": row[2]
            }
        return {}
    except Exception as e:
        print(f"Error loading ticket config: {e}")
        return {}
    finally:
        conn.close()

def save_tickets_config(data):
    # This function is now slightly different, we update individual fields or upsert
    conn = get_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ticket_config (uniq_id, category_id, log_channel_id, support_role_id)
            VALUES (1, %s, %s, %s)
            ON CONFLICT (uniq_id) DO UPDATE SET
                category_id = EXCLUDED.category_id,
                log_channel_id = EXCLUDED.log_channel_id,
                support_role_id = EXCLUDED.support_role_id
        """, (
            data.get("category_id"),
            data.get("log_channel_id"),
            data.get("support_role_id")
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving ticket config: {e}")
    finally:
        conn.close()

def get_active_ticket(user_id):
    conn = get_connection()
    if not conn:
        return None
        
    try:
        cur = conn.cursor()
        cur.execute("SELECT channel_id FROM active_tickets WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting active ticket: {e}")
        return None
    finally:
        conn.close()

def add_active_ticket(user_id, channel_id):
    conn = get_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO active_tickets (user_id, channel_id) VALUES (%s, %s)", (user_id, channel_id))
        conn.commit()
    except Exception as e:
        print(f"Error adding active ticket: {e}")
    finally:
        conn.close()

def remove_active_ticket(channel_id):
    conn = get_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM active_tickets WHERE channel_id = %s", (channel_id,))
        conn.commit()
    except Exception as e:
        print(f"Error removing active ticket: {e}")
    finally:
        conn.close()

def is_channel_ticket(channel_id):
    conn = get_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM active_tickets WHERE channel_id = %s", (channel_id,))
        return cur.fetchone() is not None
    except Exception as e:
        print(f"Error checking ticket channel: {e}")
        return False
    finally:
        conn.close()

async def log_ticket_event(guild, title, description, color, fields=None):
    config = load_tickets_config()
    log_channel_id = config.get("log_channel_id")
    if not log_channel_id:
        return
    
    log_channel = guild.get_channel(log_channel_id)
    if not log_channel:
        return

    embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
            
    await log_channel.send(embed=embed)

class TicketLauncher(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.green, custom_id="ticket:create", emoji="🎫")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_tickets_config()
        category_id = config.get("category_id")

        if not category_id:
            await interaction.response.send_message("❌ Ticket category not set. Please contact an admin.", ephemeral=True)
            return

        category = interaction.guild.get_channel(category_id)
        if not category:
            await interaction.response.send_message("❌ Ticket category not found. Please contact an admin.", ephemeral=True)
            return
            
        # Check active tickets
        existing_channel_id = get_active_ticket(interaction.user.id)
        
        if existing_channel_id:
            existing_channel = interaction.guild.get_channel(existing_channel_id)
            
            if existing_channel:
                await interaction.response.send_message(f"❌ You already have an open ticket: {existing_channel.mention}", ephemeral=True)
                return
            else:
                # Channel deleted manually? cleanup based on user id isn't direct in DB with helper, but add_active_ticket will fail if PK exists?
                # Actually, if existing_channel is None, it means the channel is gone.
                # But get_active_ticket returned an ID. So we should remove it.
                # We need a remove by user_id or handle it. 
                # Let's add that helper to be safe or just use raw delete here?
                # For cleaner code, assume remove_active_ticket only takes channel_id as per API above.
                # We can't remove by user_id with current helper.
                # Let's just try to create and cleaner logic:
                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM active_tickets WHERE user_id = %s", (interaction.user.id,))
                    conn.commit()
                except:
                    pass
                finally:
                    if conn: conn.close()

        # Permissions
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add support role
        support_role_id = config.get("support_role_id")
        support_role = None
        if support_role_id:
            support_role = interaction.guild.get_role(support_role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            channel_name = f"ticket-{interaction.user.name}"
            ticket_channel = await interaction.guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
            
            # Save to DB
            add_active_ticket(interaction.user.id, ticket_channel.id)

            embed = discord.Embed(
                title="🎫 Support Ticket",
                description=f"Welcome {interaction.user.mention}!\nSupport will be with you shortly.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Click the button below to close this ticket.")
            
            # Message outside embed
            mentions = [interaction.user.mention]
            if support_role:
                mentions.append(support_role.mention)
            
            await ticket_channel.send(content=" ".join(mentions), embed=embed, view=TicketControls())
            
            await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

            # Log creation
            await log_ticket_event(
                interaction.guild,
                "Ticket Created",
                f"Ticket created by {interaction.user.mention}",
                discord.Color.green(),
                [("User", f"{interaction.user} (`{interaction.user.id}`)", True),
                 ("Channel", ticket_channel.mention, True)]
            )
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create ticket: {e}", ephemeral=True)


class TicketCloseModal(discord.ui.Modal, title="Close Ticket"):
    reason = discord.ui.TextInput(
        label="Reason for closing",
        style=discord.TextStyle.paragraph,
        placeholder="Issue resolved, etc...",
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        reason_text = self.reason.value or 'No reason provided'
        await interaction.response.send_message(f"🔒 Ticket closing in 5 seconds...\nReason: {reason_text}")
        
        # Log closure
        await log_ticket_event(
            interaction.guild,
            "Ticket Closed",
            f"Ticket closed by {interaction.user.mention}",
            discord.Color.red(),
            [("User", f"{interaction.user} (`{interaction.user.id}`)", True),
             ("Channel", interaction.channel.name, True),
             ("Reason", reason_text, False)]
        )

        await asyncio.sleep(5)
        
        remove_active_ticket(interaction.channel.id)

        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}: {reason_text}")


class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket:close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Validate that this is a registered ticket
        if not is_channel_ticket(interaction.channel.id):
            await interaction.response.send_message("❌ This channel is not in the ticket database. I cannot close it via this button.", ephemeral=True)
            return

        await interaction.response.send_modal(TicketCloseModal())


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='set_ticket_category', hidden=True)
    @commands.has_permissions(administrator=True)
    async def set_ticket_category(self, ctx, category: discord.CategoryChannel):
        """
        Sets the category where tickets will be created. (Admin only)
        Usage: !set_ticket_category <category_id_or_name>
        """
        data = load_tickets_config()
        data["category_id"] = category.id
        save_tickets_config(data)
        await ctx.send(f"✅ Ticket category set to: {category.name}")

    @commands.command(name='set_ticketlog_channel', hidden=True)
    @commands.has_permissions(administrator=True)
    async def set_ticketlog_channel(self, ctx, channel: discord.TextChannel):
        """
        Sets the channel where ticket logs will be sent. (Admin only)
        Usage: ?set_ticketlog_channel <channel>
        """
        data = load_tickets_config()
        data["log_channel_id"] = channel.id
        save_tickets_config(data)
        await ctx.send(f"✅ Ticket log channel set to: {channel.mention}")

    @commands.command(name='set_support_role', hidden=True)
    @commands.has_permissions(administrator=True)
    async def set_support_role(self, ctx, role: discord.Role):
        """
        Sets the support role that can access tickets. (Admin only)
        Usage: ?set_support_role <role>
        """
        data = load_tickets_config()
        data["support_role_id"] = role.id
        save_tickets_config(data)
        await ctx.send(f"✅ Support role set to: {role.name}")

    @commands.command(name='create_ticket', hidden=True)
    @commands.has_permissions(administrator=True)
    async def create_ticket(self, ctx):
        """
        Sends the 'Create Ticket' panel. (Admin only)
        Usage: !create_ticket
        """
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Need help? Click the button below to create a ticket.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=TicketLauncher())

    @commands.command(name='close_ticket', hidden=True)
    @commands.has_permissions(administrator=True)
    async def close_ticket_cmd(self, ctx, *, reason: str = "No reason provided"):
        """
        Closes the current ticket channel. (Admin only)
        Usage: !close_ticket [reason]
        """
        # Validate that this is a registered ticket
        if not is_channel_ticket(ctx.channel.id):
            await ctx.send("❌ This channel is not a registered ticket. I cannot close it.")
            return

        await ctx.send(f"🔒 Ticket closing in 5 seconds...\nReason: {reason}")
        
        # Log closure
        await log_ticket_event(
            ctx.guild,
            "Ticket Closed",
            f"Ticket closed by {ctx.author.mention}",
            discord.Color.red(),
            [("User", f"{ctx.author} (`{ctx.author.id}`)", True),
             ("Channel", ctx.channel.name, True),
             ("Reason", reason, False)]
        )

        await asyncio.sleep(5)
        
        remove_active_ticket(ctx.channel.id)

        await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}: {reason}")

async def setup(bot):
    bot.add_view(TicketLauncher())
    bot.add_view(TicketControls())
    await bot.add_cog(Tickets(bot))
