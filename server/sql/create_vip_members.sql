-- VIP 会员表建表语句
-- 数据库：MySQL 8.0

CREATE TABLE IF NOT EXISTS `vip_members` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `openid` VARCHAR(100) NOT NULL,
  `plan_type` ENUM('monthly', 'quarterly', 'yearly', 'permanent') NOT NULL,
  `start_at` DATETIME NOT NULL,
  `expire_at` DATETIME DEFAULT NULL COMMENT '永久会员为 NULL',
  `remark` VARCHAR(200) DEFAULT NULL COMMENT '备注',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user` (`user_id`),
  INDEX `idx_openid` (`openid`),
  INDEX `idx_expire` (`expire_at`),
  CONSTRAINT `fk_vip_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='VIP 会员表';
