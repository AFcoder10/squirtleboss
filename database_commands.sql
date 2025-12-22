-- Generated Database Commands

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


-- Data Migration
INSERT INTO guild_config (guild_id, levelup_channel_id) VALUES (1342481669747245109, 1342481670674190389) ON CONFLICT (guild_id) DO UPDATE SET levelup_channel_id = EXCLUDED.levelup_channel_id;
INSERT INTO levels (guild_id, user_id, xp, level, last_xp) VALUES (1342481669747245109, 688983124868202496, 332, 4, 1766416819.6180203) ON CONFLICT (guild_id, user_id) DO NOTHING;
INSERT INTO guild_config (guild_id, levelup_channel_id) VALUES (1339192279470178375, 1451515856013230103) ON CONFLICT (guild_id) DO UPDATE SET levelup_channel_id = EXCLUDED.levelup_channel_id;
INSERT INTO levels (guild_id, user_id, xp, level, last_xp) VALUES (1339192279470178375, 688983124868202496, 75, 1, 1766151516.8626864) ON CONFLICT (guild_id, user_id) DO NOTHING;
INSERT INTO levels (guild_id, user_id, xp, level, last_xp) VALUES (1328824772066279554, 760720549092917248, 24, 1, 1766151177.4360676) ON CONFLICT (guild_id, user_id) DO NOTHING;
INSERT INTO tags (name, content, author_id, created_at) VALUES ('meoww', 'eferrefre', 688983124868202496, '19-12-2025') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, content, author_id, created_at) VALUES ('meowwww', 'jdhfnjdeuhfb', 688983124868202496, '19-12-2025') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, content, author_id, created_at) VALUES ('meow', 'owoi', 688983124868202496, '19-12-2025') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, content, author_id, created_at) VALUES ('moe', '<@981221592627552286>', 688983124868202496, '19-12-2025') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, content, author_id, created_at) VALUES ('five', 'https://tenor.com/view/high-five-patrick-star-spongebob-squarepants-the-patrick-star-show-yes-gif-2201400520488940521', 688983124868202496, '19-12-2025') ON CONFLICT (name) DO NOTHING;
INSERT INTO tags (name, content, author_id, created_at) VALUES ('eoo', 'wooo', 688983124868202496, '19-12-2025') ON CONFLICT (name) DO NOTHING;
INSERT INTO ticket_config (category_id, log_channel_id, support_role_id) VALUES (1341694362479886336, 1451325325261803613, 1346473296866312224) ON CONFLICT (uniq_id) DO UPDATE SET category_id = EXCLUDED.category_id, log_channel_id = EXCLUDED.log_channel_id, support_role_id = EXCLUDED.support_role_id;
