const express = require('express');
const router = express.Router();
const db = require('../config/database');
const authMiddleware = require('../middleware/auth');

// 初始化协作邀请表
const initInvitesTable = async () => {
    try {
        await db.run(`
            CREATE TABLE IF NOT EXISTS invitations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT,
                receiver_id INT,
                document_id INT,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        `);
    } catch (e) { console.error("初始化邀请表失败:", e); }
};
initInvitesTable();

// 1. 获取协作文档的详细信息（允许公开通过链接读取）
router.get('/access/:docId', async (req, res) => {
    try {
        const doc = await db.get('SELECT * FROM documents WHERE id = ?', [req.params.docId]);
        if (!doc) return res.status(404).json({ error: '找不到该卷宗' });
        res.json(doc);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 2. 通过用户名发送邀请
router.post('/invite', authMiddleware, async (req, res) => {
    try {
        const { username, document_id } = req.body;
        // 查找接收者
        const receiver = await db.get('SELECT id FROM users WHERE username = ?', [username]);
        if (!receiver) return res.status(404).json({ error: '找不到该户籍名号，请核对。' });
        if (receiver.id === req.userId) return res.status(400).json({ error: '不可邀请自己。' });

        // 插入邀请记录
        await db.run('INSERT INTO invitations (sender_id, receiver_id, document_id) VALUES (?, ?, ?)', 
            [req.userId, receiver.id, document_id]);
        res.json({ success: true, message: '飞鸽传书已送达！' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 3. 获取我的待办信件
router.get('/my-invites', authMiddleware, async (req, res) => {
    try {
        // 联合查询发送者名字和文档名字
        const sql = `
            SELECT i.id, i.status, i.created_at, u.username as sender_name, d.title as doc_title, d.id as doc_id
            FROM invitations i
            JOIN users u ON i.sender_id = u.id
            JOIN documents d ON i.document_id = d.id
            WHERE i.receiver_id = ? AND i.status = 'pending'
            ORDER BY i.created_at DESC
        `;
        const invites = await db.all(sql,[req.userId]);
        res.json(invites);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// 4. 接受邀请
router.post('/accept/:id', authMiddleware, async (req, res) => {
    try {
        await db.run("UPDATE invitations SET status = 'accepted' WHERE id = ?",[req.params.id]);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

module.exports = router;