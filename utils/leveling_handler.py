import json
import os
import math
import time

DATA_PATH = os.path.join(os.getcwd(), 'data', 'levels.json')

def load_data():
    if not os.path.exists(DATA_PATH):
        return {}
    try:
        with open(DATA_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_data(data):
    # Atomic save to prevent corruption
    temp_path = DATA_PATH + '.tmp'
    with open(temp_path, 'w') as f:
        json.dump(data, f, indent=4)
    os.replace(temp_path, DATA_PATH)

def get_user_data(guild_id, user_id):
    data = load_data()
    guild_id = str(guild_id)
    user_id = str(user_id)
    
    if guild_id not in data:
        return None
    if user_id not in data[guild_id]:
        return None
        
    return data[guild_id][user_id]

def calculate_xp_for_level(level):
    # Formula: 5 * (level ^ 2) + 50 * level + 100
    return 5 * (level ** 2) + 50 * level + 100

def get_leaderboard(guild_id, limit=10):
    data = load_data()
    guild_id = str(guild_id)
    
    if guild_id not in data:
        return []
        
    # Filter out non-user keys like "levelup_channel"
    users = []
    for user_id, user_data in data[guild_id].items():
        if isinstance(user_data, dict) and 'xp' in user_data:
            users.append({'user_id': user_id, **user_data})
            
    # Sort by XP descending
    users.sort(key=lambda x: x['xp'], reverse=True)
    return users[:limit]

def set_levelup_channel(guild_id, channel_id):
    data = load_data()
    guild_id = str(guild_id)
    
    if guild_id not in data:
        data[guild_id] = {}
        
    data[guild_id]['levelup_channel'] = channel_id
    save_data(data)

def get_levelup_channel(guild_id):
    data = load_data()
    guild_id = str(guild_id)
    return data.get(guild_id, {}).get('levelup_channel')

def update_user_xp(guild_id, user_id, xp_amount):
    data = load_data()
    guild_id = str(guild_id)
    user_id = str(user_id)
    
    if guild_id not in data:
        data[guild_id] = {}
        
    if user_id not in data[guild_id]:
        data[guild_id][user_id] = {
            'xp': 0,
            'level': 1,
            'last_xp': 0
        }
    
    user_data = data[guild_id][user_id]
    
    # Check cooldown
    current_time = time.time()
    if current_time - user_data.get('last_xp', 0) < 60:
        return user_data['level'], False
        
    user_data['xp'] += xp_amount
    user_data['last_xp'] = current_time
    
    # Check for level up
    current_level = user_data['level']
    xp_needed = calculate_xp_for_level(current_level)
    
    leveled_up = False
    if user_data['xp'] >= xp_needed:
        user_data['level'] += 1
        # Subtract XP cost or keep cumulative? Usually cumulative is better for leaderboards, 
        # but formula implies "XP needed for NEXT level".
        # If we keep total XP, we just check against the threshold for CURRENT level.
        # Let's assume cumulative XP model based on "rank level and xp".
        leveled_up = True
        
    save_data(data)
    return user_data['level'], leveled_up

def get_rank(guild_id, user_id):
    leaderboard = get_leaderboard(guild_id, limit=999999) # Get all users
    user_id = str(user_id)
    
    for index, entry in enumerate(leaderboard):
        if entry['user_id'] == user_id:
            return index + 1
            
    return None
