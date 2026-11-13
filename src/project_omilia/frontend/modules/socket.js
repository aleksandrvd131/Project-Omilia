/**
 * Project Omiλia — WebSocket Module
 * Управление WebSocket соединением, повторными попытками и отправкой кадров.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Omilia = root.Omilia || {};
    root.Omilia.Socket = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  let ws = null;
  let isWsBusy = false;
  let wsTimeout = null;
  let lastSendTime = 0;

  function ensureWebSocket(options = {}) {
    const {
      authToken = null,
      onMessage = null,
      onError = null,
      onClose = null,
      onOpen = null,
    } = options;

    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return ws;
    }

    const proto = (typeof window !== 'undefined' && window.location?.protocol === 'https:') ? 'wss:' : 'ws:';
    const host = (typeof window !== 'undefined' && window.location?.host) ? window.location.host : 'localhost:8000';
    const token = authToken || (typeof localStorage !== 'undefined' ? localStorage.getItem('omilia_token') : null) || '';
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const wsUrl = `${proto}//${host}/ws/gestures${tokenParam}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = (event) => {
      console.log('[WebSocket] Соединение установлено');
      if (onOpen) onOpen(event);
    };

    ws.onmessage = (event) => {
      isWsBusy = false;
      if (wsTimeout) {
        clearTimeout(wsTimeout);
        wsTimeout = null;
      }
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch (err) {
        console.warn('Ошибка парсинга WebSocket сообщения:', err);
      }
    };

    ws.onerror = (err) => {
      isWsBusy = false;
      console.error('[WebSocket] Ошибка:', err);
      if (onError) onError(err);
    };

    ws.onclose = (event) => {
      isWsBusy = false;
      console.log('[WebSocket] Соединение закрыто');
      if (onClose) onClose(event);
    };

    return ws;
  }

  function sendPayload(payload, throttleMs = 41) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    const now = (typeof performance !== 'undefined') ? performance.now() : Date.now();
    if (isWsBusy || (now - lastSendTime < throttleMs)) {
      return false;
    }
    isWsBusy = true;
    lastSendTime = now;
    if (wsTimeout) clearTimeout(wsTimeout);
    wsTimeout = setTimeout(() => { isWsBusy = false; }, 350);

    ws.send(JSON.stringify(payload));
    return true;
  }

  function sendRaw(payload) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(typeof payload === 'string' ? payload : JSON.stringify(payload));
    return true;
  }

  function close() {
    if (ws) {
      ws.close();
      ws = null;
    }
    isWsBusy = false;
    if (wsTimeout) {
      clearTimeout(wsTimeout);
      wsTimeout = null;
    }
  }

  function isOpen() {
    return Boolean(ws && ws.readyState === WebSocket.OPEN);
  }

  function getSocket() {
    return ws;
  }

  function resetBusy() {
    isWsBusy = false;
    if (wsTimeout) {
      clearTimeout(wsTimeout);
      wsTimeout = null;
    }
  }

  return {
    ensureWebSocket,
    sendPayload,
    sendRaw,
    close,
    isOpen,
    getSocket,
    resetBusy,
  };
});
