const express = require('express');
const axios = require('axios');
const router = express.Router();
const authMiddleware = require('../middleware/auth');

router.post('/analyze', authMiddleware, async (req, res) => {
    try {
        const { text } = req.body;
        const response = await axios.post(process.env.QWEN_API_URL, {
            model: "qwen-plus", // 或 qwen-plus
            messages: [
                { role: "system", content: "你是一位精通国学的博学导师。请对用户提供的古籍片段进行：1. 译文（优雅的现代汉语）；2. 历史背景（涉及的人物、年代或典故）；3. 文学赏析（微言大义）。4.进行划分，断句，将原文断句后的结果生成出来。5.对于不全的部分，你可以考虑自动补充。 请用美观的排版输出，分成这五个板块输出。希望你较快的输出一下" },
                { role: "user", content: `请解析以下内容：${text}` }
            ]
        }, {
            headers: { 'Authorization': `Bearer ${process.env.QWEN_API_KEY}`, 'Content-Type': 'application/json' }
        });

        res.json({ analysis: response.data.choices[0].message.content });
    } catch (error) {
        res.status(500).json({ error: "通义千问解析失败" });
    }
});

module.exports = router;