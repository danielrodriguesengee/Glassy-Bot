process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";


const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, jidNormalizedUser } = require('baileys');



const qrcode = require('qrcode-terminal');



const express = require('express');



const axios = require('axios');



const pino = require('pino');



const fs = require('fs');







const logger = pino({



  transport: {



    targets: [



      { target: 'pino/file', level: 'info' },



      { target: 'pino/file', level: 'info', options: { destination: './gateway.log' } }



    ]



  }



});







const API_WEBHOOK_URL = process.env.API_WEBHOOK_URL || 'http://localhost:5000/webhook';



const GATEWAY_PORT = 3000;







const limitationMessage = "Olá! Eu sou a Glassy, uma assistente virtual. No momento, eu não consigo processar áudios, imagens, vídeos ou ligações. Por favor, envie sua solicitação em formato de texto. 😉";







const app = express();



app.use(express.json({ limit: '50mb' }));







let sock;



let reconnectInterval;







// --- AJUSTE CRÍTICO APLICADO AQUI: ROTA DE ENVIO COM PRÉ-VERIFICAÇÃO ---



app.post('/send-message', async (req, res) => {



    const { to, text, mediaData, fileName } = req.body;



    if (!sock) {



        return res.status(500).json({ status: 'error', message: 'WhatsApp não está conectado' });



    }



    if (!to || (!text && !mediaData)) {



        return res.status(400).json({ status: 'error', message: 'Pedido incompleto' });



    }



    try {



        const number = to.split('@')[0];



        



        // 1. Pré-verifica se o número existe no WhatsApp



        const [result] = await sock.onWhatsApp(number);







        if (result?.exists) {



            const verifiedJid = result.jid; // Usa o JID verificado retornado pelo WhatsApp







            // 2. Envia a mensagem usando o JID verificado



            if (mediaData && fileName) {



                const message = {



                    document: Buffer.from(mediaData, 'base64'),



                    fileName: fileName,



                    caption: text || ''



                };



                await sock.sendMessage(verifiedJid, message);



                res.status(200).json({ status: 'success', message: 'Mídia enviada' });



            } else {



                await sock.sendMessage(verifiedJid, { text: text });



                res.status(200).json({ status: 'success', message: 'Texto enviado' });



            }



        } else {



            logger.error(`[Gateway] Falha ao enviar: Número ${number} não existe no WhatsApp.`);



            res.status(404).json({ status: 'error', message: `Número ${number} não encontrado no WhatsApp` });



        }



    } catch (err) {



        logger.error(err, 'Falha ao enviar mensagem via /send-message');



        res.status(500).json({ status: 'error', message: 'Falha interna do gateway' });



    }



});



// --- FIM DO AJUSTE ---







async function connectToWhatsApp() {



    if (sock) {



        try {



            sock.end(undefined);



        } catch(e) {



            logger.warn('Erro ao encerrar a instância anterior do socket, pode ser ignorado:', e.message);



        }



    }



    if (reconnectInterval) {



        clearInterval(reconnectInterval);



        reconnectInterval = null;



    }







    const { state, saveCreds } = await useMultiFileAuthState('session');



    



    sock = makeWASocket({



        auth: state,



        logger: pino({ level: 'silent' })



    });







    sock.ws.on('CB:call', async (node) => {



        const callNode = node.content[0];



        if (callNode.tag === 'offer') {



            const callFrom = jidNormalizedUser(callNode.attrs['from']);



            if (callFrom) {



                logger.info(`[Gateway] Chamada recebida de ${callFrom}. Enviando aviso.`);



                await sock.sendMessage(callFrom, { text: limitationMessage });



            } else {



                logger.warn('[Gateway] Chamada recebida de número desconhecido/privado. Ignorando.');



            }



        }



    });







    sock.ev.on('connection.update', (update) => {



        const { connection, lastDisconnect, qr } = update;







        if (qr) {



            logger.info('QR Code recebido, escaneie com seu celular:');



            qrcode.generate(qr, { small: true });



        }







        if (connection === 'close') {



            const reason = lastDisconnect?.error?.output?.statusCode;







            if (reason === DisconnectReason.loggedOut) {



                logger.warn('❌ Sessão inválida (loggedOut). Apagando credenciais e reiniciando para gerar novo QR...');



                if (fs.existsSync('./session')) {



                    fs.rmSync('./session', { recursive: true, force: true });



                }



                connectToWhatsApp();



            } 



            else if (reason === DisconnectReason.restartRequired || reason === 515) {



                logger.warn(`⚠️ Servidor solicitou reinicialização (código ${reason}). Aguardando 15s antes de tentar novamente...`);



                setTimeout(connectToWhatsApp, 15000);



            }



            else {



                logger.error({ error: lastDisconnect?.error }, `Conexão fechada, motivo: ${reason}. Iniciando ciclo de reconexão a cada 1 min...`);



                reconnectInterval = setInterval(connectToWhatsApp, 60 * 1000);



            }



        } else if (connection === 'open') {



            logger.info('✅ WhatsApp conectado!');



            if (reconnectInterval) {



                clearInterval(reconnectInterval);



                reconnectInterval = null;



            }



        }



    });



    



    sock.ev.on('messages.upsert', async (m) => {



        const msg = m.messages[0];



        const userId = msg.key.remoteJid;







        if (!msg.message || userId === 'status@broadcast' || userId.endsWith('@g.us')) {



            return;



        }







        const messageContent = msg.message;



        const messageText = (messageContent.conversation || messageContent.extendedTextMessage?.text || "").toLowerCase().trim();







        if (messageText === '#pausarbot' || messageText === '#reativarbot') {



            const sender = msg.key.fromMe ? "Atendente" : "Cliente";



            logger.info(`[Gateway] Comando '${messageText}' detectado do ${sender} na conversa ${userId}`);



            try {



                await axios.post(API_WEBHOOK_URL, { userId: userId, message: messageText });



            } catch (e) {



                logger.error(`[Gateway] Falha ao enviar comando '${messageText}' para a API.`);



            }



            return;



        }







        if (msg.key.fromMe) return;







        try {



            const stateResponse = await axios.post(`${API_WEBHOOK_URL.replace('/webhook', '')}/check-state`, { userId: userId });



            if (stateResponse.data.state === "HUMAN_ATTENDANCE") {



                logger.info(`[Gateway] Mensagem de ${userId} ignorada (Modo Humano).`);



                return;



            }







            const isMedia = messageContent.imageMessage || messageContent.videoMessage || messageContent.audioMessage || messageContent.stickerMessage || messageContent.documentMessage;



            if (isMedia) {



                logger.info(`[Gateway] Mídia recebida de ${userId}. Enviando aviso.`);



                await sock.sendMessage(userId, { text: limitationMessage });



                return;



            }







            if (!messageText) return;







            await sock.sendPresenceUpdate('composing', userId);



            logger.info(`[Gateway] Mensagem recebida de ${userId}: "${messageText}"`);



            await axios.post(API_WEBHOOK_URL, { userId: userId, message: messageText });



        } catch (error) {



            if (error.response) {



                logger.error(`[Gateway] Erro ao comunicar com a API: ${error.response.status} - ${JSON.stringify(error.response.data)}`);



            } else if (error.request) {



                logger.error(`[Gateway] ERRO CRÍTICO: Não foi possível conectar à API em ${API_WEBHOOK_URL}. A API Python está rodando?`);



            } else {



                logger.error(error, `[Gateway] Erro ao processar mensagem de ${userId}`);



            }



        }



    });







    sock.ev.on('creds.update', saveCreds);



}







app.listen(GATEWAY_PORT, () => {



    logger.info(`📡 Gateway escutando na porta ${GATEWAY_PORT}.`);



    connectToWhatsApp();



});


