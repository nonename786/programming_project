const express = require('express');
const db = require('../config/database');
const authMiddleware = require('../middleware/auth');
const router = express.Router();

// 辅助函数：防止文本中的特殊字符破坏 XML 结构
function escapeXml(unsafe) {
    if (!unsafe) return '';
    return unsafe.toString().replace(/[<>&'"]/g, function (c) {
        switch (c) {
            case '<': return '&lt;';
            case '>': return '&gt;';
            case '&': return '&amp;';
            case '\'': return '&apos;';
            case '"': return '&quot;';
        }
    });
}

// 导出全库 XML 接口
router.get('/all', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;

        // 1. 获取该用户的所有卷宗 (documents)
        const docs = await db.all('SELECT * FROM documents WHERE user_id = ? ORDER BY created_at ASC', [userId]);
        
        // 2. 获取该用户的所有批注 (关联查询)
        const annotations = await db.all(`
            SELECT a.*, d.title as doc_title 
            FROM annotations a 
            JOIN documents d ON a.document_id = d.id 
            WHERE d.user_id = ? 
            ORDER BY a.document_id, a.page_number ASC`, [userId]);

        // 3. 获取该用户的所有造字
        const characters = await db.all('SELECT * FROM custom_characters WHERE user_id = ? ORDER BY created_at ASC',[userId]);

        // 4. 开始组装 XML 字符串
        let xml = `<?xml version="1.0" encoding="UTF-8"?>\n`;
        xml += `<古籍编纂系统_全库档案>\n`;

        // ================= 卷宗与批注部分 =================
        xml += `  <卷宗列表>\n`;
        for (const doc of docs) {
            xml += `    <卷宗 卷名="${escapeXml(doc.title)}" 载入时间="${new Date(doc.created_at).toLocaleString()}">\n`;
            
            // 筛选出属于这个卷宗的所有批注
            const docAnns = annotations.filter(a => a.document_id === doc.id);
            for (const ann of docAnns) {
                xml += `      <批注 页码="${ann.page_number}" 状态="${escapeXml(ann.status)}" 体例="${escapeXml(ann.mark_type)}">\n`;
                xml += `        <原文>${escapeXml(ann.original_text)}</原文>\n`;
                xml += `        <简体>${escapeXml(ann.simplified_text)}</简体>\n`;
                xml += `        <字义>${escapeXml(ann.meaning)}</字义>\n`;
                xml += `        <注解>${escapeXml(ann.notes)}</注解>\n`;
                xml += `        <名师讲解>${escapeXml(ann.ai_analysis)}</名师讲解>\n`;
                // 图片数据过大，使用 CDATA 标签包裹防止解析错误
                if (ann.image_data) {
                    xml += `        <截图数据><![CDATA[${ann.image_data}]]></截图数据>\n`;
                }
                xml += `      </批注>\n`;
            }
            xml += `    </卷宗>\n`;
        }
        xml += `  </卷宗列表>\n`;

        // ================= 异体造字部分 =================
        xml += `  <异体造字库>\n`;
        for (const char of characters) {
            xml += `    <造字记录>\n`;
            xml += `      <暂定字符名>${escapeXml(char.character_name)}</暂定字符名>\n`;
            xml += `      <分配编码>${escapeXml(char.unicode_code)}</分配编码>\n`;
            xml += `      <描述释义>${escapeXml(char.description)}</描述释义>\n`;
            if (char.image_data) {
                xml += `      <字形图像数据><![CDATA[${char.image_data}]]></字形图像数据>\n`;
            }
            xml += `    </造字记录>\n`;
        }
        xml += `  </异体造字库>\n`;

        xml += `</古籍编纂系统_全库档案>`;

        // 5. 设置响应头，告知浏览器这是一个需要下载的 XML 文件
        res.setHeader('Content-Type', 'application/xml');
        res.setHeader('Content-Disposition', `attachment; filename="database_export_${Date.now()}.xml"`);
        
        // 发送文件内容
        res.send(xml);

    } catch (err) {
        console.error("XML导出失败:", err);
        res.status(500).json({ error: '导出生成失败' });
    }
});

module.exports = router;