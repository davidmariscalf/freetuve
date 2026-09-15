// FreeTuve resilience layer.
//
// Railway can restart the backend after a transient OOM or process failure.
// The lesson metadata is recovered server-side; this polling override keeps the
// browser attached to the same lesson while the backend comes back online.

window.pollLesson = async function pollLessonWithRecovery(id) {
  const maxPollAttempts = 1200;
  const retryDelayMs = 1500;
  const maxConsecutiveTransportFailures = 40; // ~60 seconds of restart grace.
  let consecutiveTransportFailures = 0;

  for (let attempt = 0; attempt < maxPollAttempts; attempt += 1) {
    let data;
    try {
      data = await window.request(`/api/lessons/${id}`);
      consecutiveTransportFailures = 0;
    } catch (error) {
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

    if (data.status === 'ready') return window.normalizeLesson(data);
    if (data.status === 'error') {
      throw new Error(data.error || 'No se pudo crear la lección.');
    }

    window.setStatus(
      data.status === 'processing'
        ? 'Procesando vídeo, subtítulos y ejercicios…'
        : 'Preparando la lección…',
    );
    await window.sleep(retryDelayMs);
  }

  throw new Error('El procesamiento está tardando demasiado. Prueba con un vídeo más corto.');
};
