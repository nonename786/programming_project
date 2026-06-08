const express = require('express');
const db = require('../config/database');
const authMiddleware = require('../middleware/auth');
const router = express.Router();

router.post('/', authMiddleware, async (req, res) => {
  try {
    // 接收原有的 character_image 字段
    const { unicode_code, character_name, description, character_image } = req.body;
    
    // 插入数据库（完美保留原有的 character_image 列名）
    const result = await db.run(
      `INSERT INTO custom_characters (user_id, unicode_code, character_name, description, character_image) 
       VALUES (?, ?, ?, ?, ?)`,[req.userId, unicode_code, character_name, description, character_image || null]
    );
    
    res.json({ success: true, id: result.id, message: '造字成功' });
  } catch (err) {
    console.error("造字入库失败:", err.message);
    res.status(500).json({ error: err.message });
  }
});

// 【核心修复】：必须放在文件最底端，否则路由会报 404
module.exports = router;