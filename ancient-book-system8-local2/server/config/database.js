const mysql = require('mysql2/promise');
require('dotenv').config();

// 创建连接池
const pool = mysql.createPool({
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'ancient_book_db',
  port: process.env.DB_PORT || 3306,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
  enableKeepAlive: true,
  keepAliveInitialDelayMs: 0,
  supportBigNumbers: true,
  bigNumberStrings: true,
  charset: 'utf8mb4'
});

// 测试连接
pool.getConnection()
  .then(connection => {
    console.log('✅ MySQL 数据库连接成功');
    connection.release();
  })
  .catch(err => {
    console.error('❌ MySQL 数据库连接失败:');
    console.error('   错误信息:', err.message);
    console.error('   请检查以下配置:');
    console.error(`   - DB_HOST: ${process.env.DB_HOST}`);
    console.error(`   - DB_USER: ${process.env.DB_USER}`);
    console.error(`   - DB_PORT: ${process.env.DB_PORT}`);
    console.error(`   - DB_NAME: ${process.env.DB_NAME}`);
  });

// 数据库操作包装器
const db = {
  // 执行单条SQL
  run: async (sql, params = []) => {
    let connection;
    try {
      connection = await pool.getConnection();
      const [result] = await connection.execute(sql, params);
      return {
        id: result.insertId,
        changes: result.affectedRows,
        result
      };
    } catch (error) {
      console.error('❌ 执行SQL出错:', sql);
      console.error('   参数:', params);
      console.error('   错误:', error.message);
      throw error;
    } finally {
      if (connection) connection.release();
    }
  },

  // 获取单条记录
  get: async (sql, params = []) => {
    let connection;
    try {
      connection = await pool.getConnection();
      const [rows] = await connection.execute(sql, params);
      return rows[0] || null;
    } catch (error) {
      console.error('❌ 查询出错:', sql);
      console.error('   参数:', params);
      throw error;
    } finally {
      if (connection) connection.release();
    }
  },

  // 获取多条记录
  all: async (sql, params = []) => {
    let connection;
    try {
      connection = await pool.getConnection();
      const [rows] = await connection.execute(sql, params);
      return rows || [];
    } catch (error) {
      console.error('❌ 查询出错:', sql);
      console.error('   参数:', params);
      throw error;
    } finally {
      if (connection) connection.release();
    }
  },

  // 执行事务
  transaction: async (callback) => {
    let connection;
    try {
      connection = await pool.getConnection();
      await connection.beginTransaction();
      const result = await callback(connection);
      await connection.commit();
      return result;
    } catch (error) {
      if (connection) await connection.rollback();
      throw error;
    } finally {
      if (connection) connection.release();
    }
  },

  // 关闭连接池
  close: async () => {
    await pool.end();
  }
};

module.exports = db;
