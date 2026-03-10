/**
 * WhatsApp Authentication Script
 * Run this ONCE locally to scan the QR code and save the session.
 * Usage: cd whatsapp && npm install && node auth.js
 */
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './session' }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ],
    },
});

client.on('qr', (qr) => {
    console.log('\n📱 Scan this QR code with WhatsApp on your phone:\n');
    qrcode.generate(qr, { small: true });
    console.log('\nOpen WhatsApp → Settings → Linked Devices → Link a Device\n');
});

client.on('ready', () => {
    console.log('\n✅ WhatsApp authenticated successfully!');
    console.log('📁 Session saved to ./session/');
    console.log('   You can now deploy this session for automated messaging.\n');
    process.exit(0);
});

client.on('auth_failure', (msg) => {
    console.error('❌ Authentication failed:', msg);
    process.exit(1);
});

console.log('🔄 Initializing WhatsApp Web...\n');
client.initialize();
