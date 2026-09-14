const form = document.querySelector('#lesson-form');
const statusBox = document.querySelector('#status');
const workspace = document.querySelector('#workspace');
const video = document.querySelector('#video');
const title = document.querySelector('#lesson-title');
const speed = document.querySelector('#speed');
const listenButton = document.querySelector('#listen');
const listenCount = document.querySelector('#listen-count');
const locked = document.querySelector('#question-locked');
const answerForm = document.querySelector('#answer-form');
const question = document.querySelector('#question');
const feedback = document.querySelector('#feedback');
const nextButton = document.querySelector('#next');
const progressLabel = document.querySelector('#progress-label');
const progressBar = document.querySelector('#progress-bar');
const scoreLabel = document.querySelector('#score-label');

let lesson = null;
let queue = [];
let queueIndex = 0;
let current = null;
let listens = 0;
let selectedChoice = null;
let stopHandler = null;
let scores = [];
let retryCounts = new Map();

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
  const response = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  let payload = null;
  try { payload = await response.json(); } catch (_) { payload = {}; }
  if (!response.ok) throw new Error(payload.detail || payload.error || 'Ha ocurrido un error inesperado.');
  return payload;
}

async function pollLesson(id) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const data = await request(`/api/lessons/${id}`);
    if (data.status === 'ready') return data;
    if (data.status === 'error') throw new Error(data.error || 'No se pudo crear la lección.');
    setStatus('Procesando vídeo y creando ejercicios…');
    await sleep(1500);
  }
  throw new Error('El procesamiento está tardando demasiado. Prueba con un vídeo más corto.');
}

form.addEventListener('submit', async event => {
  event.preventDefault();
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
    startLesson();
    hideStatus();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
});

function startLesson() {
  title.textContent = lesson.title || 'Lección';
  video.src = lesson.media_url;
  queue = lesson.exercises.map(item => item.id);
  queueIndex = 0;
  scores = [];
  retryCounts = new Map();
  workspace.classList.remove('hidden');
  loadCurrent();
  workspace.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
  video.playbackRate = Number(speed.value);
});

listenButton.addEventListener('click', async () => {
  if (!current) return;
  if (stopHandler) video.removeEventListener('timeupdate', stopHandler);
  video.pause();
  video.currentTime = Math.max(0, current.start - 0.12);
  video.playbackRate = Number(speed.value);
  listens += 1;
  listenCount.textContent = `Escuchas: ${listens} · mínimo ${current.min_listens}`;
  if (listens >= current.min_listens) {
    locked.classList.add('hidden');
    answerForm.classList.remove('hidden');
  }
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
  } catch (_) {
    setStatus('El navegador ha bloqueado la reproducción. Pulsa play en el vídeo y vuelve a intentarlo.', true);
  }
});

function collectAnswer() {
  if (current.type === 'dictation') {
    return document.querySelector('#dictation-answer').value.trim();
  }
  if (current.type === 'multiple_choice') {
    return selectedChoice ? [selectedChoice] : [];
  }
  return [...question.querySelectorAll('[data-blank-index]')]
    .sort((a, b) => Number(a.dataset.blankIndex) - Number(b.dataset.blankIndex))
    .map(input => input.value.trim());
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
  submit.disabled = true;
  try {
    const result = await request(`/api/lessons/${lesson.id}/attempts`, {
      method: 'POST',
      body: JSON.stringify({ exercise_id: current.id, answer, listens }),
    });
    scores.push(result.score);
    feedback.className = `feedback ${result.correct ? 'good' : 'bad'}`;
    feedback.textContent = result.correct
      ? `Correcto. ${result.score}/100.`
      : `No del todo. Respuesta: ${formatCorrectAnswer(result.correct_answer)} · ${result.score}/100.`;
    answerForm.querySelectorAll('input, textarea, button').forEach(el => { el.disabled = true; });
    nextButton.classList.remove('hidden');
    if (!result.correct) {
      const retries = retryCounts.get(current.id) || 0;
      if (retries < 2) {
        retryCounts.set(current.id, retries + 1);
        const insertAt = Math.min(queueIndex + 3, queue.length);
        queue.splice(insertAt, 0, current.id);
      }
    }
    updateProgress();
  } catch (error) {
    feedback.className = 'feedback bad';
    feedback.textContent = error.message;
  } finally {
    submit.disabled = false;
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
  progressBar.style.width = '100%';
  progressLabel.textContent = 'Lección terminada';
  const average = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  feedback.className = 'feedback good';
  feedback.textContent = `Has terminado. Puntuación media: ${average.toFixed(0)}/100. Las frases falladas se han repetido hasta dos veces durante la sesión.`;
  scoreLabel.textContent = `Puntuación media: ${average.toFixed(0)}`;
}
