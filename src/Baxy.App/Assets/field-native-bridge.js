(() => {
  'use strict';

  const CHANNEL = 'baxy.field.v1';
  const pending = new Map();
  const sockets = new Map();
  let sequence = 0;

  function nextId(prefix) {
    sequence += 1;
    return `${prefix}-${Date.now().toString(36)}-${sequence.toString(36)}`;
  }

  function post(kind, payload) {
    window.chrome.webview.postMessage({ channel: CHANNEL, kind, ...payload });
  }

  function rpc(kind, payload = {}) {
    const id = nextId('rpc');
    return new Promise((resolve, reject) => {
      const timeout = window.setTimeout(() => {
        pending.delete(id);
        reject(new Error(`BAXY native request timed out: ${kind}`));
      }, 30000);
      pending.set(id, { resolve, reject, timeout });
      post(kind, { id, ...payload });
    });
  }

  function completeReply(message) {
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    window.clearTimeout(request.timeout);
    if (message.ok) request.resolve(message.value);
    else request.reject(new Error(message.error || 'BAXY native request failed'));
  }

  class NativeWebSocket extends EventTarget {
    constructor(url) {
      super();
      this.url = String(url);
      this.protocol = '';
      this.extensions = '';
      this.binaryType = 'blob';
      this.bufferedAmount = 0;
      this.readyState = NativeWebSocket.CONNECTING;
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
      this._id = nextId('socket');
      sockets.set(this._id, this);
      post('socket_open', { socketId: this._id, url: this.url });
    }

    send() {
      if (this.readyState !== NativeWebSocket.OPEN) {
        throw new DOMException('WebSocket is not open', 'InvalidStateError');
      }
    }

    close(code = 1000, reason = '') {
      if (this.readyState === NativeWebSocket.CLOSED) return;
      this.readyState = NativeWebSocket.CLOSING;
      post('socket_close', { socketId: this._id, code, reason: String(reason) });
      this._close(code, String(reason));
    }

    _open() {
      if (this.readyState !== NativeWebSocket.CONNECTING) return;
      this.readyState = NativeWebSocket.OPEN;
      const event = new Event('open');
      this.dispatchEvent(event);
      if (typeof this.onopen === 'function') this.onopen(event);
    }

    _message(data) {
      if (this.readyState !== NativeWebSocket.OPEN) return;
      const event = new MessageEvent('message', { data });
      this.dispatchEvent(event);
      if (typeof this.onmessage === 'function') this.onmessage(event);
    }

    _close(code = 1000, reason = '') {
      if (this.readyState === NativeWebSocket.CLOSED) return;
      this.readyState = NativeWebSocket.CLOSED;
      sockets.delete(this._id);
      const event = new CloseEvent('close', { code, reason, wasClean: code === 1000 });
      this.dispatchEvent(event);
      if (typeof this.onclose === 'function') this.onclose(event);
    }
  }

  NativeWebSocket.CONNECTING = 0;
  NativeWebSocket.OPEN = 1;
  NativeWebSocket.CLOSING = 2;
  NativeWebSocket.CLOSED = 3;
  Object.assign(NativeWebSocket.prototype, {
    CONNECTING: 0,
    OPEN: 1,
    CLOSING: 2,
    CLOSED: 3,
  });

  window.chrome.webview.addEventListener('message', (event) => {
    const message = event.data;
    if (!message || message.channel !== CHANNEL) return;
    if (message.kind === 'reply') {
      completeReply(message);
      return;
    }
    if (message.kind !== 'socket_event') return;
    const socket = sockets.get(message.socketId);
    if (!socket) return;
    if (message.event === 'open') socket._open();
    else if (message.event === 'message') socket._message(message.data);
    else if (message.event === 'close') socket._close(message.code, message.reason);
  });

  window.fetch = async (input, init = {}) => {
    const requestUrl = typeof input === 'string' || input instanceof URL
      ? String(input)
      : String(input.url);
    const url = new URL(requestUrl, window.location.href);
    if (url.origin !== window.location.origin) {
      return new Response(JSON.stringify({ error: 'external_network_disabled' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const method = String(init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    let body = null;
    if (typeof init.body === 'string') body = init.body;
    else if (init.body != null) body = String(init.body);

    try {
      const value = await rpc('http', {
        method,
        path: `${url.pathname}${url.search}`,
        body,
      });
      return new Response(value.body || '', {
        status: value.status,
        headers: value.headers || { 'Content-Type': 'application/json' },
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: String(error) }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  };

  window.WebSocket = NativeWebSocket;
  window.pywebview = {
    api: {
      win_minimize: () => rpc('window_command', { command: 'minimize' }),
      win_toggle_maximize: () => rpc('window_command', { command: 'toggle_maximize' }),
      win_close: () => rpc('window_command', { command: 'close' }),
      win_is_maximized: () => rpc('window_command', { command: 'is_maximized' }),
    },
  };

  document.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    const target = event.target instanceof Element ? event.target : null;
    if (!target?.closest('.pywebview-drag-region')) return;
    post('window_drag', {});
  }, true);
})();
