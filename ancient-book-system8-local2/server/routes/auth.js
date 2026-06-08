const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../config/database');
const router = express.Router();

const JWT_SECRET = process.env.JWT_SECRET;
//定义路由，编写API接口
// 注册
router.post('/register', async (req, res) => {
  try {
    //解构赋值
    const { username, email, password, confirmPassword } = req.body;

    // 验证输入
    if (!username || !email || !password) {
      return res.status(400).json({ error: '请填写所有字段' });
    }

    if (password !== confirmPassword) {
      return res.status(400).json({ error: '两次密码不一致' });
    }

    if (password.length < 6) {
      return res.status(400).json({ error: '密码至少6位' });
    }

    // 检查用户是否已存在
    const existingUser = await db.get(
      'SELECT * FROM users WHERE username = ? OR email = ?',
      [username, email]
    );

    if (existingUser) {
      return res.status(400).json({ 
        error: existingUser.username === username ? '用户名已存在' : '邮箱已存在' 
      });
    }

    // 密码加密
    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);

    // 创建用户
    const result = await db.run(
      'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
      [username, email, hashedPassword]
    );

    // 生成 token
    const token = jwt.sign(
      { userId: result.id, username },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    res.status(201).json({
      message: '注册成功',
      token,
      user: { id: result.id, username, email }
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: '注册失败: ' + err.message });
  }
});

// 登录
router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ error: '请填写用户名和密码' });
    }

    const user = await db.get('SELECT * FROM users WHERE username = ?', [username]);

    if (!user) {
      return res.status(400).json({ error: '用户不存在' });
    }

    const isPasswordValid = await bcrypt.compare(password, user.password);

    if (!isPasswordValid) {
      return res.status(400).json({ error: '密码错误' });
    }

    const token = jwt.sign(
      { userId: user.id, username: user.username },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    res.json({
      message: '登录成功',
      token,
      user: { id: user.id, username: user.username, email: user.email }
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: '登录失败: ' + err.message });
  }
});

// 验证 token
router.post('/verify', (req, res) => {
  try {
    const token = req.headers.authorization?.split(' ')[1];

    if (!token) {
      return res.status(401).json({ valid: false, error: 'Token缺失' });
    }

    const decoded = jwt.verify(token, JWT_SECRET);
    res.json({ valid: true, user: decoded });
  } catch (err) {
    res.status(401).json({ valid: false, error: 'Token无效或已过期' });
  }
});

module.exports = router;
