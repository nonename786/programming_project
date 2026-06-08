const express = require('express');
const router = express.Router();
const db = require('../config/database');
const authMiddleware = require('../middleware/auth');

// 1. 获取当前用户的所有历史记录汇总
router.get('/all', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;

        const docs = await db.all('SELECT id, title, created_at, file_type FROM documents WHERE user_id = ? ORDER BY created_at DESC',[userId]);
        
        // 查询批注：获取全部字段(a.*)确保包含 original_text, meaning, image_data 等
        const annotations = await db.all(`
            SELECT a.*, d.title as doc_title 
            FROM annotations a 
            JOIN documents d ON a.document_id = d.id 
            WHERE d.user_id = ? 
            ORDER BY a.created_at DESC`, [userId]);

        // 【修改点】：造字记录改为获取所有字段 (*) 或者明确包含图片字段(image_data)
        const characters = await db.all('SELECT * FROM custom_characters WHERE user_id = ? ORDER BY created_at DESC', [userId]);

        res.json({ docs, annotations, characters });
    } catch (err) {
        res.status(500).json({ error: '获取历史失败: ' + err.message });
    }
});

// 2. 删除特定批注记录
router.delete('/annotation/:id', authMiddleware, async (req, res) => {
    try {
        await db.run('DELETE FROM annotations WHERE id = ?', [req.params.id]);
        res.json({ success: true, message: '批注记录已抹除' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 3. 删除造字记录
router.delete('/character/:id', authMiddleware, async (req, res) => {
    try {
        await db.run('DELETE FROM custom_characters WHERE id = ?', [req.params.id]);
        res.json({ success: true, message: '造字记录已抹除' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

module.exports = router;