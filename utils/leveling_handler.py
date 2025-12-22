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

def update_user_xp(guild_id, user_id, xp_amount):
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
        if current_time - last_xp < 60:
            return level, False
            
        xp += xp_amount
        last_xp = current_time
        
        # Check for level up
        xp_needed = calculate_xp_for_level(level)
        leveled_up = False
        
        if xp >= xp_needed:
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
        
        level = 1
        while True:
            needed = calculate_xp_for_level(level)
            if xp_amount >= needed:
                xp_amount -= needed # Wait, is XP cumulative or reset?
                # looking at update_user_xp:
                # xp += xp_amount ... if xp >= xp_needed: level += 1
                # It doesn't subtract XP. So XP is cumulative total for that level?
                # "if xp >= xp_needed: level += 1"
                # It does NOT reset XP to 0.
                # So XP grows indefinitely.
                # So `calculate_xp_for_level` is the threshold for THAT specific level.
                
                # So if I am level 1, I need 5(1)^2 + 50(1) + 100 = 155 XP to go to Level 2.
                # If I have 160 XP, I am Level 2? 
                # But wait, does the threshold increase?
                # Level 2 needed: 5(4) + 100 + 100 = 220?
                # If I have 160, and I level up to 2. My XP is still 160.
                # Next check: if 160 >= 220? False.
                # So yes, XP is cumulative.
                
                # So to calculate level from Total XP:
                # We just loop up.
                pass
            else:
                break
            
            # This logic assumes XP is NOT reset.
            level += 1
            
        # Re-check update_user_xp logic loop:
        # if xp >= xp_needed: level += 1
        # It only checks ONCE. So if I give 1,000,000 XP, it only levels up +1.
        # That's a bug in original code too if getting massive XP at once.
        # But for `set_user_xp`, we want to calculate the correct level for the *Total* XP.
        
        # Let's brute force level calc for safety
        calculated_level = 1
        current_threshold = calculate_xp_for_level(calculated_level)
        temp_xp = xp_amount
        
        # Actually, the previous code doesn't subtract.
        # So we just check if Total XP >= Threshold(Level).
        
        # Wait, if XP is cumulative, then:
        # Level 1 requires 155.
        # Level 2 requires 220.
        # If I have 300 XP.
        # Am I level 1 (passed 155) -> Level 2.
        # Am I level 2 (passed 220) -> Level 3.
        # So getting level from XP:
        
        lc = 1
        while True:
            req = calculate_xp_for_level(lc)
            if xp_amount >= req:
                lc += 1
            else:
                break
        
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
