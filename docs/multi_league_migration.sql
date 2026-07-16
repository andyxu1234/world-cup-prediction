-- ============================================================
-- 多联赛支持改造 SQL 脚本
-- 在影子库 football_prediction 上执行
-- ============================================================

-- ============================================================
-- Step 1: 新建 leagues 表
-- ============================================================

CREATE TABLE leagues (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL COMMENT '英文名',
    cn_name VARCHAR(50) NOT NULL COMMENT '中文名',
    logo VARCHAR(500) COMMENT '联赛 logo URL',
    highlightly_league_id INT NOT NULL COMMENT 'Highlightly 对应的 league_id',
    season INT NOT NULL COMMENT '当前赛季年份',
    type ENUM('league', 'cup') NOT NULL COMMENT '联赛 or 杯赛',
    country VARCHAR(50) COMMENT '国家/地区',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用同步',
    sort_order INT DEFAULT 0 COMMENT '前端展示排序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_highlightly (highlightly_league_id, season)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='联赛表';


-- ============================================================
-- Step 2: 预置联赛数据
-- highlightly_league_id 来自 Highlightly /leagues 接口实际返回值
-- season 统一用 2026
-- 世界杯 is_active=FALSE（已结束，不同步新数据但保留历史）
-- ============================================================

INSERT INTO leagues (name, cn_name, logo, highlightly_league_id, season, type, country, is_active, sort_order) VALUES
('World Cup',                '世界杯', 'https://highlightly.net/soccer/images/leagues/1635.png',   1635,   2026, 'cup',    'World',  FALSE, 0),
('Premier League',           '英超',   'https://highlightly.net/soccer/images/leagues/33973.png',  33973,  2026, 'league', 'England', TRUE, 1),
('Ligue 1',                  '法甲',   'https://highlightly.net/soccer/images/leagues/52695.png',  52695,  2026, 'league', 'France',  TRUE, 2),
('Bundesliga',               '德甲',   'https://highlightly.net/soccer/images/leagues/67162.png',  67162,  2026, 'league', 'Germany', TRUE, 3),
('Serie A',                  '意甲',   'https://highlightly.net/soccer/images/leagues/115669.png', 115669, 2026, 'league', 'Italy',   TRUE, 4),
('La Liga',                  '西甲',   'https://highlightly.net/soccer/images/leagues/119924.png', 119924, 2026, 'league', 'Spain',   TRUE, 5),
('UEFA Champions League',    '欧冠',   'https://highlightly.net/soccer/images/leagues/2486.png',   2486,   2026, 'cup',    'Europe',  TRUE, 6),
('UEFA Europa League',       '欧联',   'https://highlightly.net/soccer/images/leagues/3337.png',   3337,   2026, 'cup',    'Europe',  TRUE, 7);


-- ============================================================
-- Step 3: teams 表加 league_id 字段
-- ============================================================

ALTER TABLE teams 
ADD COLUMN league_id INT NULL COMMENT '所属联赛 ID',
ADD CONSTRAINT fk_teams_league FOREIGN KEY (league_id) REFERENCES leagues(id);

-- 回填：所有现有球队归到世界杯
UPDATE teams SET league_id = (SELECT id FROM leagues WHERE cn_name = '世界杯' LIMIT 1) 
WHERE league_id IS NULL;


-- ============================================================
-- Step 4: matches 表加 league_id 字段
-- ============================================================

ALTER TABLE matches 
ADD COLUMN league_id INT NULL COMMENT '所属联赛 ID',
ADD CONSTRAINT fk_matches_league FOREIGN KEY (league_id) REFERENCES leagues(id);

-- 回填：所有现有比赛归到世界杯
UPDATE matches SET league_id = (SELECT id FROM leagues WHERE cn_name = '世界杯' LIMIT 1) 
WHERE league_id IS NULL;


-- ============================================================
-- Step 5: long_term_predictions 表加 league_id 字段
-- ============================================================

ALTER TABLE long_term_predictions 
ADD COLUMN league_id INT NULL COMMENT '所属联赛 ID',
ADD CONSTRAINT fk_ltp_league FOREIGN KEY (league_id) REFERENCES leagues(id);

-- 回填
UPDATE long_term_predictions SET league_id = (SELECT id FROM leagues WHERE cn_name = '世界杯' LIMIT 1) 
WHERE league_id IS NULL;


-- ============================================================
-- Step 6: 验证
-- ============================================================

-- 验证 leagues 表
SELECT id, cn_name, highlightly_league_id, season, type, is_active FROM leagues ORDER BY sort_order;

-- 验证 teams 回填
SELECT league_id, COUNT(*) FROM teams GROUP BY league_id;
-- 预期: 所有球队 league_id = 世界杯的 id

-- 验证 matches 回填
SELECT league_id, COUNT(*) FROM matches GROUP BY league_id;
-- 预期: 所有比赛 league_id = 世界杯的 id

-- 验证 long_term_predictions 回填
SELECT league_id, COUNT(*) FROM long_term_predictions GROUP BY league_id;
