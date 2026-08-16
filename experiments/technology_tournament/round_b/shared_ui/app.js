const log = document.querySelector('#conversation-log');
const form = document.querySelector('#composer');
const input = document.querySelector('#message-input');
const sendButton = document.querySelector('#send-button');
const progress = document.querySelector('#progress');
const progressTitle = document.querySelector('#progress-title');
const progressDetail = document.querySelector('#progress-detail');
const bridgeState = document.querySelector('#bridge-state');
const coreLabel = document.querySelector('#core-label');
const lastState = document.querySelector('#last-state');
const activity = document.querySelector('#activity-list');
const contrastButton = document.querySelector('#contrast-button');
const automationPanel = document.querySelector('#automation-panel');
const automationInvocation = document.querySelector('#automation-invocation');

const pendingWebView = new Map();
let busy = false;
let lastResponse = null;

function invocationId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return `ui-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function bridgeKind() {
  if (globalThis.__TAURI__?.core?.invoke) return 'Tauri + Rust';
  if (globalThis.chrome?.webview?.postMessage) return '.NET + WebView2';
  return 'Vista previa';
}

function updateBridgeState() {
  const kind = bridgeKind();
  const connected = kind !== 'Vista previa';
  bridgeState.className = `status-pill ${connected ? 'connected' : 'pending'}`;
  bridgeState.innerHTML = `<span aria-hidden="true"></span>${connected ? 'Core listo' : 'Vista previa'}`;
  coreLabel.textContent = kind;
}

async function configureAutomationMode() {
  let enabled = new URLSearchParams(globalThis.location.search).get('automation') === '1';
  if (!enabled && globalThis.__TAURI__?.core?.invoke) {
    try {
      const info = await globalThis.__TAURI__.core.invoke('runtime_info');
      enabled = info?.automation === true;
    } catch {
      enabled = false;
    }
  }
  automationPanel.hidden = !enabled;
}

function appendMessage(role, text, detail = '') {
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = role === 'user' ? 'TÚ' : 'B';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  bubble.append(paragraph);
  if (detail) {
    const small = document.createElement('small');
    small.textContent = detail;
    bubble.append(small);
  }
  article.append(avatar, bubble);
  log.append(article);
  log.scrollTop = log.scrollHeight;
}

function setProgress(title, detail) {
  progress.hidden = false;
  progressTitle.textContent = title;
  progressDetail.textContent = detail;
  lastState.className = 'mission-state working';
  lastState.textContent = title;
}

function renderActivity(response) {
  const operations = Array.isArray(response.operations) ? response.operations : [];
  const steps = [
    { state: 'done', title: 'Entendido', detail: `Intención: ${response.intent || 'desconocida'}` },
    ...operations.map((operation) => ({
      state: operation.state === 'done' ? 'done' : 'blocked',
      title: operation.operation || 'Operación',
      detail: operation.relative_path ? `Ruta local: ${operation.relative_path}` : 'Efecto local',
    })),
    {
      state: response.verification?.status === 'verified' ? 'done' : response.state,
      title: response.verification?.status === 'verified' ? 'Verificado' : 'Sin efecto verificable',
      detail: response.verification?.status === 'verified' ? 'El estado real coincide.' : 'BAXY no declaró un éxito falso.',
    },
  ];
  activity.replaceChildren();
  steps.forEach((step, index) => {
    const item = document.createElement('li');
    item.className = step.state;
    const number = document.createElement('span');
    number.textContent = step.state === 'done' ? '✓' : String(index + 1);
    const body = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = step.title;
    const detail = document.createElement('p');
    detail.textContent = step.detail;
    body.append(title, detail);
    item.append(number, body);
    activity.append(item);
  });
}

function demoSubmit(request) {
  const lowered = request.message.toLocaleLowerCase('es');
  const response = lowered.startsWith('hola')
    ? 'Estoy bien y lista para ayudarte.'
    : 'La vista previa está lista; abre uno de los shells para ejecutar y verificar la misión.';
  return Promise.resolve({
    schema_version: 1,
    invocation_id: request.invocation_id,
    mission_id: `preview-${request.invocation_id}`,
    state: lowered.startsWith('hola') ? 'done' : 'blocked',
    intent: lowered.startsWith('hola') ? 'conversation' : 'preview',
    effect: 'none',
    risk: 'low',
    operations: [],
    verification: { status: lowered.startsWith('hola') ? 'not_applicable' : 'unverified', evidence: [] },
    response,
    replayed: false,
  });
}

function submitThroughBridge(request) {
  if (globalThis.__TAURI__?.core?.invoke) {
    return globalThis.__TAURI__.core.invoke('submit', { request });
  }
  if (globalThis.chrome?.webview?.postMessage) {
    return new Promise((resolve, reject) => {
      const timeout = globalThis.setTimeout(() => {
        pendingWebView.delete(request.invocation_id);
        reject(new Error('El core no respondió a tiempo.'));
      }, 15000);
      pendingWebView.set(request.invocation_id, { resolve, reject, timeout });
      globalThis.chrome.webview.postMessage(request);
    });
  }
  return demoSubmit(request);
}

if (globalThis.chrome?.webview?.addEventListener) {
  globalThis.chrome.webview.addEventListener('message', (event) => {
    const response = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
    const pending = pendingWebView.get(response?.invocation_id);
    if (!pending) return;
    globalThis.clearTimeout(pending.timeout);
    pendingWebView.delete(response.invocation_id);
    pending.resolve(response);
  });
}

async function submitMessage(message, forcedInvocationId = null) {
  const text = message.trim();
  if (!text || busy) return null;
  busy = true;
  sendButton.disabled = true;
  input.disabled = true;
  appendMessage('user', text);
  setProgress('Entendiendo', 'Estoy delimitando la misión y su riesgo…');
  const testInvocationId = automationPanel.hidden ? '' : automationInvocation.value.trim();
  const request = { invocation_id: forcedInvocationId || testInvocationId || invocationId(), message: text };
  try {
    await new Promise((resolve) => globalThis.setTimeout(resolve, 80));
    setProgress('Actuando', 'Solo dentro del espacio local autorizado…');
    const response = await submitThroughBridge(request);
    lastResponse = response;
    progress.hidden = true;
    lastState.className = `mission-state ${response.state || 'failed'}`;
    lastState.textContent = response.state === 'done' ? 'Verificado' : response.state === 'blocked' ? 'Bloqueado' : 'Falló';
    appendMessage('assistant', response.response || 'No recibí una respuesta utilizable.', response.replayed ? 'Resultado recuperado sin repetir el efecto.' : 'Resultado del core local.');
    renderActivity(response);
    return response;
  } catch (error) {
    progress.hidden = true;
    lastState.className = 'mission-state failed';
    lastState.textContent = 'Falló';
    appendMessage('assistant', 'No pude contactar el core local.', error instanceof Error ? error.message : 'Fallo interno');
    throw error;
  } finally {
    busy = false;
    sendButton.disabled = false;
    input.disabled = false;
    input.value = '';
    input.focus();
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  void submitMessage(input.value);
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll('[data-example]').forEach((button) => {
  button.addEventListener('click', () => {
    input.value = button.dataset.example || '';
    input.focus();
  });
});

contrastButton.addEventListener('click', () => {
  const enabled = document.body.classList.toggle('high-contrast');
  contrastButton.setAttribute('aria-pressed', String(enabled));
});

globalThis.baxyTest = {
  submit: submitMessage,
  get lastResponse() { return lastResponse; },
  bridgeKind,
};

updateBridgeState();
void configureAutomationMode();
input.focus();
