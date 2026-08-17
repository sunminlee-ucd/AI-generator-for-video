const fileInput = document.querySelector('#video-file');
const uploadButton = document.querySelector('#upload-button');
const workspace = document.querySelector('#workspace');
const uploadPanel = document.querySelector('#upload-panel');
const preview = document.querySelector('#preview');
const metadata = document.querySelector('#metadata');
const status = document.querySelector('#status');
const form = document.querySelector('#chat-form');
const promptInput = document.querySelector('#prompt');
const messages = document.querySelector('#messages');
const undoButton = document.querySelector('#undo-button');

let project = null;

function setStatus(text) {
  status.textContent = text;
}

function addMessage(role, text) {
  const node = document.createElement('div');
  node.className = `message ${role}`;
  node.textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

uploadButton.addEventListener('click', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  setStatus('Uploading');
  const body = new FormData();
  body.append('file', file);
  try {
    project = await api('/api/projects', { method: 'POST', body });
    preview.src = project.source_url;
    const m = project.metadata;
    metadata.textContent = `${m.duration_seconds}s · ${m.dimensions.width}×${m.dimensions.height}`;
    uploadPanel.classList.add('hidden');
    workspace.classList.remove('hidden');
    addMessage('assistant', 'Video loaded. Tell me what you want to change.');
    setStatus('Ready');
  } catch (error) {
    setStatus('Upload failed');
    addMessage('assistant', error.message);
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!project) return;
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  promptInput.value = '';
  addMessage('user', prompt);
  setStatus('Planning');
  try {
    const result = await api(`/api/projects/${project.id}/commands`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    addMessage('assistant', result.assistant_message);
    if (result.job_id) await pollJob(result.job_id);
    else setStatus('Ready');
  } catch (error) {
    addMessage('assistant', error.message);
    setStatus('Failed');
  }
});

undoButton.addEventListener('click', async () => {
  if (!project) return;
  setStatus('Undoing');
  try {
    const result = await api(`/api/projects/${project.id}/undo`, { method: 'POST' });
    addMessage('assistant', result.assistant_message);
    await pollJob(result.job_id);
  } catch (error) {
    addMessage('assistant', error.message);
    setStatus('Failed');
  }
});

async function pollJob(jobId) {
  setStatus('Rendering');
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    const job = await api(`/api/jobs/${jobId}`);
    if (job.status === 'completed') {
      preview.src = `${job.output_url}?t=${Date.now()}`;
      preview.load();
      setStatus('Ready');
      return;
    }
    if (job.status === 'failed') throw new Error(job.error || 'Rendering failed');
    setStatus(job.status === 'running' ? 'Rendering' : 'Queued');
  }
}
