// FreeTuve resilience layer.
//
// Railway can restart the backend after an OOM or process failure. Normal
// process restarts can resume persisted pending/processing lessons server-side.
// If a replacement container loses ephemeral lesson state, the browser keeps
// the original creation request and recreates that lesson automatically.

const PENDING_PREFIX = 'freetuve.pending.v1.';
const originalRequest = window.request.bind(window);

function pendingKey(id) {
  return `${PENDING_PREFIX}${id}`;
}

function readPendingRequest(id) {
  try {
    const value = JSON.parse(sessionStorage.getItem(pendingKey(id)) || 'null');
    return value?.request && typeof value.request === 'object' ? value.request : null;
  } catch (_) {
    return null;
  }
}

function rememberPendingRequest(id, requestBody) {
  try {
    sessionStorage.setItem(pendingKey(id), JSON.stringify({
      request: requestBody,
      created_at: new Date().toISOString(),
    }));
  } catch (_) {
    // Storage can be disabled; server-side recovery still remains available.
  }
}

function forgetPendingRequest(id) {
  try { sessionStorage.removeItem(pendingKey(id)); } catch (_) {}
}

function purgeLegacyPendingRequests() {
  // Older builds stored the original creation payload in localStorage. Remove
  // those records so source URLs and pasted transcripts do not persist beyond
  // the browser session after upgrading.
  try {
    const keys = [];
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);
      if (key?.startsWith(PENDING_PREFIX)) keys.push(key);
    }
    for (const key of keys) localStorage.removeItem(key);
  } catch (_) {}
}

purgeLegacyPendingRequests();

// Preserve HTTP status information that the original request helper intentionally
// hides. The rest of app.js keeps using the same request API.
window.request = async function resilientRequest(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body != null && !headers['Content-Type'] && !headers['content-type']) {
    headers['Content-Type'] = 'application/json';
  }

  let response;
  try {
    response = await fetch(window.apiUrl(url), { ...options, headers });
  } catch (_) {
    const error = new Error('No se pudo conectar con el servidor. Comprueba tu conexión y vuelve a intentarlo.');
    error.transient = true;
    throw error;
  }

  let payload = null;
  if (response.status !== 204) {
    try { payload = await response.json(); } catch (_) { payload = {}; }
  }
  if (!response.ok) {
    const error = new Error(payload?.detail || payload?.error || 'Ha ocurrido un error inesperado.');
    error.status = response.status;
    error.transient = response.status >= 500 || response.status === 408;
    throw error;
  }

  if (url === '/api/lessons' && String(options.method || 'GET').toUpperCase() === 'POST' && payload?.id) {
    try {
      const requestBody = typeof options.body === 'string' ? JSON.parse(options.body) : options.body;
      if (requestBody && typeof requestBody === 'object') rememberPendingRequest(payload.id, requestBody);
    } catch (_) {}
  }

  return payload;
};

window.pollLesson = async function pollLessonWithRecovery(initialId, kind = 'video') {
  // Full-length movie transcription can legitimately take far longer than a short video
  // on the 1 GB CPU worker. Keep the existing ~30 minute ceiling for videos, but
  // allow movie jobs up to ~4 hours before the browser gives up polling.
  const maxPollAttempts = kind === 'movie' ? 9600 : 1200;
  const retryDelayMs = 1500;
  const maxConsecutiveTransportFailures = 40; // ~60 seconds of restart grace.
  const maxRecreations = 2;
  let currentId = initialId;
  const noun = kind === 'movie' ? 'película' : 'vídeo';
  let consecutiveTransportFailures = 0;
  let recreations = 0;

  for (let attempt = 0; attempt < maxPollAttempts; attempt += 1) {
    let data;
    try {
      data = await window.request(`/api/lessons/${currentId}`);
      consecutiveTransportFailures = 0;
    } catch (error) {
      // A fresh container may legitimately return 404 because Railway's
      // ephemeral filesystem was replaced. Recreate the same request rather
      // than making the user start over manually.
      if (error.status === 404 && recreations < maxRecreations) {
        const originalPayload = readPendingRequest(currentId);
        if (originalPayload) {
          window.setStatus('El servidor se reinició. Recuperando la lección automáticamente…');
          const previousId = currentId;
          const recreated = await window.request('/api/lessons', {
            method: 'POST',
            body: JSON.stringify(originalPayload),
          });
          currentId = recreated.id;
          recreations += 1;
          forgetPendingRequest(previousId);
          await window.sleep(retryDelayMs);
          continue;
        }
      }

      if (!error.transient) throw error;
      consecutiveTransportFailures += 1;
      if (consecutiveTransportFailures >= maxConsecutiveTransportFailures) {
        throw new Error(
          'El servidor no consiguió recuperarse automáticamente. Vuelve a intentarlo en unos instantes.',
        );
      }
      window.setStatus('El servidor se está recuperando. Reintentando automáticamente…');
      await window.sleep(retryDelayMs);
      continue;
    }

    if (data.status === 'ready') {
      forgetPendingRequest(currentId);
      if (currentId !== initialId) forgetPendingRequest(initialId);
      return window.normalizeLesson(data);
    }
    if (data.status === 'error') {
      forgetPendingRequest(currentId);
      if (currentId !== initialId) forgetPendingRequest(initialId);
      throw new Error(data.error || 'No se pudo crear la lección.');
    }

    window.setStatus(
      data.status === 'processing'
        ? `Procesando ${noun}, subtítulos y ejercicios…`
        : 'Preparando la lección…',
    );
    await window.sleep(retryDelayMs);
  }

  throw new Error('El procesamiento está tardando demasiado. Prueba con una fuente más corta o ligera.');
};

// Keep the old helper reachable for debugging without using it in normal flow.
window.freetuveOriginalRequest = originalRequest;
