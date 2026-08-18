const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const fileInput = $('#video-file');
const uploadButton = $('#upload-button');
const uploadPanel = $('#upload-panel');
const workspace = $('#workspace');
const preview = $('#preview');
const previewStage = $('#preview-stage');
const directLayer = $('#direct-layer');
const directLayerLabel = $('#direct-layer-label');
const resizeHandle = $('#resize-handle');
const selectionHint = $('#selection-hint');
const metadataNode = $('#metadata');
const projectNameNode = $('#project-name');
const statusNode = $('#status');
const form = $('#chat-form');
const promptInput = $('#prompt');
const messages = $('#messages');
const undoButton = $('#undo-button');
const assetInput = $('#asset-file');
const assetsNode = $('#assets');
const operationsNode = $('#operations');
const applyProposalButton = $('#apply-proposal');
const saveOperationsButton = $('#save-operations');
const desktopApplyButton = $('#desktop-apply');
const mobileSaveButton = $('#mobile-save');
const proposalNote = $('#proposal-note');
const editCount = $('#edit-count');
const bottomNav = $('#bottom-nav');
const bottomAction = $('#bottom-action');
const toastNode = $('#toast');
const uploadLabelTitle = $('.upload-dropzone strong');
const uploadLabelSubtitle = $('.upload-dropzone span');

let project = null;
let operations = [];
let pendingProposal = null;
let pendingPrompt = '';
let proposalStartIndex = 0;
let activeTab = 'ai';
let operationsDirty = false;
let selectedOperationIndex = null;
let selectedMotionIndex = null;
let toastTimer = null;
let pointerState = null;

function isMobileLayout() {
  return window.matchMedia('(max-width: 859px)').matches;
}

function setStatus(text) {
  statusNode.textContent = text;
}

function showToast(text) {
  toastNode.textContent = text;
  toastNode.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastNode.classList.add('hidden'), 2600);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
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

function switchTab(tab) {
  activeTab = tab;
  $$('.mobile-panel').forEach((panel) => panel.classList.toggle('hidden', panel.dataset.panel !== tab));
  $$('.nav-item').forEach((button) => {
    const active = button.dataset.tab === tab;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  updateBottomAction();
}

function updateBottomAction() {
  desktopApplyButton?.classList.toggle('hidden', !pendingProposal);
  saveOperationsButton?.classList.toggle('hidden', Boolean(pendingProposal));
  if (!project || !isMobileLayout() || activeTab !== 'edits' || !operations.length) {
    bottomAction.classList.add('hidden');
    applyProposalButton.classList.add('hidden');
    mobileSaveButton.classList.add('hidden');
    return;
  }
  bottomAction.classList.remove('hidden');
  if (pendingProposal) {
    applyProposalButton.classList.remove('hidden');
    mobileSaveButton.classList.add('hidden');
  } else {
    applyProposalButton.classList.add('hidden');
    mobileSaveButton.classList.remove('hidden');
    mobileSaveButton.textContent = operationsDirty ? 'Render updated preview' : 'Render preview';
  }
}

function assetById(id) {
  return (project?.assets || []).find((asset) => asset.id === id);
}

function assetOptions(kind, selected) {
  const list = (project?.assets || []).filter((asset) => !kind || asset.kind === kind);
  if (!list.length) return '<option value="">Add media first</option>';
  return list.map((asset) => `<option value="${asset.id}" ${asset.id === selected ? 'selected' : ''}>${escapeHtml(asset.filename)}</option>`).join('');
}

function field(label, key, value, type = 'text', extra = '', className = '') {
  return `<label class="${className}">${label}<input data-key="${key}" type="${type}" value="${escapeHtml(value ?? '')}" ${extra}></label>`;
}

function selectField(label, key, value, options, className = '') {
  return `<label class="${className}">${label}<select data-key="${key}">${options.map(([v, t]) => `<option value="${v}" ${v === value ? 'selected' : ''}>${t}</option>`).join('')}</select></label>`;
}

function operationName(op) {
  return {
    trim: 'Trim video', speed: 'Playback speed', mute: 'Mute audio', volume: 'Video volume',
    text_overlay: 'Text', split_screen: 'Split screen', picture_in_picture: 'Picture in picture',
    masked_video: 'Shape video', music: 'Background music', style_transfer: 'AI visual style'
  }[op.type] || op.type.replaceAll('_', ' ');
}

function operationSummary(op) {
  const motion = (op.motion_keyframes || []).length;
  if (op.type === 'trim') return `Keep ${op.start_seconds ?? 0}s to ${op.end_seconds ?? 'end'}`;
  if (op.type === 'speed') return `${op.speed ?? 1}× speed`;
  if (op.type === 'mute') return 'Remove the original audio';
  if (op.type === 'volume') return `${Math.round((op.volume ?? 1) * 100)}% volume`;
  if (op.type === 'text_overlay') return `“${String(op.text || 'Text').slice(0, 34)}”`;
  if (op.type === 'split_screen') return `${op.layout === 'stacked' ? 'Top and bottom' : 'Side by side'} with ${assetById(op.secondary_asset_id)?.filename || 'another video'}`;
  if (op.type === 'picture_in_picture') return `${assetById(op.secondary_asset_id)?.filename || 'Overlay video'}${motion ? ` · ${motion} motion points` : ''}`;
  if (op.type === 'masked_video') return `${(op.shape || 'star').replace(/^./, (c) => c.toUpperCase())} over ${assetById(op.secondary_asset_id)?.filename || 'background video'}${motion ? ` · ${motion} motion points` : ''}`;
  if (op.type === 'music') return `${assetById(op.source_asset_id)?.filename || 'Music'} · ${Math.round((op.volume ?? .35) * 100)}%`;
  if (op.type === 'style_transfer') return String(op.style_prompt || 'AI style').slice(0, 55);
  return 'Adjust this change';
}

function motionField(label, key, value, type = 'number', extra = '') {
  return `<label>${label}<input data-motion-key="${key}" type="${type}" value="${escapeHtml(value ?? '')}" ${extra}></label>`;
}

function easingOptions(value) {
  return [['linear', 'Constant speed'], ['ease_in', 'Start slowly'], ['ease_out', 'End slowly'], ['ease_in_out', 'Smooth start and end']]
    .map(([v, t]) => `<option value="${v}" ${v === value ? 'selected' : ''}>${t}</option>`).join('');
}

function motionEditor(op, index) {
  if (!['masked_video', 'picture_in_picture'].includes(op.type)) return '';
  const frames = op.motion_keyframes || [];
  const chips = frames.map((frame, motionIndex) => `<button type="button" class="keyframe-chip ${selectedOperationIndex === index && selectedMotionIndex === motionIndex ? 'active' : ''}" data-motion-select="${motionIndex}">${Number(frame.time_seconds || 0).toFixed(1)}s</button>`).join('');
  const selected = selectedOperationIndex === index && selectedMotionIndex != null ? frames[selectedMotionIndex] : null;
  const panel = selected ? `
    <div class="keyframe-panel" data-motion-index="${selectedMotionIndex}">
      ${motionField('Time', 'time_seconds', selected.time_seconds ?? 0, 'number', 'step="0.1" min="0"')}
      <label>Movement<select data-motion-key="easing">${easingOptions(selected.easing || 'linear')}</select></label>
      ${motionField('Horizontal position', 'x', selected.x ?? 0, 'number', 'step="1"')}
      ${motionField('Vertical position', 'y', selected.y ?? 0, 'number', 'step="1"')}
      <p class="keyframe-help">Tip: with this motion point selected, drag the shape directly on the video instead of typing position numbers.</p>
      <button type="button" class="operation-action danger wide remove-selected-keyframe">Delete this motion point</button>
    </div>` : '';

  return `<div class="motion-section">
    <div class="motion-section-head">
      <div><strong>Movement</strong><span>Add positions at different moments.</span></div>
      <button type="button" class="motion-add add-keyframe">Add position now</button>
    </div>
    <div class="keyframe-chips">${chips || '<span class="empty-state">No movement yet.</span>'}</div>
    ${panel}
  </div>`;
}

function operationControls(op) {
  if (op.type === 'trim') return field('Start time', 'start_seconds', op.start_seconds, 'number', 'step="0.1" min="0"') + field('End time', 'end_seconds', op.end_seconds, 'number', 'step="0.1" min="0"');
  if (op.type === 'speed') return selectField('Speed', 'speed', op.speed ?? 1, [[0.5, '0.5×'], [0.75, '0.75×'], [1, 'Normal'], [1.25, '1.25×'], [1.5, '1.5×'], [2, '2×']]);
  if (op.type === 'volume') return field('Volume multiplier', 'volume', op.volume ?? 1, 'number', 'step="0.05" min="0" max="4"');
  if (op.type === 'text_overlay') return [
    `<label class="wide">Text<textarea data-key="text" rows="2">${escapeHtml(op.text || '')}</textarea></label>`,
    selectField('Position', 'position', op.position || 'bottom', [['top', 'Top'], ['center', 'Centre'], ['bottom', 'Bottom']]),
    selectField('Font', 'font_family', op.font_family || 'DejaVu Sans', [['DejaVu Sans', 'Clean sans'], ['Liberation Sans', 'Liberation Sans'], ['Liberation Serif', 'Serif'], ['Liberation Mono', 'Mono']]),
    field('Font size', 'font_size', op.font_size || 48, 'number', 'min="8" max="240"'),
    field('Text colour', 'font_color', op.font_color || 'white'),
    field('Background', 'text_background_color', op.text_background_color || 'black@0.45'),
  ].join('');
  if (op.type === 'split_screen') return `<label class="wide">Second video<select data-key="secondary_asset_id">${assetOptions('video', op.secondary_asset_id)}</select></label>` + selectField('Layout', 'layout', op.layout || 'side_by_side', [['side_by_side', 'Side by side'], ['stacked', 'Top and bottom']]) + field('First video size', 'ratio', op.ratio || .5, 'number', 'step="0.05" min="0.15" max="0.85"');
  if (op.type === 'picture_in_picture') return `<label class="wide">Overlay video<select data-key="secondary_asset_id">${assetOptions('video', op.secondary_asset_id)}</select></label>` + field('Width', 'width', op.width || 360, 'number', 'min="32"') + field('Height', 'height', op.height || 202, 'number', 'min="32"') + field('X position', 'x', op.x ?? 20, 'number') + field('Y position', 'y', op.y ?? 20, 'number') + field('Show from', 'start_seconds', op.start_seconds, 'number', 'step="0.1" min="0"') + field('Until', 'end_seconds', op.end_seconds, 'number', 'step="0.1" min="0"');
  if (op.type === 'masked_video') return `<label class="wide">Background video<select data-key="secondary_asset_id">${assetOptions('video', op.secondary_asset_id)}</select></label>` + selectField('Shape', 'shape', op.shape || 'star', [['star', 'Star'], ['circle', 'Circle'], ['heart', 'Heart'], ['triangle', 'Triangle']]) + field('Width', 'width', op.width || 360, 'number', 'min="32"') + field('Height', 'height', op.height || 360, 'number', 'min="32"') + field('X position', 'x', op.x ?? 40, 'number') + field('Y position', 'y', op.y ?? 40, 'number') + field('Rotation', 'rotation', op.rotation || 0, 'number') + field('Soft edge', 'feather', op.feather || 0, 'number', 'min="0" max="100"') + field('Opacity', 'opacity', op.opacity ?? 1, 'number', 'step="0.05" min="0" max="1"') + field('Show from', 'start_seconds', op.start_seconds, 'number', 'step="0.1" min="0"') + field('Until', 'end_seconds', op.end_seconds, 'number', 'step="0.1" min="0"');
  if (op.type === 'music') return `<label class="wide">Music<select data-key="source_asset_id">${assetOptions('audio', op.source_asset_id)}</select></label>` + field('Music volume', 'volume', op.volume ?? .35, 'number', 'step="0.05" min="0" max="4"') + field('Start time', 'start_seconds', op.start_seconds || 0, 'number', 'step="0.1" min="0"') + field('End time', 'end_seconds', op.end_seconds, 'number', 'step="0.1" min="0"') + field('Fade in', 'fade_in_seconds', op.fade_in_seconds || 0, 'number', 'step="0.1" min="0"') + field('Fade out', 'fade_out_seconds', op.fade_out_seconds || 0, 'number', 'step="0.1" min="0"') + `<label class="switch-label wide"><input data-key="ducking" type="checkbox" ${op.ducking ? 'checked' : ''}>Lower music automatically while someone is speaking</label>`;
  if (op.type === 'style_transfer') return `<label class="wide">Style description<textarea data-key="style_prompt" rows="3">${escapeHtml(op.style_prompt || '')}</textarea></label>`;
  return '<p class="empty-state wide">This change has no extra settings.</p>';
}

function operationEditor(op, index) {
  const open = selectedOperationIndex === index ? 'open' : '';
  const visualAction = ['masked_video', 'picture_in_picture'].includes(op.type)
    ? '<button type="button" class="operation-action edit-on-video">Position on video</button>' : '';
  return `<details class="operation" data-index="${index}" ${open}>
    <summary class="operation-summary">
      <span class="operation-title"><strong>${escapeHtml(operationName(op))}</strong><span>${escapeHtml(operationSummary(op))}</span></span>
    </summary>
    <div class="operation-body">
      <div class="operation-toggle-row">
        <label class="switch-label"><input data-key="enabled" type="checkbox" ${op.enabled !== false ? 'checked' : ''}>Use this change</label>
      </div>
      <div class="control-grid">${operationControls(op)}</div>
      ${motionEditor(op, index)}
      <div class="operation-actions">${visualAction}<button type="button" class="operation-action danger remove-op">Remove</button></div>
    </div>
  </details>`;
}

function renderAssets() {
  const assets = project?.assets || [];
  assetsNode.innerHTML = assets.length ? assets.map((asset) => `<div class="asset-chip"><div><strong>${escapeHtml(asset.filename)}</strong><span>${escapeHtml(asset.kind)}</span></div></div>`).join('') : '<div class="empty-state">No extra media yet. Add a second video for backgrounds or split screen, or add a music file.</div>';
}

function renderOperations() {
  editCount.textContent = String(operations.length);
  operationsNode.innerHTML = operations.length ? operations.map(operationEditor).join('') : '<div class="empty-state">No changes yet. Open the AI tab and describe what you want in plain language.</div>';
  bindOperationEvents();
  updateBottomAction();
  renderDirectLayer();
}

function bindOperationEvents() {
  operationsNode.querySelectorAll('.operation').forEach((card) => {
    const index = Number(card.dataset.index);
    card.addEventListener('toggle', () => {
      if (card.open) {
        selectedOperationIndex = index;
        if (!['masked_video', 'picture_in_picture'].includes(operations[index].type)) selectedMotionIndex = null;
        renderDirectLayer();
      }
    });
    card.querySelectorAll('[data-key]').forEach((input) => {
      input.addEventListener('input', () => updateOperation(index, input));
      input.addEventListener('change', () => updateOperation(index, input));
    });
    card.querySelector('.remove-op')?.addEventListener('click', () => {
      operations.splice(index, 1);
      selectedOperationIndex = null;
      selectedMotionIndex = null;
      markDirty();
      renderOperations();
    });
    card.querySelector('.edit-on-video')?.addEventListener('click', () => selectVisualLayer(index, null));
    card.querySelector('.add-keyframe')?.addEventListener('click', () => addKeyframe(index));
    card.querySelectorAll('[data-motion-select]').forEach((button) => button.addEventListener('click', () => {
      const motionIndex = Number(button.dataset.motionSelect);
      selectVisualLayer(index, motionIndex);
      const frame = operations[index].motion_keyframes?.[motionIndex];
      if (frame && Number.isFinite(Number(frame.time_seconds))) preview.currentTime = Number(frame.time_seconds);
      renderOperations();
      if (isMobileLayout()) previewStage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }));
    card.querySelectorAll('[data-motion-key]').forEach((input) => {
      input.addEventListener('input', () => updateSelectedMotion(index, input, false));
      input.addEventListener('change', () => updateSelectedMotion(index, input, input.dataset.motionKey === 'time_seconds'));
    });
    card.querySelector('.remove-selected-keyframe')?.addEventListener('click', () => {
      if (selectedOperationIndex !== index || selectedMotionIndex == null) return;
      operations[index].motion_keyframes.splice(selectedMotionIndex, 1);
      selectedMotionIndex = null;
      markDirty();
      renderOperations();
    });
  });
}

function syncProposal() {
  if (pendingProposal) pendingProposal.operations = operations.slice(proposalStartIndex);
}

function markDirty() {
  operationsDirty = true;
  syncProposal();
  updateBottomAction();
}

function updateOperation(index, input) {
  const key = input.dataset.key;
  let value = input.type === 'checkbox' ? input.checked : input.value;
  if (input.type === 'number') value = value === '' ? null : Number(value);
  if (key === 'speed') value = Number(value);
  operations[index][key] = value;
  markDirty();
  renderDirectLayer();
}

function updateSelectedMotion(index, input, reorder) {
  if (selectedOperationIndex !== index || selectedMotionIndex == null) return;
  const frame = operations[index].motion_keyframes[selectedMotionIndex];
  const key = input.dataset.motionKey;
  let value = input.value;
  if (input.type === 'number') value = value === '' ? 0 : Number(value);
  frame[key] = value;
  if (reorder) {
    const selectedFrame = frame;
    operations[index].motion_keyframes.sort((a, b) => Number(a.time_seconds) - Number(b.time_seconds));
    selectedMotionIndex = operations[index].motion_keyframes.indexOf(selectedFrame);
  }
  markDirty();
  renderDirectLayer();
}

function easingProgress(name, p) {
  const x = Math.min(1, Math.max(0, p));
  if (name === 'ease_in') return x * x;
  if (name === 'ease_out') return 1 - (1 - x) * (1 - x);
  if (name === 'ease_in_out') return x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
  return x;
}

function positionAtTime(op, time) {
  const frames = [...(op.motion_keyframes || [])].sort((a, b) => Number(a.time_seconds) - Number(b.time_seconds));
  if (!frames.length) return { x: Number(op.x ?? 40), y: Number(op.y ?? 40) };
  if (time <= Number(frames[0].time_seconds)) return { x: Number(frames[0].x), y: Number(frames[0].y) };
  if (time >= Number(frames.at(-1).time_seconds)) return { x: Number(frames.at(-1].x), y: Number(frames.at(-1).y) };
  for (let i = 0; i < frames.length - 1; i += 1) {
    const a = frames[i];
    const b = frames[i + 1];
    const ta = Number(a.time_seconds); const tb = Number(b.time_seconds);
    if (time >= ta && time <= tb) {
      const p = easingProgress(a.easing || 'linear', (time - ta) / Math.max(.001, tb - ta));
      return { x: Number(a.x) + (Number(b.x) - Number(a.x)) * p, y: Number(a.y) + (Number(b.y) - Number(a.y)) * p };
    }
  }
  return { x: Number(op.x ?? 40), y: Number(op.y ?? 40) };
}

function addKeyframe(index) {
  const op = operations[index];
  op.motion_keyframes ||= [];
  let time = Number.isFinite(preview.currentTime) ? Number(preview.currentTime.toFixed(2)) : 0;
  while (op.motion_keyframes.some((frame) => Math.abs(Number(frame.time_seconds) - time) < .001)) time = Number((time + .1).toFixed(2));
  const position = positionAtTime(op, time);
  const frame = { time_seconds: time, x: Math.round(position.x), y: Math.round(position.y), easing: 'ease_in_out' };
  op.motion_keyframes.push(frame);
  op.motion_keyframes.sort((a, b) => Number(a.time_seconds) - Number(b.time_seconds));
  selectedOperationIndex = index;
  selectedMotionIndex = op.motion_keyframes.indexOf(frame);
  markDirty();
  renderOperations();
  showToast('Motion point added. Drag the shape to set its position.');
}

function selectVisualLayer(index, motionIndex) {
  selectedOperationIndex = index;
  selectedMotionIndex = motionIndex;
  renderDirectLayer();
  selectionHint.classList.remove('hidden');
  if (isMobileLayout()) previewStage.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function sourceDimensions() {
  return {
    width: Number(project?.metadata?.dimensions?.width || 1280),
    height: Number(project?.metadata?.dimensions?.height || 720),
  };
}

function videoContentRect() {
  const stageRect = previewStage.getBoundingClientRect();
  const videoRect = preview.getBoundingClientRect();
  const source = sourceDimensions();
  const boxW = videoRect.width;
  const boxH = videoRect.height;
  const sourceRatio = source.width / source.height;
  const boxRatio = boxW / boxH;
  let width; let height; let left; let top;
  if (boxRatio > sourceRatio) {
    height = boxH; width = height * sourceRatio; left = videoRect.left - stageRect.left + (boxW - width) / 2; top = videoRect.top - stageRect.top;
  } else {
    width = boxW; height = width / sourceRatio; left = videoRect.left - stageRect.left; top = videoRect.top - stageRect.top + (boxH - height) / 2;
  }
  return { left, top, width, height };
}

function renderDirectLayer() {
  if (selectedOperationIndex == null || !operations[selectedOperationIndex] || !['masked_video', 'picture_in_picture'].includes(operations[selectedOperationIndex].type)) {
    directLayer.classList.add('hidden');
    selectionHint.classList.add('hidden');
    return;
  }
  const op = operations[selectedOperationIndex];
  const source = sourceDimensions();
  const rect = videoContentRect();
  const frame = selectedMotionIndex != null ? op.motion_keyframes?.[selectedMotionIndex] : null;
  const position = frame ? { x: Number(frame.x), y: Number(frame.y) } : positionAtTime(op, Number(preview.currentTime || 0));
  const scaleX = rect.width / source.width;
  const scaleY = rect.height / source.height;
  directLayer.style.left = `${rect.left + position.x * scaleX}px`;
  directLayer.style.top = `${rect.top + position.y * scaleY}px`;
  directLayer.style.width = `${Math.max(18, Number(op.width || 360) * scaleX)}px`;
  directLayer.style.height = `${Math.max(18, Number(op.height || 360) * scaleY)}px`;
  directLayer.className = 'direct-layer';
  if (op.type === 'masked_video') directLayer.classList.add(`shape-${op.shape || 'star'}`);
  directLayerLabel.textContent = frame ? `Position at ${Number(frame.time_seconds).toFixed(1)}s` : 'Drag to move';
  directLayer.classList.remove('hidden');
  selectionHint.classList.remove('hidden');
}

function setVisualPosition(op, x, y) {
  if (selectedMotionIndex != null && op.motion_keyframes?.[selectedMotionIndex]) {
    op.motion_keyframes[selectedMotionIndex].x = Math.round(x);
    op.motion_keyframes[selectedMotionIndex].y = Math.round(y);
  } else {
    op.x = Math.round(x);
    op.y = Math.round(y);
  }
}

function beginPointer(event, mode) {
  if (selectedOperationIndex == null) return;
  event.preventDefault();
  const op = operations[selectedOperationIndex];
  const frame = selectedMotionIndex != null ? op.motion_keyframes?.[selectedMotionIndex] : null;
  const position = frame ? { x: Number(frame.x), y: Number(frame.y) } : positionAtTime(op, Number(preview.currentTime || 0));
  pointerState = {
    mode,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    opX: position.x,
    opY: position.y,
    width: Number(op.width || 360),
    height: Number(op.height || 360),
  };
  directLayer.setPointerCapture?.(event.pointerId);
}

directLayer.addEventListener('pointerdown', (event) => {
  if (event.target === resizeHandle) return;
  beginPointer(event, 'move');
});
resizeHandle.addEventListener('pointerdown', (event) => beginPointer(event, 'resize'));

directLayer.addEventListener('pointermove', (event) => {
  if (!pointerState || pointerState.pointerId !== event.pointerId || selectedOperationIndex == null) return;
  const op = operations[selectedOperationIndex];
  const rect = videoContentRect();
  const source = sourceDimensions();
  const dx = (event.clientX - pointerState.startX) * source.width / rect.width;
  const dy = (event.clientY - pointerState.startY) * source.height / rect.height;
  if (pointerState.mode === 'move') {
    setVisualPosition(op, pointerState.opX + dx, pointerState.opY + dy);
  } else {
    op.width = Math.max(32, Math.round(pointerState.width + dx));
    op.height = Math.max(32, Math.round(pointerState.height + dy));
  }
  operationsDirty = true;
  syncProposal();
  renderDirectLayer();
});

function endPointer(event) {
  if (!pointerState || pointerState.pointerId !== event.pointerId) return;
  pointerState = null;
  markDirty();
  renderOperations();
}
directLayer.addEventListener('pointerup', endPointer);
directLayer.addEventListener('pointercancel', endPointer);

fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  uploadButton.disabled = !file;
  if (file) {
    uploadLabelTitle.textContent = file.name;
    uploadLabelSubtitle.textContent = 'Ready to upload';
  } else {
    uploadLabelTitle.textContent = 'Tap to choose a video';
    uploadLabelSubtitle.textContent = 'MP4, MOV and other common video formats';
  }
});

uploadButton.addEventListener('click', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  uploadButton.disabled = true;
  uploadButton.textContent = 'Uploading…';
  setStatus('Uploading…');
  const body = new FormData(); body.append('file', file);
  try {
    project = await api('/api/projects', { method: 'POST', body });
    operations = project.operations || [];
    operationsDirty = false;
    preview.src = project.source_url;
    projectNameNode.textContent = project.filename || file.name;
    metadataNode.textContent = `${project.metadata.duration_seconds}s · ${project.metadata.dimensions.width}×${project.metadata.dimensions.height}`;
    uploadPanel.classList.add('hidden');
    workspace.classList.remove('hidden');
    bottomNav.classList.remove('hidden');
    renderAssets(); renderOperations(); switchTab('ai');
    addMessage('assistant', 'Your video is ready. Tell me what you want to change. I will suggest the edit first, so you can review it before rendering.');
    setStatus('Ready');
    showToast('Video ready');
  } catch (error) {
    setStatus('Upload failed');
    showToast(error.message);
    uploadButton.disabled = false;
  } finally {
    uploadButton.textContent = 'Continue';
  }
});

assetInput.addEventListener('change', async () => {
  const file = assetInput.files[0];
  if (!file || !project) return;
  setStatus('Adding media…');
  const body = new FormData(); body.append('file', file); body.append('kind', 'auto');
  try {
    await api(`/api/projects/${project.id}/assets`, { method: 'POST', body });
    project = await api(`/api/projects/${project.id}`);
    renderAssets(); renderOperations();
    setStatus('Ready');
    showToast(`${file.name} added`);
  } catch (error) {
    setStatus('Failed');
    showToast(error.message);
  }
  assetInput.value = '';
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!project) return;
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  promptInput.value = '';
  addMessage('user', prompt);
  setStatus('AI is planning…');
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  submit.textContent = 'Thinking…';
  try {
    const result = await api(`/api/projects/${project.id}/commands`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt })
    });
    pendingPrompt = prompt;
    pendingProposal = result.plan;
    proposalStartIndex = (project.operations || []).length;
    operations = [...(project.operations || []), ...(result.plan.operations || [])];
    operationsDirty = true;
    addMessage('assistant', result.assistant_message || 'I prepared an edit proposal.');
    proposalNote.textContent = 'AI has prepared changes, but nothing has been rendered yet. Open any card to adjust it, then apply.';
    proposalNote.classList.remove('hidden');
    renderOperations();
    switchTab('edits');
    setStatus('Review changes');
    showToast('Review the AI changes before applying');
  } catch (error) {
    addMessage('assistant', error.message);
    setStatus('Failed');
    showToast(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = 'Ask AI';
  }
});

async function applyProposal() {
  if (!pendingProposal || !project) return;
  const proposed = operations.slice(proposalStartIndex);
  setStatus('Rendering…');
  try {
    const result = await api(`/api/projects/${project.id}/apply-plan`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: pendingPrompt, assistant_message: pendingProposal.assistant_message, operations: proposed })
    });
    await pollJob(result.job_id);
    project = await api(`/api/projects/${project.id}`);
    operations = project.operations || [];
    pendingProposal = null;
    pendingPrompt = '';
    proposalStartIndex = operations.length;
    operationsDirty = false;
    proposalNote.classList.add('hidden');
    renderOperations();
    showToast('AI changes applied');
  } catch (error) {
    setStatus('Failed');
    showToast(error.message);
  }
}
applyProposalButton.addEventListener('click', applyProposal);
desktopApplyButton?.addEventListener('click', applyProposal);

async function saveOperations() {
  if (!project || pendingProposal) return;
  setStatus('Rendering…');
  try {
    const result = await api(`/api/projects/${project.id}/operations`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operations })
    });
    await pollJob(result.job_id);
    project = await api(`/api/projects/${project.id}`);
    operations = project.operations || [];
    operationsDirty = false;
    renderOperations();
    showToast('Preview updated');
  } catch (error) {
    setStatus('Failed');
    showToast(error.message);
  }
}
saveOperationsButton.addEventListener('click', saveOperations);
mobileSaveButton.addEventListener('click', saveOperations);

undoButton.addEventListener('click', async () => {
  if (!project) return;
  setStatus('Undoing…');
  try {
    const result = await api(`/api/projects/${project.id}/undo`, { method: 'POST' });
    await pollJob(result.job_id);
    project = await api(`/api/projects/${project.id}`);
    operations = project.operations || [];
    operationsDirty = false;
    pendingProposal = null;
    proposalNote.classList.add('hidden');
    selectedOperationIndex = null; selectedMotionIndex = null;
    renderOperations();
    showToast('Last AI edit undone');
  } catch (error) {
    setStatus('Failed');
    showToast(error.message);
  }
});

async function pollJob(jobId) {
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 900));
    const job = await api(`/api/jobs/${jobId}`);
    if (job.status === 'completed') {
      preview.src = `${job.output_url}?t=${Date.now()}`;
      preview.load();
      setStatus('Ready');
      return;
    }
    if (job.status === 'failed') throw new Error(job.error || 'Rendering failed');
    setStatus(job.status === 'running' ? 'Rendering…' : 'Waiting…');
  }
}

$$('.nav-item').forEach((button) => button.addEventListener('click', () => switchTab(button.dataset.tab)));
$$('[data-prompt]').forEach((button) => button.addEventListener('click', () => {
  promptInput.value = button.dataset.prompt;
  promptInput.focus();
}));
preview.addEventListener('timeupdate', () => {
  if (selectedOperationIndex != null && selectedMotionIndex == null) renderDirectLayer();
});
preview.addEventListener('loadedmetadata', renderDirectLayer);
window.addEventListener('resize', () => { renderDirectLayer(); updateBottomAction(); });

switchTab('ai');
