import db
import math
import time

def get_connection():
    return db.get_connection()

def calculate_xp_for_level(level):
    # Formula: 5 * (level ^ 2) + 50 * level + 100
    return 5 * (level ** 2) + 50 * level + 100

def get_user_data(guild_id, user_id):
    conn = get_connection()
    if not conn:
        return None
        
    try:
        cur = conn.cursor()
        cur.execute("SELECT xp, level, last_xp FROM levels WHERE guild_id = %s AND user_id = %s", (guild_id, user_id))
        row = cur.fetchone()
        
        if row:
            return {
                'xp': row[0],
                'level': row[1],
                'last_xp': row[2]
            }
        return None
    except Exception as e:
        print(f"Error getting user data: {e}")
        return None
    finally:
        conn.close()

def get_leaderboard(guild_id, limit=10):
    conn = get_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, xp, level, last_xp 
            FROM levels 
            WHERE guild_id = %s 
            ORDER BY xp DESC 
            LIMIT %s
        """, (guild_id, limit))
        rows = cur.fetchall()
        
        users = []
        for row in rows:
            users.append({
                'user_id': str(row[0]),
                'xp': row[1],
                'level': row[2],
                'last_xp': row[3]
            })
        return users
    except Exception as e:
        print(f"Error getting leaderboard: {e}")
        return []
    finally:
        conn.close()

def set_levelup_channel(guild_id, channel_id):
    conn = get_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO guild_config (guild_id, levelup_channel_id)
            VALUES (%s, %s)
            ON CONFLICT (guild_id) DO UPDATE SET levelup_channel_id = EXCLUDED.levelup_channel_id
        """, (guild_id, channel_id))
        conn.commit()
    except Exception as e:
        print(f"Error setting levelup channel: {e}")
    finally:
        conn.close()

def get_levelup_channel(guild_id):
    conn = get_connection()
    if not conn:
        return None
        
    try:
        cur = conn.cursor()
        cur.execute("SELECT levelup_channel_id FROM guild_config WHERE guild_id = %s", (guild_id,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting levelup channel: {e}")
        return None
    finally:
        conn.close()

def update_user_xp(guild_id, user_id, xp_amount, bypass_cooldown=False):
    conn = get_connection()
    if not conn:
        return 1, False
        
    try:
        cur = conn.cursor()
        
        # Get current data or initialize
        cur.execute("SELECT xp, level, last_xp FROM levels WHERE guild_id = %s AND user_id = %s", (guild_id, user_id))
        row = cur.fetchone()
        
        current_time = time.time()
        
        if row:
            xp, level, last_xp = row
        else:
            xp, level, last_xp = 0, 1, 0
            
        # Check cooldown
        if not bypass_cooldown and (current_time - last_xp < 60):
            return level, False
            
        xp += xp_amount
        last_xp = current_time
        
        # Check for level up
        xp_needed = calculate_xp_for_level(level)
        leveled_up = False
        
        if xp >= xp_needed:
            xp -= xp_needed  # Reset XP by subtracting requirement
            level += 1
            leveled_up = True
            
        # Upsert
        cur.execute("""
            INSERT INTO levels (guild_id, user_id, xp, level, last_xp)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                xp = EXCLUDED.xp,
                level = EXCLUDED.level,
                last_xp = EXCLUDED.last_xp
        """, (guild_id, user_id, xp, level, last_xp))
        conn.commit()
        
        return level, leveled_up
        
    except Exception as e:
        print(f"Error updating user XP: {e}")
        return 1, False
    finally:
        conn.close()

def get_rank(guild_id, user_id):
    conn = get_connection()
    if not conn:
        return None
    
    try:
        # Calculate rank using SQL window function or count
        cur = conn.cursor()
        cur.execute("""
            SELECT rank FROM (
                SELECT user_id, RANK() OVER (ORDER BY xp DESC) as rank 
                FROM levels 
                WHERE guild_id = %s
            ) as ranked_users
            WHERE user_id = %s
        """, (guild_id, user_id))
        
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting rank: {e}")
        return None
    finally:
        conn.close()

def set_user_xp(guild_id, user_id, xp_amount):
    conn = get_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        
        # Calculate level based on new XP
        # This is tricky because the formula is Level -> XP.
        # Inverse formula needed or iterative check?
        # Formula: XP = 5 * (L^2) + 50 * L + 100
        # This is XP needed for NEXT level.
        # This relationship is complex.
        # The existing system doesn't seem to track "Total XP" perfectly against a curve, 
        # it just checks if current_xp >= needed_for_next.
        # So if we set XP to 1000, what is the level?
        # A simple approach: set XP and keep level as is? No, that breaks things.
        # Or just reset level to 1 and let them level up?
        # Or try to calculate level? 
        # Quadratic formula: 5L^2 + 50L + (100 - XP) = 0 (roughly)
        # But `calculate_xp_for_level` returns the threshold for the CURRENT level to advance to NEXT?
        # "xp_needed = calculate_xp_for_level(level)"
        # If user has `xp`, and `xp >= xp_needed`, they level up.
        # So we should probably iterate to find the correct level for the given XP?
        # Or just let the admin set Level too?
        # User asked for "change xp".
        # Let's just set XP and Level.
        # But for `set_user_xp` with just `xp_amount`, we should probably just set XP and leave level alone, 
        # or reset level to 1 and recalculate? Recalculating is safer.
        
        # Adjusted logic for Non-Cumulative XP
        # The user wants "XP resets after level up".
        # So "xp" in DB is current progress towards NEXT level.
        # "level" is current level.
        
        # If user runs ?setxp 1500:
        # We assume they want to set the TOTAL XP? Or just the current XP bar?
        # Usually "setxp" sets the current bar value.
        # But if the value is higher than the level requirement, we should probably level them up automatically?
        # Or just let it be high and they level up on next message?
        
        # Let's assume ?setxp sets the `xp` column directly.
        # If it's > requirement, we just set it. 
        # The `update_user_xp` function will handle the level up on next trigger.
        # OR we could be smart and calculate the level if it overflows.
        
        # If I set XP to 5000, and level 1 needs 155:
        # Should I be Level 1 with 5000 XP (waiting for next message to level up many times)?
        # Or Level X with Y XP?
        
        # Let's just set the XP column. This allows admins to fix things or force high XP.
        # But `set_user_xp` was previously trying to calculate level.
        
        # If we want to recalculate EVERYTHING based on total XP, that's complex because we are switching models.
        # Given "setxp", let's just set the `xp` value for the CURRENT level.
        # If they want to change level, they can't with this command?
        # Maybe we should assume the user handles the level separately or doesn't care.
        # But wait, `setxp` implies setting the progress.
        
        # Let's just set the raw value.
        lc = row[1] if row else 1 # Keep current level or default 1
        
        # But wait, we need `row` to know current level if we are just updating XP.
        # We need to fetch it first if we didn't above (we didn't).
        
        # Fetch current level
        cur.execute("SELECT level FROM levels WHERE guild_id = %s AND user_id = %s", (guild_id, user_id))
        r = cur.fetchone()
        
        current_level = r[0] if r else 1
        
        # Update only XP, keep level
        # If xp_amount > needed for current_level, they will level up on next message.
        lc = current_level
        
        cur.execute("""
            INSERT INTO levels (guild_id, user_id, xp, level, last_xp)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                xp = EXCLUDED.xp,
                level = EXCLUDED.level
        """, (guild_id, user_id, xp_amount, lc, time.time()))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting user XP: {e}")
        return False
    finally:
        conn.close()
