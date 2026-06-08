const express = require('express');
const db = require('../config/database');
const authMiddleware = require('../middleware/auth');
const router = express.Router();

router.post('/', authMiddleware, async (req, res) => {
  try {
    // 【修改点 1】：在解构赋值中，接收前端传来的 image_data
    const { 
        document_id, page_number, mark_type, mark_color, 
        original_text, simplified_text, meaning, notes, 
        ai_analysis, coordinates, status, image_data 
    } = req.body;

    // 【修改点 2】：将其加入安全检查数组中（如果没有传，则默认存入 null）
    const safeData =[
        document_id || null,
        page_number || 1,
        mark_type || '字',
        mark_color || '#8b2929',
        original_text || '',
        simplified_text || '',
        meaning || '',
        notes || '',
        ai_analysis || '',
        coordinates || '{}',
        status || '待审',
        image_data || null  // <--- 新增在这里
    ];

    // 【修改点 3】：在 SQL 语句的字段列表和 VALUES 中各加一个位置
    // 注意：最后多了一个 image_data 字段，以及对应的占位符 ?
    const sql = `INSERT INTO annotations 
      (document_id, page_number, mark_type, mark_color, original_text, simplified_text, meaning, notes, ai_analysis, coordinates, status, image_data) 
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`;

    const result = await db.run(sql, safeData);
    res.json({ success: true, id: result.id });
  } catch (err) {
    console.error("后端数据库操作失败:", err.message);
    res.status(500).json({ error: err.message });
  }
});

// 获取某文档的所有标注
router.get('/:document_id', authMiddleware, async (req, res) => {
  try {
    const annotations = await db.all('SELECT * FROM annotations WHERE document_id = ?',[req.params.document_id]);
    res.json(annotations);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});
// --- 【新增】：精确获取某文档特定页码的所有批注 ---
router.get('/:document_id/page/:page_number', authMiddleware, async (req, res) => {
    try {
        const { document_id, page_number } = req.params;
        
        // 使用 document_id 和 page_number 双重条件进行精准筛选
        const sql = `SELECT * FROM annotations WHERE document_id = ? AND page_number = ?`;
        const annotations = await db.all(sql, [document_id, page_number]);
        
        res.json({
            success: true,
            data: annotations,
            message: `成功获取第 ${page_number} 页的批注记录`
        });
    } catch (err) {
        console.error("分页获取批注失败:", err.message);
        res.status(500).json({ error: '获取本页批注数据失败' });
    }
});
module.exports = router;