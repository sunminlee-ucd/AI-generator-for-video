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
const assetInput = document.querySelector('#asset-file');
const assetsNode = document.querySelector('#assets');
const operationsNode = document.querySelector('#operations');
const applyProposalButton = document.querySelector('#apply-proposal');
const saveOperationsButton = document.querySelector('#save-operations');
const proposalNote = document.querySelector('#proposal-note');

let project = null;
let operations = [];
let pendingProposal = null;
let pendingPrompt = '';

function setStatus(text) { status.textContent = text; }
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
function assetOptions(kind) {
  const list = (project?.assets || []).filter((asset) => !kind || asset.kind === kind);
  return list.map((asset) => `<option value="${asset.id}">${escapeHtml(asset.filename)}</option>`).join('');
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}
function renderAssets() {
  assetsNode.innerHTML = '';
  for (const asset of project?.assets || []) {
    const item = document.createElement('div');
    item.className = 'asset-chip';
    item.innerHTML = `<strong>${escapeHtml(asset.filename)}</strong><span>${asset.kind}</span>`;
    assetsNode.appendChild(item);
  }
  if (!(project?.assets || []).length) assetsNode.innerHTML = '<p class="empty">No extra media yet.</p>';
}
function field(label, key, value, type='text', extra='') {
  return `<label>${label}<input data-key="${key}" type="${type}" value="${escapeHtml(value ?? '')}" ${extra}></label>`;
}
function selectField(label, key, value, options) {
  return `<label>${label}<select data-key="${key}">${options.map(([v,t]) => `<option value="${v}" ${v===value?'selected':''}>${t}</option>`).join('')}</select></label>`;
}
function operationEditor(op, index) {
  let controls = '';
  if (op.type === 'trim') controls = field('Start (s)', 'start_seconds', op.start_seconds, 'number', 'step="0.1" min="0"') + field('End (s)', 'end_seconds', op.end_seconds, 'number', 'step="0.1" min="0"');
  if (op.type === 'speed') controls = field('Speed', 'speed', op.speed, 'number', 'step="0.1" min="0.5" max="2"');
  if (op.type === 'volume') controls = field('Volume', 'volume', op.volume, 'number', 'step="0.05" min="0" max="4"');
  if (op.type === 'text_overlay') controls = [
    field('Text', 'text', op.text),
    selectField('Position', 'position', op.position || 'bottom', [['top','Top'],['center','Centre'],['bottom','Bottom']]),
    selectField('Font', 'font_family', op.font_family || 'DejaVu Sans', [['DejaVu Sans','DejaVu Sans'],['Liberation Sans','Liberation Sans'],['Liberation Serif','Liberation Serif'],['Liberation Mono','Liberation Mono']]),
    field('Font size', 'font_size', op.font_size || 48, 'number', 'min="8" max="240"'),
    field('Font colour', 'font_color', op.font_color || 'white'),
    field('Background', 'text_background_color', op.text_background_color || 'black@0.45'),
  ].join('');
  if (op.type === 'split_screen') controls = `<label>Second video<select data-key="secondary_asset_id">${assetOptions('video')}</select></label>` + selectField('Layout', 'layout', op.layout || 'side_by_side', [['side_by_side','Side by side'],['stacked','Stacked']]) + field('Ratio', 'ratio', op.ratio || 0.5, 'number', 'step="0.05" min="0.15" max="0.85"');
  if (op.type === 'picture_in_picture') controls = `<label>Overlay video<select data-key="secondary_asset_id">${assetOptions('video')}</select></label>` + field('X', 'x', op.x || 20, 'number') + field('Y', 'y', op.y || 20, 'number') + field('Width', 'width', op.width || 360, 'number') + field('Height', 'height', op.height || 202, 'number');
  if (op.type === 'masked_video') controls = `<label>Background video<select data-key="secondary_asset_id">${assetOptions('video')}</select></label>` + selectField('Mask', 'shape', op.shape || 'star', [['star','Star'],['circle','Circle'],['heart','Heart'],['triangle','Triangle']]) + field('X', 'x', op.x || 40, 'number') + field('Y', 'y', op.y || 40, 'number') + field('Width', 'width', op.width || 360, 'number') + field('Height', 'height', op.height || 360, 'number') + field('Rotation', 'rotation', op.rotation || 0, 'number') + field('Feather', 'feather', op.feather || 0, 'number', 'min="0" max="100"') + field('Opacity', 'opacity', op.opacity ?? 1, 'number', 'step="0.05" min="0" max="1"');
  if (op.type === 'music') controls = `<label>Music<select data-key="source_asset_id">${assetOptions('audio')}</select></label>` + field('Volume', 'volume', op.volume ?? 0.35, 'number', 'step="0.05" min="0" max="4"') + field('Start (s)', 'start_seconds', op.start_seconds || 0, 'number', 'step="0.1"') + field('End (s)', 'end_seconds', op.end_seconds, 'number', 'step="0.1"') + field('Fade in', 'fade_in_seconds', op.fade_in_seconds || 0, 'number', 'step="0.1"') + field('Fade out', 'fade_out_seconds', op.fade_out_seconds || 0, 'number', 'step="0.1"') + `<label class="check"><input data-key="ducking" type="checkbox" ${op.ducking?'checked':''}> Duck music under speech</label>`;
  if (op.type === 'style_transfer') controls = `<label>Style prompt<textarea data-key="style_prompt" rows="3">${escapeHtml(op.style_prompt || '')}</textarea></label>`;

  return `<article class="operation" data-index="${index}">
    <div class="operation-head"><div><span class="op-type">${op.type.replaceAll('_',' ')}</span><small>${op.id?.slice(0,8) || ''}</small></div><label class="check"><input data-key="enabled" type="checkbox" ${op.enabled !== false ? 'checked':''}> Enabled</label></div>
    <div class="control-grid">${controls || '<p class="hint">No additional parameters.</p>'}</div>
    <button class="danger remove-op" type="button">Remove</button>
  </article>`;
}
function renderOperations() {
  operationsNode.innerHTML = operations.map(operationEditor).join('') || '<p class="empty">No edits yet. Ask AI for a proposal.</p>';
  operationsNode.querySelectorAll('.operation').forEach((card) => {
    const index = Number(card.dataset.index);
    card.querySelectorAll('[data-key]').forEach((input) => {
      if (input.dataset.key === 'secondary_asset_id' && operations[index].secondary_asset_id) input.value = operations[index].secondary_asset_id;
      if (input.dataset.key === 'source_asset_id' && operations[index].source_asset_id) input.value = operations[index].source_asset_id;
      input.addEventListener('change', () => updateOperation(index, input));
      input.addEventListener('input', () => updateOperation(index, input));
    });
    card.querySelector('.remove-op')?.addEventListener('click', () => { operations.splice(index, 1); renderOperations(); });
  });
}
function updateOperation(index, input) {
  const key = input.dataset.key;
  let value = input.type === 'checkbox' ? input.checked : input.value;
  if (input.type === 'number') value = value === '' ? null : Number(value);
  operations[index][key] = value;
  if (pendingProposal) pendingProposal.operations = operations;
}

uploadButton.addEventListener('click', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  setStatus('Uploading');
  const body = new FormData(); body.append('file', file);
  try {
    project = await api('/api/projects', { method: 'POST', body });
    operations = project.operations || [];
    preview.src = project.source_url;
    metadata.textContent = `${project.metadata.duration_seconds}s · ${project.metadata.dimensions.width}×${project.metadata.dimensions.height}`;
    uploadPanel.classList.add('hidden'); workspace.classList.remove('hidden');
    renderAssets(); renderOperations();
    addMessage('assistant', 'Video loaded. Add any extra videos or music, then ask me for an edit proposal.');
    setStatus('Ready');
  } catch (error) { setStatus('Upload failed'); addMessage('assistant', error.message); }
});

assetInput.addEventListener('change', async () => {
  const file = assetInput.files[0]; if (!file || !project) return;
  setStatus('Uploading media');
  const body = new FormData(); body.append('file', file); body.append('kind', 'auto');
  try {
    await api(`/api/projects/${project.id}/assets`, { method: 'POST', body });
    project = await api(`/api/projects/${project.id}`);
    renderAssets(); renderOperations(); setStatus('Ready');
  } catch (error) { addMessage('assistant', error.message); setStatus('Failed'); }
  assetInput.value = '';
});

form.addEventListener('submit', async (event) => {
  event.preventDefault(); if (!project) return;
  const prompt = promptInput.value.trim(); if (!prompt) return;
  promptInput.value = ''; addMessage('user', prompt); setStatus('Planning');
  try {
    const result = await api(`/api/projects/${project.id}/commands`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ prompt }) });
    pendingPrompt = prompt; pendingProposal = result.plan;
    operations = [...(project.operations || []), ...(result.plan.operations || [])];
    addMessage('assistant', `${result.assistant_message}\nReview the proposed controls before applying.`);
    proposalNote.textContent = 'AI proposal is not rendered yet. Adjust any values, disable/remove changes, then apply.';
    proposalNote.classList.remove('hidden'); applyProposalButton.classList.remove('hidden');
    renderOperations(); setStatus('Review proposal');
  } catch (error) { addMessage('assistant', error.message); setStatus('Failed'); }
});

applyProposalButton.addEventListener('click', async () => {
  if (!pendingProposal || !project) return;
  const existingCount = (project.operations || []).length;
  const proposed = operations.slice(existingCount);
  setStatus('Rendering');
  try {
    const result = await api(`/api/projects/${project.id}/apply-plan`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ prompt: pendingPrompt, assistant_message: pendingProposal.assistant_message, operations: proposed }) });
    await pollJob(result.job_id);
    project = await api(`/api/projects/${project.id}`); operations = project.operations || [];
    pendingProposal = null; proposalNote.classList.add('hidden'); applyProposalButton.classList.add('hidden'); renderOperations();
  } catch (error) { addMessage('assistant', error.message); setStatus('Failed'); }
});

saveOperationsButton.addEventListener('click', async () => {
  if (!project) return; setStatus('Rendering');
  try {
    const result = await api(`/api/projects/${project.id}/operations`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ operations }) });
    await pollJob(result.job_id); project = await api(`/api/projects/${project.id}`); operations = project.operations || []; renderOperations();
  } catch (error) { addMessage('assistant', error.message); setStatus('Failed'); }
});

undoButton.addEventListener('click', async () => {
  if (!project) return; setStatus('Undoing');
  try {
    const result = await api(`/api/projects/${project.id}/undo`, { method:'POST' }); await pollJob(result.job_id);
    project = await api(`/api/projects/${project.id}`); operations = project.operations || []; renderOperations(); addMessage('assistant', result.assistant_message);
  } catch (error) { addMessage('assistant', error.message); setStatus('Failed'); }
});

async function pollJob(jobId) {
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const job = await api(`/api/jobs/${jobId}`);
    if (job.status === 'completed') { preview.src = `${job.output_url}?t=${Date.now()}`; preview.load(); setStatus('Ready'); return; }
    if (job.status === 'failed') throw new Error(job.error || 'Rendering failed');
    setStatus(job.status === 'running' ? 'Rendering' : 'Queued');
  }
}
