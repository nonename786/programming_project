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