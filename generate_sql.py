import json
import os

OUTPUT_FILE = "database_commands.sql"

def get_schema():
    return """
-- Schema Creation

CREATE TABLE IF NOT EXISTS levels (
    guild_id BIGINT,
    user_id BIGINT,
    xp BIGINT DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_xp DOUBLE PRECISION DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id BIGINT PRIMARY KEY,
    levelup_channel_id BIGINT
);

CREATE TABLE IF NOT EXISTS tags (
    name TEXT PRIMARY KEY,
    content TEXT,
    author_id BIGINT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS ticket_config (
    uniq_id INTEGER PRIMARY KEY DEFAULT 1 CHECK (uniq_id = 1),
    category_id BIGINT,
    log_channel_id BIGINT,
    support_role_id BIGINT
);

CREATE TABLE IF NOT EXISTS active_tickets (
    user_id BIGINT PRIMARY KEY,
    channel_id BIGINT
);

CREATE TABLE IF NOT EXISTS tempbans (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    guild_id BIGINT,
    end_time DOUBLE PRECISION
);

"""

def escape_string(s):
    if s is None:
        return "NULL"
    if isinstance(s, (int, float)):
        return str(s)
    # Basic SQL escaping for single quotes
    return "'" + str(s).replace("'", "''") + "'"

def generate_levels(f):
    print("Processing levels.json...")
    path = os.path.join('data', 'levels.json')
    if not os.path.exists(path):
        f.write("-- levels.json not found\n")
        return

    with open(path, 'r') as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError:
            f.write("-- levels.json is invalid\n")
            return

    for guild_id_str, guild_data in data.items():
        guild_id = int(guild_id_str)
        
        if 'levelup_channel' in guild_data:
            channel_id = guild_data['levelup_channel']
            if channel_id:
                f.write(f"INSERT INTO guild_config (guild_id, levelup_channel_id) VALUES ({guild_id}, {channel_id}) ON CONFLICT (guild_id) DO UPDATE SET levelup_channel_id = EXCLUDED.levelup_channel_id;\n")
        
        for user_id_str, user_data in guild_data.items():
            if user_id_str == 'levelup_channel':
                continue
                
            if isinstance(user_data, dict):
                user_id = int(user_id_str)
                xp = user_data.get('xp', 0)
                level = user_data.get('level', 1)
                last_xp = user_data.get('last_xp', 0)
                f.write(f"INSERT INTO levels (guild_id, user_id, xp, level, last_xp) VALUES ({guild_id}, {user_id}, {xp}, {level}, {last_xp}) ON CONFLICT (guild_id, user_id) DO NOTHING;\n")

def generate_tags(f):
    print("Processing tags.json...")
    path = os.path.join('data', 'tags.json')
    if not os.path.exists(path):
        f.write("-- tags.json not found\n")
        return

    with open(path, 'r') as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError:
            f.write("-- tags.json is invalid\n")
            return

    for name, tag_data in data.items():
        content = escape_string(tag_data.get('content', ''))
        author_id = tag_data.get('author_id', 'NULL')
        created_at = escape_string(tag_data.get('created_at', ''))
        name_esc = escape_string(name)
        f.write(f"INSERT INTO tags (name, content, author_id, created_at) VALUES ({name_esc}, {content}, {author_id}, {created_at}) ON CONFLICT (name) DO NOTHING;\n")

def generate_tickets(f):
    print("Processing tickets.json and ticketinfo.json...")
    
    # tickets.json
    tickets_path = os.path.join('data', 'tickets.json')
    if os.path.exists(tickets_path):
        with open(tickets_path, 'r') as json_file:
            try:
                config = json.load(json_file)
                if config:
                    cat_id = config.get('category_id', 'NULL')
                    log_id = config.get('log_channel_id', 'NULL')
                    role_id = config.get('support_role_id', 'NULL')
                    f.write(f"INSERT INTO ticket_config (category_id, log_channel_id, support_role_id) VALUES ({cat_id}, {log_id}, {role_id}) ON CONFLICT (uniq_id) DO UPDATE SET category_id = EXCLUDED.category_id, log_channel_id = EXCLUDED.log_channel_id, support_role_id = EXCLUDED.support_role_id;\n")
            except json.JSONDecodeError:
                f.write("-- tickets.json invalid\n")

    # ticketinfo.json
    info_path = os.path.join('data', 'ticketinfo.json')
    if os.path.exists(info_path):
        with open(info_path, 'r') as json_file:
            try:
                info = json.load(json_file)
                active_tickets = info.get('active_tickets', {})
                for user_id_str, channel_id in active_tickets.items():
                    f.write(f"INSERT INTO active_tickets (user_id, channel_id) VALUES ({user_id_str}, {channel_id}) ON CONFLICT (user_id) DO NOTHING;\n")
            except json.JSONDecodeError:
                f.write("-- ticketinfo.json invalid\n")

def generate_tempbans(f):
    print("Processing tempbans.json...")
    path = os.path.join('data', 'tempbans.json')
    if not os.path.exists(path):
        f.write("-- tempbans.json not found\n")
        return

    with open(path, 'r') as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError:
            f.write("-- tempbans.json invalid\n")
            return

    bans = data.get('bans', [])
    for ban in bans:
        user_id = ban.get('user_id', 'NULL')
        guild_id = ban.get('guild_id', 'NULL')
        end_time = ban.get('end_time', 'NULL')
        f.write(f"INSERT INTO tempbans (user_id, guild_id, end_time) VALUES ({user_id}, {guild_id}, {end_time});\n")

def main():
    with open(OUTPUT_FILE, 'w') as f:
        f.write("-- Generated Database Commands\n")
        f.write(get_schema())
        f.write("\n-- Data Migration\n")
        
        generate_levels(f)
        generate_tags(f)
        generate_tickets(f)
        generate_tempbans(f)
        
    print(f"Successfully created {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
