-- Create tables for SquirtleData

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

CREATE TABLE IF NOT EXISTS vouches (
    user_id BIGINT PRIMARY KEY,
    score INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS giveaways (
    message_id BIGINT PRIMARY KEY,
    channel_id BIGINT,
    guild_id BIGINT,
    host_id BIGINT,
    title TEXT,
    prize TEXT,
    winners INT,
    end_time BIGINT,
    status TEXT,
    gw_id TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS giveaway_participants (
    message_id BIGINT,
    user_id BIGINT,
    PRIMARY KEY (message_id, user_id)
);

CREATE TABLE IF NOT EXISTS autoroles (
    guild_id BIGINT PRIMARY KEY,
    role_id BIGINT
);

CREATE TABLE IF NOT EXISTS welcome_config (
    guild_id BIGINT PRIMARY KEY,
    channel_id BIGINT
);

CREATE TABLE IF NOT EXISTS vouch_config (
    guild_id BIGINT PRIMARY KEY,
    log_channel BIGINT,
    req_channel BIGINT,
    vouch_log_channel BIGINT,
    unvouch_log_channel BIGINT
);
