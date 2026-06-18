<template>
  <div class="overlay-result">

    <!-- ── Header ── -->
    <div class="result-header">
      <div class="header-left">
        <h2 class="result-title">识别结果</h2>
        <div class="result-meta">
          <span>{{ totalLines }} 行</span>
          <span class="sep">·</span>
          <span>平均置信度 <strong>{{ avgScore }}%</strong></span>
          <template v-if="imgW">
            <span class="sep">·</span>
            <span class="meta-dim">{{ imgW }}×{{ imgH }}</span>
          </template>
        </div>
      </div>
      <div class="result-actions">
        <button
          v-if="previewUrl"
          class="action-btn"
          :class="{ active: showOverlay }"
          title="显示/隐藏检测框"
          @click="showOverlay = !showOverlay"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <path d="M9 9h6M9 12h4"/>
          </svg>
          {{ showOverlay ? '隐藏框' : '显示框' }}
        </button>
        <button class="action-btn" @click="exportTxt" title="下载 TXT">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出
        </button>
        <button class="action-btn" :class="{ success: copied }" @click="copyAll">
          <svg v-if="!copied" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="9" y="9" width="13" height="13" rx="2"/>
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M20 6L9 17l-5-5"/>
          </svg>
          {{ copied ? '已复制' : '复制全部' }}
        </button>
      </div>
    </div>

    <!-- ── Search bar ── -->
    <div class="search-bar">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
      </svg>
      <input
        class="search-input"
        type="text"
        placeholder="搜索识别文本…"
        v-model="searchQuery"
        @focus="searchFocused = true"
        @blur="searchFocused = false"
      />
      <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''" title="清空">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
      <span v-if="searchQuery" class="search-count">
        {{ filteredIndices.length }} / {{ totalLines }}
      </span>
      <label class="search-toggle" title="仅显示低置信度（＜80%）">
        <input type="checkbox" v-model="filterLowConf" />
        <span>低置信</span>
      </label>
    </div>

    <!-- ── Body: split or list-only ── -->
    <div class="result-body" :class="{ split: previewUrl && imgLoaded }">

      <!-- Image pane (only when preview available) -->
      <div v-if="previewUrl" class="image-pane" ref="imagePaneRef"
        @wheel.prevent="onWheel"
        @mousedown="onPanStart"
        @mousemove="onPanMove"
        @mouseup="onPanEnd"
        @mouseleave="onPanEnd"
      >
        <!-- Zoom controls -->
        <div class="zoom-controls" @mousedown.stop>
          <button class="zoom-btn" @click="zoomBy(0.25)" title="放大">＋</button>
          <span class="zoom-label">{{ Math.round(scale * 100) }}%</span>
          <button class="zoom-btn" @click="zoomBy(-0.25)" title="缩小">－</button>
          <button class="zoom-btn" @click="resetZoom" title="重置">⟳</button>
        </div>

        <div
          class="image-wrap"
          :style="{
            transform: `translate(${panX}px, ${panY}px) scale(${scale})`,
            cursor: isPanning ? 'grabbing' : (scale > 1 ? 'grab' : 'default'),
          }"
        >
          <img
            :src="previewUrl"
            class="source-img"
            alt="原始图片"
            @load="onImgLoad"
            @error="imgError = true"
            draggable="false"
          />
          <!-- SVG box overlay -->
          <svg
            v-if="imgLoaded && showOverlay && boxPolygons.length"
            class="boxes-svg"
            :viewBox="`0 0 ${imgW} ${imgH}`"
            preserveAspectRatio="xMidYMid meet"
            aria-hidden="true"
          >
            <g v-for="(pts, i) in boxPolygons" :key="i">
              <polygon
                :points="pts"
                class="box-poly"
                :class="{
                  hovered: hoveredIdx === i,
                  active: activeIdx === i,
                  'low-conf': isLowConf(i),
                }"
                @mouseenter="setHover(i)"
                @mouseleave="setHover(-1)"
                @click="handleBoxClick(i)"
              />
              <!-- Confidence badge on hovered box -->
              <text
                v-if="hoveredIdx === i"
                class="box-label"
                :x="boxLabelX(i)"
                :y="boxLabelY(i)"
              >{{ confLabel(i) }}</text>
            </g>
          </svg>
        </div>
      </div>

      <!-- Text lines pane -->
      <div class="lines-pane" ref="linesPaneRef">
        <ul class="text-lines" role="list">
          <li
            v-for="(item, i) in visibleLines"
            :key="item.origIdx"
            :ref="el => { lineEls[item.origIdx] = el }"
            class="text-line"
            :class="{
              hovered:   hoveredIdx === item.origIdx,
              active:    activeIdx  === item.origIdx,
              'low-conf': isLowConf(item.origIdx),
            }"
            tabindex="0"
            role="listitem"
            :aria-label="`第${item.origIdx+1}行：${item.text}`"
            @mouseenter="setHover(item.origIdx)"
            @mouseleave="setHover(-1)"
            @click="copyLine(item)"
            @keydown.enter.space.prevent="copyLine(item)"
          >
            <span class="line-num">{{ item.origIdx + 1 }}</span>
            <span class="line-text" v-html="highlight(item.text)"></span>
            <span class="line-score" :class="scoreClass(item.score)">
              {{ (item.score * 100).toFixed(1) }}%
            </span>
            <span class="line-copy-hint" aria-hidden="true">复制</span>
          </li>
        </ul>

        <div v-if="totalLines === 0" class="lines-empty">未识别到文本</div>
        <div v-else-if="visibleLines.length === 0" class="lines-empty">无匹配结果</div>
      </div>
    </div>

    <!-- Toast -->
    <Transition name="fade">
      <div v-if="toast" class="toast" role="status" aria-live="polite">{{ toast }}</div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  pages:      { type: Array,  default: () => [] },
  previewUrl: { type: String, default: null },
})

// ── State ──────────────────────────────────────
const copied       = ref(false)
const toast        = ref('')
const showOverlay  = ref(true)
const searchQuery  = ref('')
const searchFocused = ref(false)
const filterLowConf = ref(false)
const hoveredIdx   = ref(-1)
const activeIdx    = ref(-1)
const imgLoaded    = ref(false)
const imgError     = ref(false)
const imgW         = ref(0)
const imgH         = ref(0)
const lineEls      = ref({})
const linesPaneRef = ref(null)
const imagePaneRef = ref(null)

// ── Data extraction ─────────────────────────────
const allLines = computed(() => {
  const out = []
  for (const page of props.pages ?? []) {
    const texts  = page.texts  ?? []
    const scores = page.scores ?? []
    const boxes  = page.boxes  ?? []
    for (let i = 0; i < texts.length; i++) {
      out.push({ text: texts[i], score: scores[i] ?? 0, box: boxes[i] ?? null })
    }
  }
  return out
})

const totalLines = computed(() => allLines.value.length)

const avgScore = computed(() => {
  if (!totalLines.value) return '0.0'
  const sum = allLines.value.reduce((a, l) => a + l.score, 0)
  return ((sum / totalLines.value) * 100).toFixed(1)
})

// ── Filter / search ─────────────────────────────
const filteredIndices = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return allLines.value
    .map((l, i) => ({ ...l, origIdx: i }))
    .filter(l => {
      if (filterLowConf.value && l.score >= 0.8) return false
      if (q && !l.text.toLowerCase().includes(q)) return false
      return true
    })
})

const visibleLines = computed(() => filteredIndices.value)

// ── Box polygon helpers ─────────────────────────
function parseBoxPolygon(box) {
  if (!box || box.length === 0) return null
  // [[x,y],[x,y],[x,y],[x,y]] format
  if (Array.isArray(box[0])) {
    return box.map(p => `${p[0]},${p[1]}`).join(' ')
  }
  // flat [x1,y1,x2,y2] format → 4 corners
  if (typeof box[0] === 'number') {
    if (box.length === 4) {
      const [x1, y1, x2, y2] = box
      return `${x1},${y1} ${x2},${y1} ${x2},${y2} ${x1},${y2}`
    }
    // flat 8-number polygon [x1,y1,x2,y2,x3,y3,x4,y4]
    if (box.length === 8) {
      let pts = ''
      for (let i = 0; i < 8; i += 2) pts += `${box[i]},${box[i + 1]} `
      return pts.trim()
    }
  }
  return null
}

const boxPolygons = computed(() =>
  allLines.value.map(l => parseBoxPolygon(l.box))
)

function boxBounds(i) {
  const pts = boxPolygons.value[i]
  if (!pts) return null
  const coords = pts.split(' ').map(p => p.split(',').map(Number))
  const xs = coords.map(p => p[0])
  const ys = coords.map(p => p[1])
  return {
    x1: Math.min(...xs), y1: Math.min(...ys),
    x2: Math.max(...xs), y2: Math.max(...ys),
  }
}

function boxLabelX(i) {
  const b = boxBounds(i)
  return b ? b.x1 : 0
}
function boxLabelY(i) {
  const b = boxBounds(i)
  return b ? Math.max(b.y1 - 6, 12) : 0
}
function confLabel(i) {
  const s = allLines.value[i]?.score ?? 0
  return (s * 100).toFixed(1) + '%'
}

// ── Hover & active linkage ──────────────────────
function setHover(idx) {
  hoveredIdx.value = idx
  if (idx >= 0) scrollLineIntoView(idx)
}

function scrollLineIntoView(idx) {
  nextTick(() => {
    const el = lineEls.value[idx]
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

function handleBoxClick(i) {
  activeIdx.value = activeIdx.value === i ? -1 : i
  copyLine(allLines.value[i])
}

// ── Image load ──────────────────────────────────
function onImgLoad(e) {
  imgW.value = e.target.naturalWidth
  imgH.value = e.target.naturalHeight
  imgLoaded.value = true
}

// ── Score helpers ───────────────────────────────
function isLowConf(i) { return (allLines.value[i]?.score ?? 1) < 0.8 }

function scoreClass(score) {
  if (score >= 0.95) return 'score-high'
  if (score >= 0.80) return 'score-mid'
  return 'score-low'
}

// ── Search highlight ────────────────────────────
function highlight(text) {
  const q = searchQuery.value.trim()
  if (!q) return escapeHtml(text)
  const escaped = escapeHtml(text)
  const re = new RegExp(escapeRe(q), 'gi')
  return escaped.replace(re, m => `<mark class="hl">${m}</mark>`)
}
function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}
function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// ── Copy helpers ────────────────────────────────
let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 1800)
}

async function copyLine(item) {
  try {
    await navigator.clipboard.writeText(item.text ?? item)
    showToast('已复制到剪贴板')
  } catch {
    showToast('复制失败')
  }
}

async function copyAll() {
  const text = allLines.value.map(l => l.text).join('\n')
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    showToast('复制失败')
  }
}

// ── Export TXT ──────────────────────────────────
function exportTxt() {
  const text = allLines.value.map(l => l.text).join('\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url
  a.download = 'ocr-result.txt'
  a.click()
  URL.revokeObjectURL(url)
  showToast('已下载 TXT')
}

// ── Zoom & pan ──────────────────────────────────
const scale    = ref(1)
const panX     = ref(0)
const panY     = ref(0)
const isPanning = ref(false)
let panStartX = 0, panStartY = 0

const MIN_SCALE = 0.5
const MAX_SCALE = 8

function clampScale(s) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, s))
}

function zoomBy(delta) {
  scale.value = clampScale(scale.value + delta)
  if (scale.value <= 1) { panX.value = 0; panY.value = 0 }
}

function resetZoom() {
  scale.value = 1
  panX.value = 0
  panY.value = 0
}

function onWheel(e) {
  const delta = e.deltaY < 0 ? 0.15 : -0.15
  scale.value = clampScale(scale.value + delta)
  if (scale.value <= 1) { panX.value = 0; panY.value = 0 }
}

function onPanStart(e) {
  if (scale.value <= 1) return
  isPanning.value = true
  panStartX = e.clientX - panX.value
  panStartY = e.clientY - panY.value
}

function onPanMove(e) {
  if (!isPanning.value) return
  panX.value = e.clientX - panStartX
  panY.value = e.clientY - panStartY
}

function onPanEnd() {
  isPanning.value = false
}

// Reset active when pages change
watch(() => props.pages, () => {
  hoveredIdx.value = -1
  activeIdx.value  = -1
  imgLoaded.value  = false
  searchQuery.value = ''
  resetZoom()
})
</script>

<style scoped>
.overlay-result {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* ── Header ─────────────────────────────────────── */
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px 13px;
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
  flex-wrap: wrap;
}
.header-left {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
}
.result-title {
  font-size: 1.28rem;
  font-weight: 600;
  color: var(--text-primary);
}
.result-meta {
  font-size: 0.8rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 5px;
}
.result-meta strong { color: var(--text-secondary); font-weight: 500; }
.meta-dim { color: var(--text-muted); }
.sep { opacity: 0.5; }

.result-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
}
.action-btn:hover {
  color: var(--text-primary);
  border-color: var(--border-active);
  background: var(--bg-hover);
}
.action-btn.active {
  color: var(--accent);
  border-color: var(--accent-dim);
  background: var(--accent-glow);
}
.action-btn.success {
  color: var(--success);
  border-color: rgba(91,154,107,0.4);
}

/* ── Search bar ─────────────────────────────────── */
.search-bar {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: color-mix(in srgb, var(--bg-elevated) 65%, transparent);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  margin-bottom: 10px;
  flex-shrink: 0;
  transition: border-color 0.2s;
}
.search-bar:focus-within { border-color: var(--accent); }
.search-icon { color: var(--text-muted); flex-shrink: 0; }
.search-input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-family: var(--font-ui);
  font-size: 0.82rem;
}
.search-input::placeholder { color: var(--text-muted); }
.search-clear {
  color: var(--text-muted);
  padding: 2px;
  cursor: pointer;
  border-radius: 2px;
  transition: color 0.2s;
}
.search-clear:hover { color: var(--text-primary); }
.search-count {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--accent);
  flex-shrink: 0;
}
.search-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
}
.search-toggle input { accent-color: var(--accent); }

/* ── Body ───────────────────────────────────────── */
.result-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.result-body.split {
  flex-direction: row;
  gap: 10px;
  background: transparent;
}

/* ── Image pane ─────────────────────────────────── */
.image-pane {
  flex: 0 0 48%;
  min-width: 0;
  overflow: hidden;
  background:
    linear-gradient(rgba(94,216,210,.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(94,216,210,.025) 1px, transparent 1px),
    var(--bg-surface);
  background-size: 24px 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
}
.image-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transform-origin: center center;
  transition: transform 0.08s ease;
  will-change: transform;
}
.source-img {
  max-width: 100%;
  max-height: 100%;
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  user-select: none;
}

/* ── Zoom controls ──────────────────────────────── */
.zoom-controls {
  position: absolute;
  bottom: 10px;
  right: 10px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 2px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 3px 4px;
  opacity: 0.5;
  transition: opacity 0.2s;
}
.image-pane:hover .zoom-controls { opacity: 1; }
.zoom-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s;
  line-height: 1;
}
.zoom-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.zoom-label {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
  min-width: 34px;
  text-align: center;
}
.boxes-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.boxes-svg polygon { pointer-events: all; }

.box-poly {
  fill: rgba(232,168,64,0.08);
  stroke: var(--accent-dim);
  stroke-width: 1.5;
  cursor: pointer;
  transition: fill 0.15s, stroke 0.15s;
  vector-effect: non-scaling-stroke;
}
.box-poly.hovered {
  fill: rgba(232,168,64,0.22);
  stroke: var(--accent);
  stroke-width: 2;
}
.box-poly.active {
  fill: rgba(232,168,64,0.30);
  stroke: var(--accent);
  stroke-width: 2.5;
}
.box-poly.low-conf {
  stroke: var(--warning);
}
.box-poly.low-conf.hovered {
  fill: rgba(197,150,77,0.22);
  stroke: var(--warning);
}

.box-label {
  font-family: var(--font-mono);
  font-size: 28px;
  fill: var(--accent);
  paint-order: stroke;
  stroke: #0d0d0c;
  stroke-width: 8px;
  vector-effect: non-scaling-stroke;
}

/* ── Lines pane ─────────────────────────────────── */
.lines-pane {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: color-mix(in srgb, var(--bg-deep) 76%, transparent);
  padding: 6px;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
}
.result-body.split .lines-pane { background: var(--bg-deep); }

.text-lines {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.text-line {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  border: 1px solid transparent;
  animation: fade-stagger 0.3s ease both;
  position: relative;
}
.text-line:hover,
.text-line:focus-visible {
  background: var(--bg-elevated);
  border-color: var(--border-subtle);
  outline: none;
}
.text-line.hovered {
  background: rgba(232,168,64,0.07);
  border-color: rgba(232,168,64,0.2);
}
.text-line.active {
  background: rgba(232,168,64,0.12);
  border-color: rgba(232,168,64,0.35);
}
.text-line.low-conf {
  border-left: 2px solid var(--warning);
}

.line-num {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--text-muted);
  flex-shrink: 0;
  width: 22px;
  text-align: right;
}
.line-text {
  font-family: var(--font-ui);
  font-size: 0.88rem;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  word-break: break-all;
  line-height: 1.5;
}
.line-score {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  flex-shrink: 0;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--bg-surface);
}
.score-high { color: var(--success); }
.score-mid  { color: var(--warning); }
.score-low  { color: var(--error); }

.line-copy-hint {
  font-size: 0.65rem;
  color: var(--text-muted);
  opacity: 0;
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  transition: opacity 0.15s;
}
.text-line:hover .line-copy-hint { opacity: 1; }
.text-line:hover .line-score { opacity: 0; }

.lines-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-style: italic;
}

/* ── Highlight ──────────────────────────────────── */
:deep(.hl) {
  background: rgba(232,168,64,0.35);
  color: var(--text-primary);
  border-radius: 2px;
  padding: 0 1px;
}

/* ── Toast ──────────────────────────────────────── */
.toast {
  position: fixed;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  padding: 7px 18px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-active);
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  color: var(--text-primary);
  box-shadow: var(--shadow-md);
  z-index: 200;
  pointer-events: none;
  white-space: nowrap;
}
</style>
