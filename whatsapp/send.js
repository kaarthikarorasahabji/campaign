/**
 * WhatsApp Message Sender
 * Called by the Python campaign via subprocess.
 * 
 * Usage: node send.js <phone_number> <message>
 *   phone_number: full international format, e.g. 919876543210
 *   message: the text message to send
 * 
 * Output (JSON): { "success": true/false, "error": "..." }
 */
const { Client, LocalAuth } = require('whatsapp-web.js');

const phone = process.argv[2];
const message = process.argv[3];

if (!phone || !message) {
    console.log(JSON.stringify({ success: false, error: 'Usage: node send.js <phone> <message>' }));
    process.exit(1);
}

// Format phone number (remove + and spaces, ensure country code)
const formattedPhone = phone.replace(/[\s+\-()]/g, '');
const chatId = `${formattedPhone}@c.us`;

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './session' }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--single-process',
        ],
    },
});

let timeout = setTimeout(() => {
    console.log(JSON.stringify({ success: false, error: 'Timeout: WhatsApp client did not connect in 60s' }));
    process.exit(1);
}, 60000);

client.on('ready', async () => {
    clearTimeout(timeout);
    try {
        // Check if number is registered on WhatsApp
        const isRegistered = await client.isRegisteredUser(chatId);
        if (!isRegistered) {
            console.log(JSON.stringify({ success: false, error: `${formattedPhone} is not on WhatsApp` }));
            await client.destroy();
            process.exit(0);
        }

        // Send message
        await client.sendMessage(chatId, message);
        console.log(JSON.stringify({ success: true, phone: formattedPhone }));
        await client.destroy();
        process.exit(0);
    } catch (err) {
        console.log(JSON.stringify({ success: false, error: err.message }));
        await client.destroy();
        process.exit(1);
    }
});

client.on('auth_failure', (msg) => {
    clearTimeout(timeout);
    console.log(JSON.stringify({ success: false, error: `Auth failed: ${msg}. Run 'node auth.js' first.` }));
    process.exit(1);
});

client.initialize();
