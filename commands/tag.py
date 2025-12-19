import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from utils.tagsearch import search_tags

TAGS_FILE = 'tags.json'

class TagPaginationView(discord.ui.View):
    def __init__(self, ctx, data, title, per_page=15):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.data = data
        self.title = title
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(data) + per_page - 1) // per_page)
        
        # Disable buttons if only 1 page
        if self.total_pages <= 1:
            self.previous_page.disabled = True
            self.next_page.disabled = True

    def get_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        subset = self.data[start:end]
        
        embed = discord.Embed(title=f"{self.title}", color=discord.Color.blue())
        if self.total_pages > 1:
            embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • Total: {len(self.data)}")
        else:
             embed.set_footer(text=f"Total: {len(self.data)}")
             
        if not subset:
            embed.description = "No tags found."
        else:
            embed.description = "\n".join(subset)
            
        return embed

    @discord.ui.button(label="<", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label=">", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()
            
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This menu is controlled by the command author.", ephemeral=True)
            return False
        return True
        
    async def on_timeout(self):
        # Disable buttons on timeout
        for item in self.children:
            item.disabled = True
        try:
             # We can't edit the message easily without reference, but Views are attached to message.
             # self.message is set if view is sent with it? No, we need to save it.
             # Actually, simpler is just letting it stop working silently or saving message on send.
             pass
        except:
            pass

class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tags = self.load_tags()

    def load_tags(self):
        if not os.path.exists(TAGS_FILE):
            return {}
        try:
            with open(TAGS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def save_tags(self):
        with open(TAGS_FILE, 'w') as f:
            json.dump(self.tags, f, indent=4)

    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, name: str = None):
        """
        Tag management system.
        Usage: !tag <name> to view a tag.
        Subcommands: create, list, delete, search, raw, info, adelete.
        """
        if name is None:
            embed = discord.Embed(title="Tag Help", color=discord.Color.blue())
            embed.add_field(name="Commands", value="`create`, `list`, `delete`, `search`, `raw`, `info`, `adelete`")
            embed.add_field(name="Usage", value="`!tag <name>` to view a tag.")
            await ctx.send(embed=embed)
            return

        if name in self.tags:
            # Plain text as requested
            await ctx.send(self.tags[name]['content'])
        else:
            matches = search_tags(self.tags, name)
            if matches:
                 # Minimal embed for suggestion? Or text? 
                 # Requested: "just dont use embed for !tag (tag name)" - applies to found tags.
                 # For errors, embed is fine/better.
                 embed = discord.Embed(title="Tag not found", description=f"Did you mean: {', '.join(matches)}?", color=discord.Color.orange())
                 await ctx.send(embed=embed)
            else:
                 embed = discord.Embed(title="Tag not found", color=discord.Color.red())
                 await ctx.send(embed=embed)

    @tag.command()
    async def create(self, ctx, name: str, *, content: str):
        """Create a new tag."""
        if name in self.tags:
            await ctx.send(embed=discord.Embed(title="Error", description="Tag already exists.", color=discord.Color.red()))
            return
        
        self.tags[name] = {
            'content': content,
            'author_id': ctx.author.id,
            'created_at': datetime.now().strftime("%d-%m-%Y")
        }
        self.save_tags()
        await ctx.send(embed=discord.Embed(title="Success", description=f"Tag `{name}` created.", color=discord.Color.green()))

    @tag.command()
    async def list(self, ctx, target: discord.User = None):
        """List tags owned by you or another user."""
        target = target or ctx.author
        user_tags = [name for name, data in self.tags.items() if data.get('author_id') == target.id]
        
        view = TagPaginationView(ctx, user_tags, f"{target.display_name}'s Tags")
        await ctx.send(embed=view.get_embed(), view=view)

    @tag.command()
    async def delete(self, ctx, name: str):
        """Delete one of your tags."""
        if name not in self.tags:
            await ctx.send(embed=discord.Embed(title="Error", description="Tag not found.", color=discord.Color.red()))
            return
            
        if self.tags[name]['author_id'] != ctx.author.id:
            await ctx.send(embed=discord.Embed(title="Error", description="You do not own this tag.", color=discord.Color.red()))
            return
            
        del self.tags[name]
        self.save_tags()
        await ctx.send(embed=discord.Embed(title="Success", description=f"Tag `{name}` deleted.", color=discord.Color.green()))

    @tag.command(hidden=True)
    async def adelete(self, ctx, name: str):
        """(Admin) Delete any tag."""
        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send(embed=discord.Embed(title="Permission Denied", description="You don't have permission to use this command.", color=discord.Color.red()))
            return

        if name not in self.tags:
            await ctx.send(embed=discord.Embed(title="Error", description="Tag not found.", color=discord.Color.red()))
            return
            
        del self.tags[name]
        self.save_tags()
        await ctx.send(embed=discord.Embed(title="Success", description=f"Tag `{name}` deleted (Admin).", color=discord.Color.green()))

    @tag.command()
    async def raw(self, ctx, name: str):
        """Get the raw content of a tag."""
        if name in self.tags:
            # Fix escape sequence warning by using raw string or double backslash
            content = self.tags[name]['content'].replace('`', '\\`')
            await ctx.send(f"```\\n{content}\\n```")
        else:
            await ctx.send(embed=discord.Embed(title="Error", description="Tag not found.", color=discord.Color.red()))

    @tag.command()
    async def search(self, ctx, *, query: str):
        """Search for tags."""
        matches = search_tags(self.tags, query)
        view = TagPaginationView(ctx, matches, f"Search Results for '{query}'")
        await ctx.send(embed=view.get_embed(), view=view)

    @tag.command()
    async def info(self, ctx, name: str):
        """Get info about a tag."""
        if name not in self.tags:
            await ctx.send(embed=discord.Embed(title="Error", description="Tag not found.", color=discord.Color.red()))
            return
            
        data = self.tags[name]
        author = self.bot.get_user(data.get('author_id'))
        author_name = author.display_name if author else "Unknown User"
        created_at = data.get('created_at', 'Unknown')
        
        embed = discord.Embed(title=f"Tag Info: {name}", color=discord.Color.blue())
        embed.add_field(name="Owner", value=f"{author_name} (ID: {data.get('author_id')})", inline=False)
        embed.add_field(name="Created At", value=created_at, inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Tags(bot))
