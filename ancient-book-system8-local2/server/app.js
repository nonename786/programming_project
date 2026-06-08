const express = require('express');
const cors = require('cors');
const path = require('path');
const multer = require('multer');
const fs = require('fs');
require('dotenv').config();

const app = express();

// ============ 中间件配置 ============
app.use(cors());
app.use(express.json({ limit: '200mb' }));
app.use(express.urlencoded({ limit: '200mb', extended: true }));
app.use(express.static(path.join(__dirname, '../public')));
// 在其他路由引入处添加
const ocrRoutes = require('./routes/ocr');

// 在 app.use 区域添加
app.use('/api/ocr', ocrRoutes);
app.use('/api/ocr', require('./routes/ocr'));
app.use('/api/qwen',require('./routes/qwen'));
app.use('/api/history', require('./routes/history'));
const os = require('os'); // 这是 Node.js 内置模块，不需要安装

// 新增接口：获取服务器当前的局域网真实 IP
app.get('/api/server-ip', (req, res) => {
    const interfaces = os.networkInterfaces();
    let ipAddress = null;

    // 遍历电脑上所有的网卡
    for (const devName in interfaces) {
        const iface = interfaces[devName];
        for (let i = 0; i < iface.length; i++) {
            const alias = iface[i];
            // 排除本地回环地址 (127.0.0.1) 和 IPv6，找到真正的 IPv4 地址
            if (alias.family === 'IPv4' && alias.address !== '127.0.0.1' && !alias.internal) {
                ipAddress = alias.address;
                break;
            }
        }
        if (ipAddress) break;
    }
    
    res.json({ ip: ipAddress || '127.0.0.1' });
});
// ============ 上传文件配置 ============
const uploadDir = path.join(__dirname, 'uploads');
const docsDir = path.join(uploadDir, 'documents');
const charsDir = path.join(uploadDir, 'characters');
const exportsDir = path.join(uploadDir, 'exports');

[uploadDir, docsDir, charsDir, exportsDir].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// Multer 配置
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const type = req.query.type || 'documents';
    const targetDir = type === 'character' ? charsDir : docsDir;
    cb(null, targetDir);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    const ext = path.extname(file.originalname);
    cb(null, uniqueSuffix + ext);
  }
});

const upload = multer({
  storage,
  fileFilter: (req, file, cb) => {
    const type = req.query.type || 'documents';
    let allowedMimes;

    if (type === 'character') {
      allowedMimes = ['image/jpeg', 'image/png', 'image/gif'];
    } else {
      allowedMimes = ['image/jpeg', 'image/png', 'application/pdf'];
    }

    if (allowedMimes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error(`只支持 ${allowedMimes.join(',')} 格式`));
    }
  },
  limits: { fileSize: 100 * 1024 * 1024 }
});

// ============ 路由导入 ============
const authRoutes = require('./routes/auth');
const uploadRoutes = require('./routes/upload');
const annotationRoutes = require('./routes/annotations');
const characterRoutes = require('./routes/characters');
const exportRoutes = require('./routes/export');
const collaborationRoutes = require('./routes/collaboration'); 

// ============ API 路由 ============
app.use('/api/auth', authRoutes);
app.use('/api/upload', upload.single('file'), uploadRoutes);
app.use('/api/annotations', annotationRoutes);
app.use('/api/characters', characterRoutes);
app.use('/api/export', exportRoutes);
app.use('/api/collaboration', collaborationRoutes); 
// ============ 错误处理 ============
app.use((err, req, res, next) => {
  console.error('❌ 错误:', err);
  res.status(500).json({
    error: err.message || '服务器错误',
    details: process.env.NODE_ENV === 'development' ? err.stack : undefined
  });
});

// ============ 404 处理 ============
app.use((req, res) => {
  res.status(404).json({ error: '请求的资源不存在' });
});

// ============ 启动服务器 ============
const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════╗
║   🎭 古籍检索系统                      ║
║   📜 运行在 http://localhost:${PORT}   ║
║   🔗 API: http://localhost:${PORT}/api  ║
╚════════════════════════════════════════╝
  `);
  console.log('📝 环境:', process.env.NODE_ENV);
  console.log('📁 上传目录:', uploadDir);
  console.log('🗄️  数据库:', process.env.DB_NAME);
});

module.exports = app;
