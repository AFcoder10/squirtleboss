import json
import os
import psycopg2
from psycopg2.extras import execute_values
import db

def get_connection():
    return psycopg2.connect(
        host=db.DB_HOST,
        database=db.DB_NAME,
        user=db.DB_USER,
        password=db.DB_PASS,
        port=db.DB_PORT
    )

def migrate_levels(conn):
    print("Migrating levels.json...")
    path = os.path.join('data', 'levels.json')
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("levels.json is empty or invalid.")
            return

    cur = conn.cursor()
    
    levels_data = []
    guild_configs = []

    for guild_id_str, guild_data in data.items():
        guild_id = int(guild_id_str)
        
        # Handle guild config (levelup_channel)
        if 'levelup_channel' in guild_data:
            channel_id = guild_data['levelup_channel']
            if channel_id:
                guild_configs.append((guild_id, channel_id))
        
        # Handle users
        for user_id_str, user_data in guild_data.items():
            if user_id_str == 'levelup_channel':
                continue
                
            if isinstance(user_data, dict):
                user_id = int(user_id_str)
                levels_data.append((
                    guild_id,
                    user_id,
                    user_data.get('xp', 0),
                    user_data.get('level', 1),
                    user_data.get('last_xp', 0)
                ))

    if levels_data:
        execute_values(cur, """
            INSERT INTO levels (guild_id, user_id, xp, level, last_xp)
            VALUES %s
            ON CONFLICT (guild_id, user_id) DO NOTHING
        """, levels_data)
        print(f"Inserted {len(levels_data)} user level records.")

    if guild_configs:
        execute_values(cur, """
            INSERT INTO guild_config (guild_id, levelup_channel_id)
            VALUES %s
            ON CONFLICT (guild_id) DO UPDATE SET levelup_channel_id = EXCLUDED.levelup_channel_id
        """, guild_configs)
        print(f"Inserted {len(guild_configs)} guild configs.")
        
    cur.close()

def migrate_tags(conn):
    print("Migrating tags.json...")
    path = os.path.join('data', 'tags.json')
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("tags.json is empty or invalid.")
            return

    cur = conn.cursor()
    
    tags_data = []
    for name, tag_data in data.items():
        tags_data.append((
            name,
            tag_data.get('content', ''),
            tag_data.get('author_id'),
            tag_data.get('created_at')
        ))

    if tags_data:
        execute_values(cur, """
            INSERT INTO tags (name, content, author_id, created_at)
            VALUES %s
            ON CONFLICT (name) DO NOTHING
        """, tags_data)
        print(f"Inserted {len(tags_data)} tags.")
        
    cur.close()

def migrate_tickets(conn):
    print("Migrating tickets.json and ticketinfo.json...")
    
    cur = conn.cursor()

    # tickets.json (General Config)
    tickets_path = os.path.join('data', 'tickets.json')
    if os.path.exists(tickets_path):
        with open(tickets_path, 'r') as f:
            try:
                config = json.load(f)
                if config:
                    cur.execute("""
                        INSERT INTO ticket_config (category_id, log_channel_id, support_role_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (uniq_id) DO UPDATE SET
                            category_id = EXCLUDED.category_id,
                            log_channel_id = EXCLUDED.log_channel_id,
                            support_role_id = EXCLUDED.support_role_id
                    """, (
                        config.get('category_id'),
                        config.get('log_channel_id'),
                        config.get('support_role_id')
                    ))
                    print("Updated ticket config.")
            except json.JSONDecodeError:
                print("tickets.json: invalid JSON")

    # ticketinfo.json (Active Tickets)
    info_path = os.path.join('data', 'ticketinfo.json')
    if os.path.exists(info_path):
        with open(info_path, 'r') as f:
            try:
                info = json.load(f)
                active_tickets = info.get('active_tickets', {})
                
                ticket_rows = []
                for user_id_str, channel_id in active_tickets.items():
                    ticket_rows.append((int(user_id_str), channel_id))
                
                if ticket_rows:
                    execute_values(cur, """
                        INSERT INTO active_tickets (user_id, channel_id)
                        VALUES %s
                        ON CONFLICT (user_id) DO NOTHING
                    """, ticket_rows)
                    print(f"Inserted {len(ticket_rows)} active tickets.")
            except json.JSONDecodeError:
                print("ticketinfo.json: invalid JSON")
                
    cur.close()

def migrate_tempbans(conn):
    print("Migrating tempbans.json...")
    path = os.path.join('data', 'tempbans.json')
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("tempbans.json is empty or invalid.")
            return

    cur = conn.cursor()
    bans = data.get('bans', [])
    
    ban_rows = []
    for ban in bans:
        ban_rows.append((
            ban.get('user_id'),
            ban.get('guild_id'),
            ban.get('end_time')
        ))

    if ban_rows:
        execute_values(cur, """
            INSERT INTO tempbans (user_id, guild_id, end_time)
            VALUES %s
        """, ban_rows)
        print(f"Inserted {len(ban_rows)} temp bans.")
        
    cur.close()

def main():
    try:
        conn = get_connection()
        conn.autocommit = True
        print("Connected to DB.")
        
        migrate_levels(conn)
        migrate_tags(conn)
        migrate_tickets(conn)
        migrate_tempbans(conn)
        
        conn.close()
        print("Migration complete.")
        
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    main()
