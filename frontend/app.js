const form = document.querySelector('#lesson-form');
const statusBox = document.querySelector('#status');
const workspace = document.querySelector('#workspace');
const video = document.querySelector('#video');
const offlineAudio = document.querySelector('#offline-audio');
const title = document.querySelector('#lesson-title');
const speed = document.querySelector('#speed');
const listenButton = document.querySelector('#listen');
const listenCount = document.querySelector('#listen-count');
const locked = document.querySelector('#question-locked');
const answerForm = document.querySelector('#answer-form');
const question = document.querySelector('#question');
const feedback = document.querySelector('#feedback');
const transcript = document.querySelector('#transcript');
const nextButton = document.querySelector('#next');
const progressLabel = document.querySelector('#progress-label');
const progressBar = document.querySelector('#progress-bar');
const scoreLabel = document.querySelector('#score-label');
const saveOfflineButton = document.querySelector('#save-offline');
const deleteServerButton = document.querySelector('#delete-server');
const lessonMode = document.querySelector('#lesson-mode');
const mediaNote = document.querySelector('#media-note');
const savedSection = document.querySelector('#saved-section');
const savedLessons = document.querySelector('#saved-lessons');
const connectionState = document.querySelector('#connection-state');
const installButton = document.querySelector('#install-app');

const SAVED_KEY = 'freetuve.saved.v1';
const OFFLINE_CACHE = 'freetuve-offline-lessons-v1';
const API_BASE_URL = String(window.FREETUVE_API_BASE_URL || '').replace(/\/+$/, '');

function apiUrl(path) {
  if (!path || path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

function normalizeLesson(data) {
  if (!data || typeof data !== 'object') return data;
  for (const key of ['media_url', 'download_url']) {
    if (data[key]) data[key] = apiUrl(data[key]);
  }
  return data;
}

let lesson = null;
let queue = [];
let queueIndex = 0;
let current = null;
let listens = 0;
let selectedChoice = null;
let stopHandler = null;
let scores = [];
let retryCounts = new Map();
let offlineMode = false;
let installPrompt = null;

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.remove('hidden');
  statusBox.style.borderColor = isError ? 'rgba(255,123,134,.5)' : '';
}

function hideStatus() {
  statusBox.classList.add('hidden');
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body != null && !headers['Content-Type'] && !headers['content-type']) {
    headers['Content-Type'] = 'application/json';
  }

  let response;
  try {
    response = await fetch(apiUrl(url), { ...options, headers });
  } catch (_) {
    throw new Error('No se pudo conectar con el servidor. Comprueba tu conexión y vuelve a intentarlo.');
  }

  let payload = null;
  if (response.status !== 204) {
    try { payload = await response.json(); } catch (_) { payload = {}; }
  }
  if (!response.ok) throw new Error(payload?.detail || payload?.error || 'Ha ocurrido un error inesperado.');
  return payload;
}

function loadSavedMap() {
  try {
    const value = JSON.parse(localStorage.getItem(SAVED_KEY) || '{}');
    return value && typeof value === 'object' ? value : {};
  } catch (_) {
    return {};
  }
}

function saveSavedMap(value) {
  localStorage.setItem(SAVED_KEY, JSON.stringify(value));
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function updateConnectionState() {
  connectionState.textContent = navigator.onLine ? 'Online' : 'Sin conexión';
  connectionState.classList.toggle('offline', !navigator.onLine);
}

function renderSavedLessons() {
  const saved = loadSavedMap();
  const entries = Object.values(saved).sort((a, b) => (b.saved_at || '').localeCompare(a.saved_at || ''));
  savedLessons.replaceChildren();
  savedSection.classList.toggle('hidden', entries.length === 0);
  for (const item of entries) {
    const row = document.createElement('div');
    row.className = 'saved-item';
    const copy = document.createElement('div');
    const heading = document.createElement('strong');
    heading.textContent = item.title || 'Lección guardada';
    const meta = document.createElement('span');
    meta.textContent = `${item.exercise_count || item.exercises?.length || 0} ejercicios${item.size_bytes ? ` · ${formatBytes(item.size_bytes)}` : ''}`;
    copy.append(heading, meta);
    const actions = document.createElement('div');
    actions.className = 'saved-actions';
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'secondary';
    open.textContent = 'Abrir';
    open.addEventListener('click', () => startSavedLesson(item));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'ghost';
    remove.textContent = 'Eliminar';
    remove.addEventListener('click', () => removeSavedLesson(item.id));
    actions.append(open, remove);
    row.append(copy, actions);
    savedLessons.append(row);
  }
}

async function removeSavedLesson(id) {
  const saved = loadSavedMap();
  const item = saved[id];
  if (!item) return;
  if ('caches' in window) {
    const cache = await caches.open(OFFLINE_CACHE);
    await Promise.all((item.exercises || []).map(ex => cache.delete(ex.clip_url)));
  }
  delete saved[id];
  saveSavedMap(saved);
  renderSavedLessons();
  if (offlineMode && lesson?.id === id) {
    workspace.classList.add('hidden');
    lesson = null;
  }
}

async function pollLesson(id) {
  for (let attempt = 0; attempt < 1200; attempt += 1) {
    const data = await request(`/api/lessons/${id}`);
    if (data.status === 'ready') return normalizeLesson(data);
    if (data.status === 'error') throw new Error(data.error || 'No se pudo crear la lección.');
    setStatus(data.status === 'processing' ? 'Procesando vídeo, subtítulos y ejercicios…' : 'Preparando la lección…');
    await sleep(1500);
  }
  throw new Error('El procesamiento está tardando demasiado. Prueba con un vídeo más corto.');
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!navigator.onLine) {
    setStatus('Necesitas conexión para crear una nueva lección. Puedes abrir las guardadas offline.', true);
    return;
  }
  workspace.classList.add('hidden');
  setStatus('Preparando la lección…');
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const created = await request('/api/lessons', {
      method: 'POST',
      body: JSON.stringify({
        url: document.querySelector('#url').value.trim(),
        language: document.querySelector('#language').value,
        difficulty: document.querySelector('#difficulty').value,
        max_items: Number(document.querySelector('#max-items').value),
      }),
    });
    lesson = await pollLesson(created.id);
    startLesson(false);
    hideStatus();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
});

function resetSession() {
  queue = lesson.exercises.map(item => item.id);
  queueIndex = 0;
  scores = [];
  retryCounts = new Map();
  current = null;
  listens = 0;
  selectedChoice = null;
}

function startLesson(isOffline) {
  offlineMode = isOffline;
  resetSession();
  title.textContent = lesson.title || 'Lección';
  lessonMode.textContent = offlineMode ? 'Lección offline' : `Lección · ${lesson.caption_source === 'faster-whisper' ? 'transcripción local' : 'subtítulos'}`;
  saveOfflineButton.classList.toggle('hidden', offlineMode);
  deleteServerButton.classList.toggle('hidden', offlineMode);
  video.classList.toggle('hidden', offlineMode);
  offlineAudio.classList.toggle('hidden', !offlineMode);
  mediaNote.classList.toggle('hidden', !offlineMode);
  mediaNote.textContent = offlineMode ? 'Modo offline: se guardaron solo los fragmentos de audio necesarios para esta lección.' : '';
  if (!offlineMode) {
    video.src = lesson.media_url;
    offlineAudio.removeAttribute('src');
  } else {
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
  workspace.classList.remove('hidden');
  loadCurrent();
  workspace.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function startSavedLesson(saved) {
  lesson = typeof structuredClone === 'function' ? structuredClone(saved) : JSON.parse(JSON.stringify(saved));
  startLesson(true);
  hideStatus();
}

function findExercise(id) {
  return lesson.exercises.find(item => item.id === id);
}

function loadCurrent() {
  if (queueIndex >= queue.length) {
    finishLesson();
    return;
  }
  current = findExercise(queue[queueIndex]);
  listens = 0;
  selectedChoice = null;
  listenCount.textContent = `Escuchas: 0 · mínimo ${current.min_listens}`;
  answerForm.classList.add('hidden');
  locked.classList.remove('hidden');
  feedback.className = 'feedback hidden';
  feedback.textContent = '';
  transcript.className = 'transcript hidden';
  transcript.textContent = '';
  nextButton.classList.add('hidden');
  listenButton.disabled = false;
  renderQuestion();
  updateProgress();
}

function updateProgress() {
  const uniqueDone = new Set(queue.slice(0, queueIndex)).size;
  const total = lesson.exercises.length;
  progressLabel.textContent = `Ejercicio ${Math.min(uniqueDone + 1, total)} de ${total}`;
  progressBar.style.width = `${Math.min(100, (uniqueDone / total) * 100)}%`;
  const average = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  scoreLabel.textContent = `Puntuación media: ${average.toFixed(0)}`;
}

function renderQuestion() {
  question.replaceChildren();
  if (current.type === 'dictation') {
    const prompt = document.createElement('p');
    prompt.textContent = current.display;
    const area = document.createElement('textarea');
    area.id = 'dictation-answer';
    area.placeholder = 'Escribe aquí lo que has escuchado…';
    area.autocomplete = 'off';
    question.append(prompt, area);
    return;
  }
  const parts = current.display.split(/(\[\[blank:\d+\]\])/g);
  const sentence = document.createElement('div');
  for (const part of parts) {
    const marker = part.match(/^\[\[blank:(\d+)\]\]$/);
    if (!marker) {
      sentence.append(document.createTextNode(part));
      continue;
    }
    if (current.type === 'multiple_choice') {
      const blank = document.createElement('strong');
      blank.textContent = ' _____ ';
      sentence.append(blank);
    } else {
      const input = document.createElement('input');
      input.className = 'inline-blank';
      input.dataset.blankIndex = marker[1];
      input.setAttribute('aria-label', `Hueco ${Number(marker[1]) + 1}`);
      input.autocomplete = 'off';
      sentence.append(input);
    }
  }
  question.append(sentence);
  if (current.type === 'multiple_choice') {
    const grid = document.createElement('div');
    grid.className = 'choice-grid';
    for (const option of current.choices) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'secondary choice';
      button.textContent = option;
      button.addEventListener('click', () => {
        selectedChoice = option;
        grid.querySelectorAll('.choice').forEach(item => item.classList.remove('selected'));
        button.classList.add('selected');
      });
      grid.append(button);
    }
    question.append(grid);
  }
}

speed.addEventListener('change', () => {
  const rate = Number(speed.value);
  video.playbackRate = rate;
  offlineAudio.playbackRate = rate;
});

function recordListen() {
  listens += 1;
  listenCount.textContent = `Escuchas: ${listens} · mínimo ${current.min_listens}`;
  if (listens >= current.min_listens) {
    locked.classList.add('hidden');
    answerForm.classList.remove('hidden');
  }
}

async function playCurrent() {
  if (offlineMode) {
    offlineAudio.pause();
    offlineAudio.src = current.clip_url;
    offlineAudio.currentTime = 0;
    offlineAudio.playbackRate = Number(speed.value);
    await offlineAudio.play();
    recordListen();
    return;
  }
  if (stopHandler) video.removeEventListener('timeupdate', stopHandler);
  video.pause();
  video.currentTime = Math.max(0, current.start - 0.12);
  video.playbackRate = Number(speed.value);
  stopHandler = () => {
    if (video.currentTime >= current.end + 0.08) {
      video.pause();
      video.removeEventListener('timeupdate', stopHandler);
      stopHandler = null;
    }
  };
  video.addEventListener('timeupdate', stopHandler);
  try {
    await video.play();
    recordListen();
  } catch (error) {
    video.removeEventListener('timeupdate', stopHandler);
    stopHandler = null;
    throw error;
  }
}

listenButton.addEventListener('click', async () => {
  if (!current) return;
  try {
    await playCurrent();
  } catch (_) {
    setStatus(offlineMode ? 'No se pudo abrir este fragmento offline. Elimínalo y vuelve a guardarlo cuando tengas conexión.' : 'El navegador ha bloqueado la reproducción. Pulsa play en el vídeo y vuelve a intentarlo.', true);
  }
});

function collectAnswer() {
  if (current.type === 'dictation') return document.querySelector('#dictation-answer').value.trim();
  if (current.type === 'multiple_choice') return selectedChoice ? [selectedChoice] : [];
  return [...question.querySelectorAll('[data-blank-index]')]
    .sort((a, b) => Number(a.dataset.blankIndex) - Number(b.dataset.blankIndex))
    .map(input => input.value.trim());
}

function normalizeAnswer(value) {
  return String(value).normalize('NFKC').toLocaleLowerCase().replace(/[’]/g, "'").replace(/[^\p{L}\p{N}'-]+/gu, ' ').trim().replace(/\s+/g, ' ');
}

function editDistance(a, b) {
  const previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    let diagonal = previous[0];
    previous[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      const saved = previous[j];
      previous[j] = Math.min(previous[j] + 1, previous[j - 1] + 1, diagonal + (a[i - 1] === b[j - 1] ? 0 : 1));
      diagonal = saved;
    }
  }
  return previous[b.length];
}

function scoreOffline(exercise, answer, listenCountValue) {
  const penalty = Math.max(0, listenCountValue - (exercise.min_listens || 2)) * 4;
  if (exercise.type === 'dictation') {
    const expected = normalizeAnswer(exercise.expected);
    const supplied = normalizeAnswer(Array.isArray(answer) ? answer.join(' ') : answer);
    const maxLength = Math.max(1, expected.length, supplied.length);
    const similarity = Math.max(0, 1 - editDistance(expected, supplied) / maxLength);
    return { correct: similarity >= 0.96, accuracy: similarity, score: Math.max(0, Math.round(similarity * 100) - penalty), correct_answer: exercise.expected, transcript: exercise.transcript || String(exercise.expected) };
  }
  const expected = exercise.expected.map(normalizeAnswer);
  const supplied = (Array.isArray(answer) ? answer : [answer]).map(normalizeAnswer);
  const matches = expected.reduce((sum, item, index) => sum + (item === supplied[index] ? 1 : 0), 0);
  const accuracy = matches / Math.max(1, expected.length);
  return { correct: supplied.length === expected.length && accuracy === 1, accuracy, score: Math.max(0, Math.round(accuracy * 100) - penalty), correct_answer: exercise.expected, transcript: exercise.transcript || '' };
}

function formatCorrectAnswer(value) {
  return Array.isArray(value) ? value.join(' · ') : value;
}

answerForm.addEventListener('submit', async event => {
  event.preventDefault();
  const answer = collectAnswer();
  if ((Array.isArray(answer) && (answer.length === 0 || answer.some(item => !item))) || (!Array.isArray(answer) && !answer)) {
    feedback.className = 'feedback bad';
    feedback.textContent = 'Completa la respuesta antes de comprobarla.';
    return;
  }
  const submit = document.querySelector('#submit-answer');
  let graded = false;
  submit.disabled = true;
  try {
    const result = offlineMode ? scoreOffline(current, answer, listens) : await request(`/api/lessons/${lesson.id}/attempts`, { method: 'POST', body: JSON.stringify({ exercise_id: current.id, answer, listens }) });
    scores.push(result.score);
    feedback.className = `feedback ${result.correct ? 'good' : 'bad'}`;
    feedback.textContent = result.correct ? `Correcto. ${result.score}/100.` : `No del todo. Respuesta: ${formatCorrectAnswer(result.correct_answer)} · ${result.score}/100.`;
    if (result.transcript) {
      transcript.className = 'transcript';
      transcript.textContent = result.transcript;
    }
    answerForm.querySelectorAll('input, textarea, button').forEach(el => { el.disabled = true; });
    graded = true;
    nextButton.classList.remove('hidden');
    if (!result.correct) {
      const retries = retryCounts.get(current.id) || 0;
      if (retries < 2) {
        retryCounts.set(current.id, retries + 1);
        queue.splice(Math.min(queueIndex + 3, queue.length), 0, current.id);
      }
    }
    updateProgress();
  } catch (error) {
    feedback.className = 'feedback bad';
    feedback.textContent = error.message;
  } finally {
    if (!graded) submit.disabled = false;
  }
});

nextButton.addEventListener('click', () => {
  answerForm.querySelectorAll('input, textarea, button').forEach(el => { el.disabled = false; });
  queueIndex += 1;
  loadCurrent();
});

function finishLesson() {
  current = null;
  listenButton.disabled = true;
  locked.classList.add('hidden');
  answerForm.classList.add('hidden');
  nextButton.classList.add('hidden');
  transcript.classList.add('hidden');
  progressBar.style.width = '100%';
  progressLabel.textContent = 'Lección terminada';
  const average = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  feedback.className = 'feedback good';
  feedback.textContent = `Has terminado. Puntuación media: ${average.toFixed(0)}/100. Las frases falladas se han repetido hasta dos veces.`;
  scoreLabel.textContent = `Puntuación media: ${average.toFixed(0)}`;
}

saveOfflineButton.addEventListener('click', async () => {
  if (!lesson || offlineMode) return;
  if (!('caches' in window)) {
    setStatus('Este navegador no permite guardar lecciones offline.', true);
    return;
  }
  saveOfflineButton.disabled = true;
  setStatus('Preparando fragmentos offline…');
  try {
    const pack = await request(`/api/lessons/${lesson.id}/offline-pack`, { method: 'POST' });
    for (const exercise of pack.exercises || []) exercise.clip_url = apiUrl(exercise.clip_url);
    const cache = await caches.open(OFFLINE_CACHE);
    for (let index = 0; index < pack.exercises.length; index += 1) {
      const exercise = pack.exercises[index];
      setStatus(`Guardando audio offline ${index + 1}/${pack.exercises.length}…`);
      const response = await fetch(exercise.clip_url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`No se pudo guardar el fragmento ${index + 1}.`);
      await cache.put(exercise.clip_url, response.clone());
    }
    const saved = loadSavedMap();
    saved[pack.id] = { ...pack, saved_at: new Date().toISOString() };
    saveSavedMap(saved);
    renderSavedLessons();
    setStatus(`Lección guardada para usar sin conexión${pack.size_bytes ? ` · ${formatBytes(pack.size_bytes)}` : ''}.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    saveOfflineButton.disabled = false;
  }
});

deleteServerButton.addEventListener('click', async () => {
  if (!lesson || offlineMode) return;
  const saved = loadSavedMap()[lesson.id];
  const message = saved ? 'Se borrará la copia temporal del servidor. La lección offline seguirá en este dispositivo.' : 'Se borrará la lección y el vídeo temporal del servidor. Si no la has guardado offline, no podrás continuar.';
  if (!window.confirm(message)) return;
  try {
    await request(`/api/lessons/${lesson.id}`, { method: 'DELETE' });
    if (saved) {
      startSavedLesson(saved);
      setStatus('Copia del servidor eliminada. Estás usando la versión offline.');
    } else {
      workspace.classList.add('hidden');
      lesson = null;
      setStatus('Lección y vídeo temporal eliminados del servidor.');
    }
  } catch (error) {
    setStatus(error.message, true);
  }
});

window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  installPrompt = event;
  installButton.classList.remove('hidden');
});

installButton.addEventListener('click', async () => {
  if (!installPrompt) return;
  await installPrompt.prompt();
  installPrompt = null;
  installButton.classList.add('hidden');
});

window.addEventListener('appinstalled', () => {
  installPrompt = null;
  installButton.classList.add('hidden');
});

window.addEventListener('online', updateConnectionState);
window.addEventListener('offline', updateConnectionState);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}

updateConnectionState();
renderSavedLessons();
