const express = require('express');
const axios = require('axios');
const router = express.Router();
const authMiddleware = require('../middleware/auth');

// 通义千问视觉识别接口
router.post('/ai-recognize', authMiddleware, async (req, res) => {
    try {
        let { image } = req.body; // 接收 base64 字符串

        if (!image) return res.status(400).json({ error: '未接收到图片数据' });

        // 确保 Base64 带有正确的 MIME 前缀
        if (!image.startsWith('data:')) {
            image = `data:image/jpeg;base64,${image}`;
        }

        const requestData = {
            model: process.env.QWEN_VL_MODEL || "qwen-vl-max",
            messages: [
                {
                    role: "user",
                    content: [
                        {
                            type: "text",
                            text: "你是一位精通中国古籍的专家。请识别图片中的文字内容。要求：1. 将繁体字转化为简体中文输出。2. 保持古籍原本的阅读顺序（竖排从右往左），并且根据语义句读，断句，就是可以在合适的位置输出句号逗号。3. 直接输出识别后的正文，不要有任何开场白或解释。但如果图片不是文字，而是一个动物的话，请你分析一下他的特点和来源，并输出"
                        },
                        {
                            type: "image_url",
                            image_url: { "url": image }
                        }
                    ]
                }
            ]
        };

        // 调用阿里云接口
        const response = await axios.post(process.env.QWEN_API_URL, requestData, {
            headers: {
                'Authorization': `Bearer ${process.env.QWEN_API_KEY.trim()}`,
                'Content-Type': 'application/json'
            },
            timeout: 60000 // 视觉识别通常需要 10-20 秒，设置 60 秒超时
        });

        if (response.data && response.data.choices && response.data.choices[0]) {
            const resultText = response.data.choices[0].message.content;
            res.json({ text: resultText });
        } else {
            throw new Error('通义千问接口返回异常');
        }

    } catch (error) {
        console.error('Qwen-VL 识别报错:', error.response?.data || error.message);
        res.status(500).json({ 
            error: 'AI 识读失败', 
            details: error.response?.data?.error?.message || error.message 
        });
    }
});

module.exports = router;