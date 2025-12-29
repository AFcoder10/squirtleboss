import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from io import BytesIO
import db

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_channel_id(self, guild_id):
        conn = db.get_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT channel_id FROM welcome_config WHERE guild_id = %s", (guild_id,))
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    def set_channel_id(self, guild_id, channel_id):
        conn = db.get_connection()
        if not conn: return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO welcome_config (guild_id, channel_id) 
                    VALUES (%s, %s) 
                    ON CONFLICT (guild_id) 
                    DO UPDATE SET channel_id = %s
                """, (guild_id, channel_id, channel_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"DB Error setting welcome: {e}")
            return False
        finally:
            conn.close()

    async def generate_welcome_image(self, member):
        # 1. Load Background
        try:
            background = Image.open("static/welcome-bg.png").convert("RGBA")
        except:
            print("Error: static/welcome-bg.png not found")
            return None

        # 2. Get Avatar
        avatar_data = await member.display_avatar.read()
        avatar_image = Image.open(BytesIO(avatar_data)).convert("RGBA")
        avatar_image = avatar_image.resize((250, 250))

        # 2b. Load Cover Image (Logo)
        try:
            cover = Image.open("static/cover.png").convert("RGBA")
            # Resize to small logo (e.g., 150x150 or whatever covers the start)
            cover = cover.resize((150, 150))
        except:
            print("Error: static/cover.png not found")
            cover = None

        # 3. Create Circular Mask
        mask = Image.new('L', (250, 250), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 250, 250), fill=255)
        avatar_circular = ImageOps.fit(avatar_image, mask.size, centering=(0.5, 0.5))
        avatar_circular.putalpha(mask)

        # 4. Paste Avatar (Center)
        bg_w, bg_h = background.size
        av_w, av_h = avatar_circular.size
        # Center horizontally, slightly above center vertically
        paste_x = (bg_w - av_w) // 2
        paste_y = (bg_h - av_h) // 2 - 100 
        
        background.paste(avatar_circular, (paste_x, paste_y), avatar_circular)

        # 5. Calculate Layout & Fonts
        try:
            font_large = ImageFont.truetype("static/SF-Pro-Display-Regular.otf", 80)
            font_small = ImageFont.truetype("static/SF-Pro-Display-Regular.otf", 40)
        except:
             font_large = ImageFont.load_default()
             font_small = ImageFont.load_default()

        # Measure Text
        username = member.name
        server_join = member.joined_at.strftime("%B %d, %Y")
        discord_join = member.created_at.strftime("%B %d, %Y")
        member_count = member.guild.member_count
        
        server_text = f"Joined Server: {server_join}"
        discord_text = f"Joined Discord: {discord_join}"
        count_text = f"Member #{member_count}"
        
        draw = ImageDraw.Draw(background) 
        
        bbox_user = draw.textbbox((0, 0), username, font=font_large)
        w_user = bbox_user[2] - bbox_user[0]
        
        bbox_s = draw.textbbox((0, 0), server_text, font=font_small)
        w_s = bbox_s[2] - bbox_s[0]
        
        bbox_d = draw.textbbox((0, 0), discord_text, font=font_small)
        w_d = bbox_d[2] - bbox_d[0]
        
        bbox_c = draw.textbbox((0, 0), count_text, font=font_small)
        w_c = bbox_c[2] - bbox_c[0]
        
        # Determine Glass Box Size
        content_w = max(250, w_user, w_s, w_d, w_c) + 100 # Min 250 (avatar) + padding
        # content_h = 250 + 20 + 80 + 30 + 40 + 30 + 40 + 30 + 40 + 50 # Added height for count
        
        # Calculate Box Coordinates
        box_w = content_w + 100
        box_h = 250 + 450 # Increased height again for extra line
        
        box_x1 = (bg_w - box_w) // 2
        box_y1 = paste_y - 50
        box_x2 = box_x1 + box_w
        box_y2 = box_y1 + box_h
        
        # 6. Create Frosted Glass Effect
        crop = background.crop((box_x1, box_y1, box_x2, box_y2))
        blur = crop.filter(ImageFilter.GaussianBlur(radius=10))
        overlay = Image.new('RGBA', blur.size, (255, 255, 255, 100))
        glass = Image.alpha_composite(blur, overlay)
        
        # Rounded Corners Mask
        mask_glass = Image.new('L', glass.size, 0)
        draw_mask = ImageDraw.Draw(mask_glass)
        draw_mask.rounded_rectangle((0, 0, glass.size[0], glass.size[1]), radius=30, fill=255)
        
        # Paste Glass
        background.paste(glass, (box_x1, box_y1), mask_glass)

        # 7. Paste Avatar (Re-paste on top of glass)
        background.paste(avatar_circular, (paste_x, paste_y), avatar_circular)
        
        # 7b. Paste Cover Logo (Bottom Right)
        if cover:
            logo_x = bg_w - cover.size[0] - 5 
            logo_y = bg_h - cover.size[1] - 5
            background.paste(cover, (logo_x, logo_y), cover)

        # 8. Draw Text
        draw = ImageDraw.Draw(background)
        # Text Colors
        text_color = (0, 0, 0)
        
        draw.text(((bg_w - w_user) // 2, paste_y + av_h + 20), username, font=font_large, fill=text_color)
        draw.text(((bg_w - w_s) // 2, paste_y + av_h + 120), server_text, font=font_small, fill=text_color)
        draw.text(((bg_w - w_d) // 2, paste_y + av_h + 170), discord_text, font=font_small, fill=text_color)
        draw.text(((bg_w - w_c) // 2, paste_y + av_h + 220), count_text, font=font_small, fill=text_color)

        # 6. Save to Bytes
        output = BytesIO()
        background.save(output, format="PNG")
        output.seek(0)
        return output

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel_id = self.get_channel_id(member.guild.id)
        
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel:
                try:
                    img_buffer = await self.generate_welcome_image(member)
                    if img_buffer:
                        file = discord.File(fp=img_buffer, filename="welcome.png")
                        embed = discord.Embed(color=discord.Color.blue())
                        embed.set_image(url="attachment://welcome.png")
                        await channel.send(content=f"Welcome to Pokédia Community, {member.mention}", embed=embed, file=file)
                    else:
                        await channel.send(f"Welcome to Pokédia Community, {member.mention}")
                except Exception as e:
                    print(f"Error sending welcome message: {e}")

    @commands.command(name='welcome_log', hidden=True)
    @commands.has_permissions(administrator=True)
    async def welcome_log(self, ctx, channel: discord.TextChannel):
        """Sets the channel for welcome messages."""
        success = self.set_channel_id(ctx.guild.id, channel.id)
        if success:
            await ctx.send(f"✅ Welcome messages will be sent to {channel.mention}")
        else:
            await ctx.send("❌ Failed to save to database.")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
