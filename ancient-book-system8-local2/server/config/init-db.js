const mysql = require('mysql2/promise');
require('dotenv').config();
const fs = require('fs');
const path = require('path');

const initializeDatabase = async () => {
  try {
    // 连接到 MySQL 服务器（不指定数据库）
    const connection = await mysql.createConnection({
      host: process.env.DB_HOST,
      user: process.env.DB_USER,
      password: process.env.DB_PASSWORD,
      multipleStatements: true
    });

    console.log('🔌 连接到 MySQL 服务器成功');

    // 读取 SQL 文件
    const sqlPath = path.join(__dirname, '../../mysql-setup.sql');
    const sql = fs.readFileSync(sqlPath, 'utf-8');

    // 执行 SQL
    await connection.query(sql);
    console.log('✅ 数据库和表初始化成功');

    await connection.end();
  } catch (error) {
    console.error('❌ 数据库初始化失败:');
    console.error('   错误信息:', error.message);
    process.exit(1);
  }
};

// 直接执行
if (require.main === module) {
  initializeDatabase();
}

module.exports = initializeDatabase;
