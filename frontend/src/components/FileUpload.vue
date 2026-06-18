<template>
  <div class="upload-panel">
    <!-- Drop zone — uses <button> so it's keyboard accessible -->
    <button
      type="button"
      class="drop-zone"
      :class="{ 'drag-over': dragOver, 'has-file': !!file }"
      :aria-label="file ? `已选择文件 ${fileName}，点击更换` : '点击或拖放文件以上传'"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
      @click="triggerInput"
      @keydown.enter.space.prevent="triggerInput"
    >
      <input
        ref="inputRef"
        type="file"
        class="visually-hidden"
        :accept="accept"
        @change="onFileChange"
        tabindex="-1"
      />

      <!-- Empty state -->
      <template v-if="!file">
        <div class="drop-icon" aria-hidden="true">
          <span class="reticle-corner corner-tl"></span>
          <span class="reticle-corner corner-tr"></span>
          <span class="reticle-corner corner-bl"></span>
          <span class="reticle-corner corner-br"></span>
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
            <path d="M12 16V4M7.5 8.5L12 4l4.5 4.5M5 14v4a2 2 0 002 2h10a2 2 0 002-2v-4"
              stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <span class="drop-code">INPUT CHANNEL READY</span>
        <p class="drop-title">投放待识别文档</p>
        <p class="drop-hint">拖放至此，或点击浏览本地文件</p>
        <div class="format-row">
          <span>JPG</span><span>PNG</span><span>WEBP</span><span>PDF</span><span>TIFF</span>
        </div>
      </template>

      <!-- File card -->
      <template v-else>
        <div class="file-card">
          <!-- Image preview (for image files with a data URL) -->
          <div class="file-preview" v-if="previewUrl">
            <img :src="previewUrl" :alt="fileName" />
            <span class="file-type-badge">{{ fileExt.toUpperCase() }}</span>
          </div>
          <!-- Type-specific icon (PDF, TIFF, or no preview available) -->
          <div class="file-preview file-preview--icon" v-else>
            <!-- PDF icon: document with folded corner + PDF label -->
            <svg v-if="fileExt === 'pdf'" width="36" height="36" viewBox="0 0 48 48" fill="none">
              <rect x="5" y="3" width="38" height="42" rx="3" stroke="currentColor" stroke-width="1.5" opacity="0.6"/>
              <path d="M15 3v12a3 3 0 003 3h12" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
              <text x="24" y="38" text-anchor="middle" font-size="10" font-weight="700" fill="currentColor" opacity="0.9" font-family="JetBrains Mono, monospace">PDF</text>
            </svg>
            <!-- TIFF icon: image frame + placeholder lines -->
            <svg v-else-if="fileExt === 'tiff' || fileExt === 'tif'" width="36" height="36" viewBox="0 0 48 48" fill="none">
              <rect x="4" y="6" width="40" height="36" rx="3" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
              <circle cx="17" cy="22" r="4" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
              <path d="M21 30l-4-4" stroke="currentColor" stroke-width="1.5" opacity="0.4"/>
              <rect x="26" y="18" width="18" height="2" rx="1" fill="currentColor" opacity="0.3"/>
              <rect x="26" y="24" width="16" height="2" rx="1" fill="currentColor" opacity="0.25"/>
              <rect x="26" y="30" width="10" height="2" rx="1" fill="currentColor" opacity="0.2"/>
            </svg>
            <!-- Generic image icon (any image type without preview) -->
            <svg v-else-if="isImage" width="36" height="36" viewBox="0 0 48 48" fill="none">
              <rect x="4" y="6" width="40" height="36" rx="3" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
              <circle cx="17" cy="20" r="3" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
              <path d="M6 34l12-12 8 8 6-4 12 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.4"/>
            </svg>
            <!-- Generic document icon (ultimate fallback) -->
            <svg v-else width="36" height="36" viewBox="0 0 48 48" fill="none">
              <rect x="6" y="4" width="36" height="40" rx="3" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
              <path d="M6 16h36M16 28h16M16 34h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.4"/>
            </svg>
          </div>
          <div class="file-info">
            <span class="file-name">{{ fileName }}</span>
            <span class="file-meta">
              <span class="file-size">{{ fileSize }}</span>
              <span class="file-type-tag">{{ fileExt.toUpperCase() }}</span>
            </span>
          </div>
          <button class="file-remove" @click.stop="$emit('clear')" title="移除">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      </template>

      <!-- Scan line animation on drag -->
      <div v-if="dragOver" class="scan-line"></div>
    </button>

    <!-- Options bar (shown when file is loaded) -->
    <div v-if="file" class="options-bar">
      <div class="options-left">
        <label class="option" v-if="isPdf">
          <span class="option-label">DPI</span>
          <input
            type="number"
            class="option-input"
            :value="dpi"
            @input="$emit('update:dpi', Number($event.target.value))"
            min="72"
            max="600"
            step="10"
          />
        </label>
        <label class="option" v-if="isPdf">
          <span class="option-label">最大页</span>
          <input
            type="number"
            class="option-input"
            :value="maxPages"
            @input="$emit('update:maxPages', Number($event.target.value))"
            min="0"
            placeholder="全部"
          />
        </label>
      </div>
      <button
        class="btn-run"
        :disabled="loading"
        @click="$emit('run')"
      >
        <template v-if="loading">
          <span class="spinner"></span>
          识别中…
        </template>
        <template v-else>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="11" cy="11" r="8"/>
            <path d="M21 21l-4.35-4.35"/>
          </svg>
          开始识别
        </template>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  file: { type: File, default: null },
  previewUrl: { type: String, default: null },
  fileName: { type: String, default: '' },
  fileSize: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  dpi: { type: Number, default: 200 },
  maxPages: { type: Number, default: 0 },
  mode: { type: String, default: 'image' },
})

const emit = defineEmits(['update:file', 'clear', 'run', 'update:dpi', 'update:maxPages'])

const inputRef = ref(null)
const dragOver = ref(false)

const accept = '.jpg,.jpeg,.png,.webp,.bmp,.pdf,.tiff,.tif'

const isPdf = computed(() => props.file?.name?.toLowerCase().endsWith('.pdf'))

const fileExt = computed(() => {
  if (!props.fileName) return '?'
  const dot = props.fileName.lastIndexOf('.')
  return dot >= 0 ? props.fileName.slice(dot + 1).toLowerCase() : '?'
})

const isImage = computed(() => {
  const ext = fileExt.value
  return ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'tif'].includes(ext)
})

function triggerInput() {
  if (!props.file) inputRef.value?.click()
}

function onDrop(e) {
  dragOver.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) handleFile(f)
}

function onFileChange(e) {
  const f = e.target?.files?.[0]
  if (f) handleFile(f)
  if (inputRef.value) inputRef.value.value = ''
}

function handleFile(f) {
  const url = f.type.startsWith('image/') ? URL.createObjectURL(f) : null
  emit('update:file', f, url)
}
</script>

<style scoped>
.upload-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Drop zone ────────────────────────────────── */
.drop-zone {
  position: relative;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 34px 24px 30px;
  text-align: center;
  cursor: pointer;
  transition: all 0.35s ease;
  background:
    linear-gradient(135deg, var(--signal-glow), transparent 42%),
    color-mix(in srgb, var(--bg-elevated) 58%, transparent);
  overflow: hidden;
  /* reset <button> defaults */
  width: 100%;
  font-family: inherit;
  font-size: inherit;
  color: inherit;
  appearance: none;
  -webkit-appearance: none;
}
.drop-zone::before {
  content: '';
  position: absolute;
  inset: 7px;
  border: 1px dashed color-mix(in srgb, var(--text-muted) 22%, transparent);
  border-radius: calc(var(--radius-lg) - 5px);
  pointer-events: none;
  transition: border-color .3s;
}
.drop-zone:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.drop-zone:hover {
  border-color: color-mix(in srgb, var(--signal) 52%, transparent);
  transform: translateY(-2px);
  box-shadow: 0 16px 36px rgba(0,0,0,.2), inset 0 0 34px var(--signal-glow);
}
.drop-zone:hover::before { border-color: color-mix(in srgb, var(--signal) 34%, transparent); }
.drop-zone.drag-over {
  border-color: var(--accent);
  background: var(--accent-glow);
  transform: scale(1.01);
}
.drop-zone.has-file {
  padding: 14px;
  border-style: solid;
  cursor: default;
  border-color: var(--border-subtle);
}

.drop-icon {
  width: 72px;
  height: 72px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  color: var(--signal);
  background: radial-gradient(circle, var(--signal-glow), transparent 68%);
  transition: transform .35s, color 0.3s;
}
.drop-zone:hover .drop-icon { transform: scale(1.05); }
.reticle-corner {
  position: absolute;
  width: 15px;
  height: 15px;
  border-color: var(--signal);
  border-style: solid;
  opacity: .65;
}
.corner-tl { top: 0; left: 0; border-width: 1px 0 0 1px; }
.corner-tr { top: 0; right: 0; border-width: 1px 1px 0 0; }
.corner-bl { bottom: 0; left: 0; border-width: 0 0 1px 1px; }
.corner-br { bottom: 0; right: 0; border-width: 0 1px 1px 0; }
.drop-code {
  display: block;
  margin-bottom: 7px;
  font-family: var(--font-mono);
  font-size: .57rem;
  letter-spacing: .16em;
  color: var(--signal);
}

.drop-title {
  font-family: var(--font-display);
  font-size: 1.15rem;
  color: var(--text-primary);
  margin-bottom: 6px;
}
.drop-hint {
  font-size: 0.78rem;
  color: var(--text-muted);
}
.format-row {
  display: flex;
  justify-content: center;
  gap: 5px;
  margin-top: 15px;
}
.format-row span {
  padding: 2px 6px;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: .53rem;
  letter-spacing: .05em;
  color: var(--text-muted);
}

/* ── Scan line ────────────────────────────────── */
.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent,
    var(--accent) 20%,
    var(--accent) 80%,
    transparent
  );
  animation: scan-line 1.8s ease-in-out infinite;
  box-shadow: 0 0 12px var(--accent-glow), 0 0 4px var(--accent);
}

/* ── File card ────────────────────────────────── */
.file-card {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.file-preview {
  width: 64px;
  height: 64px;
  border-radius: 9px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-deep);
  border: 1px solid var(--border-active);
  box-shadow: var(--shadow-sm);
}
.file-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.file-preview--icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  position: relative;
}

/* Type badge overlay on image thumbnails */
.file-type-badge {
  position: absolute;
  bottom: 3px;
  right: 3px;
  font-family: var(--font-mono);
  font-size: 0.5rem;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 2px;
  background: rgba(13, 13, 12, 0.85);
  color: var(--accent);
  letter-spacing: 0.05em;
}

.file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
}
.file-name {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.file-size {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.file-type-tag {
  font-family: var(--font-mono);
  font-size: 0.58rem;
  font-weight: 500;
  padding: 0 4px;
  border-radius: 2px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  letter-spacing: 0.05em;
  line-height: 1.4;
}

.file-remove {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all 0.2s;
}
.file-remove:hover {
  background: rgba(194,85,77,0.15);
  color: var(--error);
}

/* ── Options bar ──────────────────────────────── */
.options-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-elevated) 58%, transparent);
  flex-wrap: wrap;
}
.options-left {
  display: flex;
  gap: 14px;
}
.option {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--text-secondary);
}
.option-label { font-weight: 500; }
.option-input {
  width: 58px;
  padding: 4px 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  text-align: center;
  transition: border-color 0.2s;
}
.option-input:focus {
  outline: none;
  border-color: var(--accent);
}

/* ── Run button ───────────────────────────────── */
.btn-run {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 20px;
  background: linear-gradient(135deg, #ffc15a, var(--accent));
  color: #19130a;
  font-weight: 600;
  font-size: 0.85rem;
  border-radius: 8px;
  transition: all 0.25s;
  letter-spacing: 0.02em;
}
.btn-run:hover:not(:disabled) {
  background: #f0b850;
  box-shadow: 0 8px 26px var(--accent-glow);
  transform: translateY(-1px);
}
.btn-run:active:not(:disabled) { transform: translateY(0); }
.btn-run:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* spinner */
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
