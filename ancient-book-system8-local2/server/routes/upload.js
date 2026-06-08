const express = require('express');
const path = require('path');
const fs = require('fs');
const db = require('../config/database');
const authMiddleware = require('../middleware/auth');
const router = express.Router();

// 上传文件
router.post('/', authMiddleware, async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: '没有文件上传' });
    }

    const { title, description } = req.body;
    const filename = req.file.filename;
    const fileType = req.file.mimetype;
    let totalPages = 1;

    // PDF 处理（这里简化处理，实际可以使用 pdf-parse）
    if (fileType === 'application/pdf') {
      totalPages = 1; // 简化版本，可扩展
    }

    // 保存到数据库
    const result = await db.run(
      `INSERT INTO documents 
       (user_id, title, filename, file_type, total_pages, description) 
       VALUES (?, ?, ?, ?, ?, ?)`,
      [req.userId, title || filename, filename, fileType, totalPages, description || '']
    );

    res.status(201).json({
      message: '文件上传成功',
      document: {
        id: result.id,
        title: title || filename,
        filename,
        fileType,
        totalPages
      }
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// 获取用户文档列表
router.get('/documents', authMiddleware, async (req, res) => {
  try {
    const documents = await db.all(
      'SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC',
      [req.userId]
    );
    res.json({ documents });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// 获取文档详情
router.get('/documents/:id', authMiddleware, async (req, res) => {
  try {
    const document = await db.get(
      'SELECT * FROM documents WHERE id = ? AND user_id = ?',
      [req.params.id, req.userId]
    );

    if (!document) {
      return res.status(404).json({ error: '文档不存在' });
    }

    res.json({ document });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// 删除文档
router.delete('/documents/:id', authMiddleware, async (req, res) => {
  try {
    const document = await db.get(
      'SELECT * FROM documents WHERE id = ? AND user_id = ?',
      [req.params.id, req.userId]
    );

    if (!document) {
      return res.status(404).json({ error: '文档不存在' });
    }

    // 删除物理文件
    const filePath = path.join(__dirname, '../uploads/documents', document.filename);
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
    }

    // 删除数据库记录
    await db.run('DELETE FROM documents WHERE id = ?', [req.params.id]);

    res.json({ message: '文档已删除' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// 获取文档文件（用于显示）
router.get('/file/:filename', authMiddleware, (req, res) => {
  try {
    const filename = req.params.filename;
    const filePath = path.join(__dirname, '../uploads/documents', filename);

    // 安全检查
    if (!filePath.startsWith(path.join(__dirname, '../uploads/documents'))) {
      return res.status(403).json({ error: '禁止访问' });
    }

    if (fs.existsSync(filePath)) {
      res.sendFile(filePath);
    } else {
      res.status(404).json({ error: '文件不存在' });
    }
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
