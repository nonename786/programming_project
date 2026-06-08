-- 创建数据库
CREATE DATABASE IF NOT EXISTS ancient_book_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE ancient_book_db;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(100) UNIQUE NOT NULL COMMENT '用户名',
  email VARCHAR(100) UNIQUE NOT NULL COMMENT '邮箱',
  password VARCHAR(255) NOT NULL COMMENT '密码哈希',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  INDEX idx_username (username),
  INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 文档表
CREATE TABLE IF NOT EXISTS documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '用户ID',
  title VARCHAR(255) NOT NULL COMMENT '文档标题',
  filename VARCHAR(255) NOT NULL COMMENT '文件名',
  file_type VARCHAR(50) COMMENT '文件类型',
  total_pages INT DEFAULT 1 COMMENT '总页数',
  description LONGTEXT COMMENT '文档描述',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user_id (user_id),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档表';

-- 标注表
CREATE TABLE IF NOT EXISTS annotations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  document_id INT NOT NULL COMMENT '文档ID',
  page_number INT COMMENT '页码',
  content VARCHAR(500) COMMENT '标注内容',
  mark_type VARCHAR(50) COMMENT '标记类型（highlight/box/underline/circle）',
  mark_color VARCHAR(50) COMMENT '标记颜色（RGB格式）',
  original_text VARCHAR(255) COMMENT '原文字',
  simplified_text VARCHAR(255) COMMENT '简体字',
  meaning LONGTEXT COMMENT '字义',
  notes LONGTEXT COMMENT '注释',
  coordinates JSON COMMENT '坐标信息',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
  INDEX idx_document_id (document_id),
  INDEX idx_page_number (page_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标注表';

-- 造字表
CREATE TABLE IF NOT EXISTS custom_characters (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '用户ID',
  unicode_code VARCHAR(50) UNIQUE COMMENT 'Unicode编码',
  character_image VARCHAR(255) COMMENT '字体图片路径',
  character_name VARCHAR(100) COMMENT '字名',
  description LONGTEXT COMMENT '字体描述',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user_id (user_id),
  INDEX idx_unicode_code (unicode_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='造字表';

-- XML 导出记录表
CREATE TABLE IF NOT EXISTS xml_exports (
  id INT AUTO_INCREMENT PRIMARY KEY,
  document_id INT NOT NULL COMMENT '文档ID',
  user_id INT NOT NULL COMMENT '用户ID',
  xml_filename VARCHAR(255) COMMENT 'XML文件名',
  xml_content LONGTEXT COMMENT 'XML内容',
  export_path VARCHAR(255) COMMENT '导出路径',
  annotations_count INT DEFAULT 0 COMMENT '标注数量',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_document_id (document_id),
  INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='XML导出记录表';

-- 创建示例用户（密码: 123456）
INSERT IGNORE INTO users (username, email, password) VALUES 
('admin', 'admin@example.com', '$2a$10$slYQmyNdGzin7olVN3/1KuK1.q77PH4M5Hd5KwWCgfQVVi8.DGCG2');

-- 1. 修复造字表图片过长问题
ALTER TABLE custom_characters MODIFY COLUMN character_image LONGTEXT;

-- 2. 标注表增加 AI 讲解字段（用于保存“名师讲解”的内容，以便导出）
ALTER TABLE annotations ADD COLUMN ai_analysis LONGTEXT;