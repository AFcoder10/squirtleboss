import discord
from discord.ext import commands
import json
import os

TICKET_FILE = 'tickets.json'
TICKET_INFO_FILE = 'ticketinfo.json'
SUPPORT_ROLE_ID = 1346473296866312224

def load_tickets_config():
    if not os.path.exists(TICKET_FILE):
        return {}
    with open(TICKET_FILE, 'r') as f:
        return json.load(f)

def save_tickets_config(data):
    with open(TICKET_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_ticket_info():
    if not os.path.exists(TICKET_INFO_FILE):
        return {"active_tickets": {}}
    try:
        with open(TICKET_INFO_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"active_tickets": {}}

def save_ticket_info(data):
    with open(TICKET_INFO_FILE, 'w') as f:
        json.dump(data, f, indent=4)

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
            
        # Check active tickets in ticketinfo.json
        info = load_ticket_info()
        user_id = str(interaction.user.id)
        active_tickets = info.get("active_tickets", {})
        
        if user_id in active_tickets:
            existing_channel_id = active_tickets[user_id]
            existing_channel = interaction.guild.get_channel(existing_channel_id)
            
            if existing_channel:
                await interaction.response.send_message(f"❌ You already have an open ticket: {existing_channel.mention}", ephemeral=True)
                return
            else:
                # Channel deleted manually? cleanup
                del active_tickets[user_id]
                save_ticket_info(info)

        # Permissions
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add support role
        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            channel_name = f"ticket-{interaction.user.name}"
            ticket_channel = await interaction.guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
            
            # Update ticketinfo.json BEFORE sending messages to ensure state is saved
            info = load_ticket_info() # Reload to be safe
            info.setdefault("active_tickets", {})[str(interaction.user.id)] = ticket_channel.id
            save_ticket_info(info)

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


def cleanup_ticket(channel_id):
    info = load_ticket_info()
    active_tickets = info.get("active_tickets", {})
    
    # Find user by channel_id
    user_id_to_remove = None
    for uid, cid in active_tickets.items():
        if cid == channel_id:
            user_id_to_remove = uid
            break
    
    if user_id_to_remove:
        del active_tickets[user_id_to_remove]
        save_ticket_info(info)

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

        import asyncio
        await asyncio.sleep(5)
        
        cleanup_ticket(interaction.channel.id)

        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}: {reason_text}")


class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket:close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Validate that this is a registered ticket
        info = load_ticket_info()
        active_tickets = info.get("active_tickets", {})
        search_id = interaction.channel.id
        is_ticket = any(ticket_id == search_id for ticket_id in active_tickets.values())
        
        if not is_ticket:
            await interaction.response.send_message("❌ This channel is not in the ticket database. I cannot close it via this button.", ephemeral=True)
            return

        await interaction.response.send_modal(TicketCloseModal())


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='set_ticket_category')
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

    @commands.command(name='set_ticketlog_channel')
    @commands.has_permissions(administrator=True)
    async def set_ticketlog_channel(self, ctx, channel: discord.TextChannel):
        """
        Sets the channel where ticket logs will be sent. (Admin only)
        Usage: !set_ticketlog_channel <channel>
        """
        data = load_tickets_config()
        data["log_channel_id"] = channel.id
        save_tickets_config(data)
        await ctx.send(f"✅ Ticket log channel set to: {channel.mention}")

    @commands.command(name='create_ticket')
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

    @commands.command(name='close_ticket')
    @commands.has_permissions(administrator=True)
    async def close_ticket_cmd(self, ctx, *, reason: str = "No reason provided"):
        """
        Closes the current ticket channel. (Admin only)
        Usage: !close_ticket [reason]
        """
        # Validate that this is a registered ticket
        info = load_ticket_info()
        active_tickets = info.get("active_tickets", {})
        
        # Check if current channel ID is in the values of active_tickets
        search_id = ctx.channel.id
        is_ticket = any(ticket_id == search_id for ticket_id in active_tickets.values())
        
        if not is_ticket:
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

        import asyncio
        await asyncio.sleep(5)
        
        cleanup_ticket(ctx.channel.id)

        await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}: {reason}")

async def setup(bot):
    bot.add_view(TicketLauncher())
    bot.add_view(TicketControls())
    await bot.add_cog(Tickets(bot))
