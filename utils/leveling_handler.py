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
        
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error getting rank: {e}")
        return None
    finally:
        conn.close()
