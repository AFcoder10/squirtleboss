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
        avatar_size = 250
        avatar_image = avatar_image.resize((avatar_size, avatar_size))

        # 2b. Load Cover Image (Logo)
        try:
            cover = Image.open("static/cover.png").convert("RGBA")
            cover = cover.resize((150, 150))
        except:
            print("Error: static/cover.png not found")
            cover = None

        # 3. Create Circular Mask for Avatar
        mask = Image.new('L', (avatar_size, avatar_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
        avatar_circular = ImageOps.fit(avatar_image, mask.size, centering=(0.5, 0.5))
        avatar_circular.putalpha(mask)

        # 4. Prepare Text
        try:
            font_large = ImageFont.truetype("static/SF-Pro-Display-Regular.otf", 80)
            font_small = ImageFont.truetype("static/SF-Pro-Display-Regular.otf", 40)
            font_title = ImageFont.truetype("static/SF-Pro-Display-Regular.otf", 60)
        except:
             font_large = ImageFont.load_default()
             font_small = ImageFont.load_default()
             font_title = ImageFont.load_default()

        username = member.name
        server_join = member.joined_at.strftime("%B %d, %Y")
        discord_join = member.created_at.strftime("%B %d, %Y")
        member_count = member.guild.member_count
        
        welcome_title = "Welcome to Pokédia Community"
        server_text = f"Joined Server: {server_join}"
        discord_text = f"Joined Discord: {discord_join}"
        count_text = f"Member #{member_count}"

        # 5. Measure Layout
        padding = 40
        draw = ImageDraw.Draw(background)
        
        # Measure text exact dimensions
        bbox_title = draw.textbbox((0, 0), welcome_title, font=font_title)
        w_title = bbox_title[2] - bbox_title[0]
        h_title = bbox_title[3] - bbox_title[1]

        bbox_user = draw.textbbox((0, 0), username, font=font_large)
        w_user = bbox_user[2] - bbox_user[0]
        h_user = bbox_user[3] - bbox_user[1]
        
        bbox_s = draw.textbbox((0, 0), server_text, font=font_small)
        w_s = bbox_s[2] - bbox_s[0]
        h_s = bbox_s[3] - bbox_s[1]
        
        bbox_d = draw.textbbox((0, 0), discord_text, font=font_small)
        w_d = bbox_d[2] - bbox_d[0]
        h_d = bbox_d[3] - bbox_d[1]
        
        bbox_c = draw.textbbox((0, 0), count_text, font=font_small)
        w_c = bbox_c[2] - bbox_c[0]
        h_c = bbox_c[3] - bbox_c[1]
        
        line_gap = 15
        
        # --- Top Title Bar Dimensions ---
        title_bar_w = padding + w_title + padding
        title_bar_h = padding + h_title + padding

        # --- Main Box Dimensions (User + Details + Avatar) ---
        max_main_text_w = max(w_user, w_s, w_d)
        total_main_text_h = h_user + line_gap + h_s + line_gap + h_d
        
        box_gap = 50 
        main_box_w = padding + max_main_text_w + box_gap + avatar_size + padding
        main_box_h = padding + max(total_main_text_h, avatar_size) + padding
        
        # --- Count Bar Dimensions ---
        count_bar_w = padding + w_c + padding
        count_bar_h = padding + h_c + padding
        
        # Vertical Spacing between tiers
        vertical_gap = 30
        
        # Total Content Height
        total_h = title_bar_h + vertical_gap + main_box_h + vertical_gap + count_bar_h
        
        bg_w, bg_h = background.size
        
        # Start Y to center the whole group vertically
        start_y = (bg_h - total_h) // 2
        
        # --- Top Title Bar Coordinates ---
        title_x1 = (bg_w - title_bar_w) // 2
        title_y1 = start_y
        title_x2 = title_x1 + title_bar_w
        title_y2 = title_y1 + title_bar_h

        # --- Main Box Coordinates ---
        main_x1 = (bg_w - main_box_w) // 2
        main_y1 = title_y2 + vertical_gap
        main_x2 = main_x1 + main_box_w
        main_y2 = main_y1 + main_box_h
        
        # --- Count Bar Coordinates ---
        count_x1 = (bg_w - count_bar_w) // 2
        count_y1 = main_y2 + vertical_gap
        count_x2 = count_x1 + count_bar_w
        count_y2 = count_y1 + count_bar_h
        
        # 6. Create Frosted Glass Effects
        def draw_glass(x1, y1, x2, y2, radius=30):
            crop = background.crop((x1, y1, x2, y2))
            blur = crop.filter(ImageFilter.GaussianBlur(radius=10))
            overlay = Image.new('RGBA', blur.size, (255, 255, 255, 100))
            glass = Image.alpha_composite(blur, overlay)
            
            mask_glass = Image.new('L', glass.size, 0)
            d_mask = ImageDraw.Draw(mask_glass)
            d_mask.rounded_rectangle((0, 0, glass.size[0], glass.size[1]), radius=radius, fill=255)
            
            background.paste(glass, (x1, y1), mask_glass)

        # Draw Title Glass
        draw_glass(title_x1, title_y1, title_x2, title_y2, radius=20)

        # Draw Main Box Glass
        draw_glass(main_x1, main_y1, main_x2, main_y2)
        
        # Draw Count Bar Glass
        draw_glass(count_x1, count_y1, count_x2, count_y2, radius=20)

        # 7. Draw Avatar (Top Right of Main Box)
        av_x = main_x2 - avatar_size - padding
        av_y = main_y1 + padding
        background.paste(avatar_circular, (av_x, av_y), avatar_circular)
        
        # 8. Draw Text
        text_color = (0, 0, 0)

        # Title Text (Centered in Title Bar)
        title_text_x = title_x1 + (title_bar_w - w_title) // 2
        title_text_y = title_y1 + (title_bar_h - h_title) // 2 - 5
        draw.text((title_text_x, title_text_y), welcome_title, font=font_title, fill=text_color)
        
        # Main Text (Left Aligned in Main Box)
        text_x = main_x1 + padding
        current_y = main_y1 + padding
        
        draw.text((text_x, current_y), username, font=font_large, fill=text_color)
        current_y += h_user + line_gap + 10 
        
        draw.text((text_x, current_y), server_text, font=font_small, fill=text_color)
        current_y += h_s + line_gap
        
        draw.text((text_x, current_y), discord_text, font=font_small, fill=text_color)
        
        # Count Text (Centered in Count Bar)
        count_text_x = count_x1 + (count_bar_w - w_c) // 2
        count_text_y = count_y1 + (count_bar_h - h_c) // 2 - 5 
        draw.text((count_text_x, count_text_y), count_text, font=font_small, fill=text_color)
        
        # 10. Paste Cover Logo (Bottom Right)
        if cover:
            logo_x = bg_w - cover.size[0] - 20
            logo_y = bg_h - cover.size[1] - 20
            background.paste(cover, (logo_x, logo_y), cover)

        # 11. Save
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
                        await channel.send(content=f"{member.mention}", embed=embed, file=file)
                    else:
                        await channel.send(f"{member.mention}")
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

    @commands.command(name='testwelcome', hidden=True)
    async def testwelcome(self, ctx, member: discord.Member = None):
        """Tests the welcome image generation."""
        if ctx.author.id != 688983124868202496:
            return
        
        member = member or ctx.author
        await ctx.send(f"Generating welcome image for {member.display_name}...")
        
        try:
            img_buffer = await self.generate_welcome_image(member)
            if img_buffer:
                file = discord.File(fp=img_buffer, filename="welcome.png")
                embed = discord.Embed(color=discord.Color.blue())
                embed.set_image(url="attachment://welcome.png")
                await ctx.send(content=f"{member.mention}", embed=embed, file=file)
            else:
                await ctx.send("❌ Failed to generate image.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
            print(f"Error in testwelcome: {e}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
