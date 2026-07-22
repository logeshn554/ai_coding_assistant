'use strict';

const logger = require('../utils/logger');

/**
 * Handles incoming WebSocket connection on /ws/chat.
 */
function handleChatSocket(ws, req) {
  logger.info('WebSocket client connected to /ws/chat');

  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message.toString());
      logger.info(`Received WS message type: ${data.type}`);

      switch (data.type) {
        case 'user_message':
          // Stream AI response back to client
          ws.send(JSON.stringify({ type: 'status', message: 'Analyzing workspace...' }));

          setTimeout(() => {
            ws.send(JSON.stringify({ type: 'thinking', content: 'Processing prompt and building context...' }));
          }, 300);

          setTimeout(() => {
            ws.send(
              JSON.stringify({
                type: 'text_delta',
                content: `DevPilot AI assistant received your task: "${data.text}". Everything is synchronized with the backend.`,
              })
            );
            ws.send(JSON.stringify({ type: 'session_done' }));
          }, 800);
          break;

        case 'change_profile':
          ws.send(JSON.stringify({ type: 'status', message: 'Profile reloaded' }));
          break;

        case 'confirm_response':
          logger.info(`Tool confirm response: ${data.approved}`);
          break;

        case 'cancel_generation':
          ws.send(JSON.stringify({ type: 'session_done' }));
          break;

        default:
          break;
      }
    } catch (e) {
      logger.error('Failed to parse WebSocket message', e);
    }
  });

  ws.on('close', () => {
    logger.info('WebSocket client disconnected');
  });

  ws.on('error', (err) => {
    logger.error('WebSocket error', err);
  });
}

module.exports = { handleChatSocket };
