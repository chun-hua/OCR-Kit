<template>
  <div class="pdf-result">

    <!-- ── Header (always visible) ── -->
    <div class="result-header">
      <div class="header-left">
        <h2 class="result-title">
          识别结果
          <span class="page-info" v-if="!isStreaming || pagesTotal > 0">
            {{ currentPage }} / {{ effectiveTotal }} 页
          </span>
        </h2>
        <span v-if="isStreaming" class="streaming-badge">
          <span class="streaming-dot"></span>
          {{ pagesReceived }}/{{ pagesTotal || '?' }} 已完成
        </span>
      </div>
      <div class="result-actions">
        <button class="action-btn" @click="exportTxt" :disabled="isStreaming" title="导出所有页为 TXT">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出
        </button>
        <button class="action-btn" @click="copyCurrentPage" title="复制本页文本">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="9" y="9" width="13" height="13" rx="2"/>
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
          </svg>
          复制本页
        </button>
        <button class="action-btn" :class="{ success: copiedAll }"
          @click="copyAllPages" :disabled="isStreaming" title="复制全部页文本">
          <svg v-if="!copiedAll" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="9" y="9" width="13" height="13" rx="2"/>
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M20 6L9 17l-5-5"/>
          </svg>
          {{ copiedAll ? '已复制' : '复制全部' }}
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
        :placeholder="`搜索第 ${currentPage} 页文本…`"
        v-model="searchQuery"
      />
      <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
      <span v-if="searchQuery" class="search-count">
        {{ filteredLines.length }} / {{ currentLines }}
      </span>
      <label class="search-toggle" title="仅显示低置信度（＜80%）">
        <input type="checkbox" v-model="filterLowConf" />
        <span>低置信</span>
      </label>
    </div>

    <!-- ── Page navigation ── -->
    <div class="page-nav">
      <button class="nav-btn" :disabled="currentPage <= 1" @click="currentPage--">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M15 18l-6-6 6-6"/>
        </svg>
        上一页
      </button>

      <div class="page-jump">
        <span>第</span>
        <input
          type="number"
          class="page-input"
          :value="currentPage"
          @change="jumpTo($event)"
          :min="1"
          :max="effectiveTotal"
        />
        <span>页</span>
      </div>

      <button class="nav-btn" :disabled="currentPage >= effectiveTotal" @click="currentPage++">
        下一页
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M9 18l6-6-6-6"/>
        </svg>
      </button>
    </div>

    <!-- ── Page stats ── -->
    <div class="page-stats">
      <span>{{ currentLines }} 行文本</span>
      <span class="stat-sep">·</span>
      <span>页均置信度 <strong>{{ currentAvgScore }}%</strong></span>
      <template v-if="pageWidth">
        <span class="stat-sep">·</span>
        <span class="stat-dim">{{ pageWidth }}×{{ pageHeight }}</span>
      </template>
    </div>

    <!-- ── Split body ── -->
    <div class="result-body" :class="{ split: !!file }">

      <!-- Left: one rendered PDF page with OCR overlay -->
      <div v-if="file" class="pdf-pane" ref="pdfPaneRef">
        <div class="zoom-controls">
          <button class="zoom-btn" @click="zoomBy(-0.2)" title="缩小">−</button>
          <span class="zoom-label">{{ Math.round(zoom * 100) }}%</span>
          <button class="zoom-btn" @click="zoomBy(0.2)" title="放大">＋</button>
          <button class="zoom-btn" @click="resetZoom" title="适合窗口">↺</button>
          <button
            class="zoom-btn"
            :class="{ active: showOverlay }"
            @click="showOverlay = !showOverlay"
            title="显示或隐藏识别框"
          >▣</button>
        </div>

        <div class="pdf-page-stage">
          <div
            v-show="pdfReady"
            class="pdf-page-wrap"
            :style="{ width: `${renderWidth}px`, height: `${renderHeight}px` }"
          >
            <canvas ref="pdfCanvasRef" class="pdf-canvas"></canvas>
            <svg
              v-if="showOverlay && pageWidth && pageHeight"
              class="boxes-svg"
              :viewBox="`0 0 ${pageWidth} ${pageHeight}`"
              preserveAspectRatio="none"
              aria-label="当前页 OCR 识别区域"
            >
              <polygon
                v-for="(points, i) in boxPolygons"
                :key="i"
                v-show="points"
                :points="points"
                class="box-poly"
                :class="{
                  hovered: hoveredIdx === i,
                  active: activeIdx === i,
                  'low-conf': isLowConf(i),
                }"
                @mouseenter="setHover(i)"
                @mouseleave="setHover(-1)"
                @click.stop="selectLine(i)"
              />
            </svg>
          </div>
        </div>

        <div v-if="pdfLoading" class="pdf-pane-loading">
          <div class="loading-ring"></div>
          <span>正在加载第 {{ currentPage }} 页…</span>
        </div>
        <div v-else-if="pdfError" class="pdf-pane-error">
          {{ pdfError }}
        </div>
      </div>

      <!-- Right: text area -->
      <div class="text-pane">
        <!-- Page loading -->
        <div v-if="isStreaming && !currentPageReady" class="page-loading">
          <div class="loading-ring"></div>
          <span>正在识别第 {{ currentPage }} 页…</span>
        </div>

        <!-- Text lines -->
        <ul class="text-lines" v-else-if="filteredLines.length > 0" role="list">
          <li
            v-for="item in filteredLines"
            :key="item.origIdx"
            class="text-line"
            :class="{
              'newly-arrived': isStreaming && isNewPage,
              'low-conf': item.score < 0.8,
              hovered: hoveredIdx === item.origIdx,
              active: activeIdx === item.origIdx,
            }"
            :ref="el => { lineEls[item.origIdx] = el }"
            :style="{ animationDelay: `${item.origIdx * 0.03}s` }"
            tabindex="0"
            role="listitem"
            @mouseenter="setHover(item.origIdx)"
            @mouseleave="setHover(-1)"
            @click="selectLine(item.origIdx)"
            @keydown.enter.space.prevent="selectLine(item.origIdx)"
          >
            <span class="line-index">{{ item.origIdx + 1 }}</span>
            <span class="line-text" v-html="highlight(item.text)"></span>
            <span class="line-score" :class="scoreClass(item.score)">
              {{ (item.score * 100).toFixed(1) }}%
            </span>
          </li>
        </ul>

        <div v-else-if="currentLines === 0 && !isStreaming" class="result-empty">
          第 {{ currentPage }} 页未识别到文本
        </div>
        <div v-else-if="filteredLines.length === 0 && currentLines > 0" class="result-empty">
          无匹配结果
        </div>
      </div>
    </div>

    <!-- ── Toast ── -->
    <Transition name="fade">
      <div v-if="toast" class="toast" role="status" aria-live="polite">{{ toast }}</div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl

const props = defineProps({
  pages:         { type: Array,   default: () => [] },
  totalPages:    { type: Number,  default: 0 },
  isStreaming:   { type: Boolean, default: false },
  pagesReceived: { type: Number,  default: 0 },
  pagesTotal:    { type: Number,  default: 0 },
  file:          { type: File,    default: null },
})

const currentPage   = ref(1)
const toast         = ref('')
const copiedAll     = ref(false)
const isNewPage     = ref(false)
const searchQuery   = ref('')
const filterLowConf = ref(false)
const hoveredIdx    = ref(-1)
const activeIdx     = ref(-1)
const showOverlay   = ref(true)
const lineEls       = ref({})

// ── PDF.js page renderer ──────────────────────────
const pdfPaneRef    = ref(null)
const pdfCanvasRef  = ref(null)
const pdfReady      = ref(false)
const pdfLoading    = ref(false)
const pdfError      = ref('')
const renderWidth   = ref(0)
const renderHeight  = ref(0)
const zoom          = ref(1)

let pdfDocument = null
let pdfLoadingTask = null
let pdfRenderTask = null
let resizeObserver = null
let renderSequence = 0

async function loadPdf(file) {
  renderSequence++
  pdfReady.value = false
  pdfError.value = ''
  pdfLoading.value = !!file

  if (pdfRenderTask) {
    pdfRenderTask.cancel()
    pdfRenderTask = null
  }
  if (pdfLoadingTask) {
    await pdfLoadingTask.destroy().catch(() => {})
    pdfLoadingTask = null
  }
  if (pdfDocument) {
    await pdfDocument.destroy().catch(() => {})
    pdfDocument = null
  }
  if (!file) {
    pdfLoading.value = false
    return
  }

  try {
    const data = new Uint8Array(await file.arrayBuffer())
    pdfLoadingTask = pdfjsLib.getDocument({ data })
    pdfDocument = await pdfLoadingTask.promise
    currentPage.value = Math.min(currentPage.value, pdfDocument.numPages)
    await renderCurrentPage()
  } catch (error) {
    if (error?.name !== 'RenderingCancelledException') {
      pdfError.value = `PDF 页面加载失败：${error.message}`
    }
  } finally {
    pdfLoading.value = false
  }
}

async function renderCurrentPage() {
  if (!pdfDocument || !pdfCanvasRef.value || !pdfPaneRef.value) return

  const sequence = ++renderSequence
  pdfLoading.value = true
  pdfError.value = ''
  pdfReady.value = false

  if (pdfRenderTask) {
    pdfRenderTask.cancel()
    pdfRenderTask = null
  }

  try {
    const pageNumber = Math.min(currentPage.value, pdfDocument.numPages)
    const page = await pdfDocument.getPage(pageNumber)
    const baseViewport = page.getViewport({ scale: 1 })
    const paneRect = pdfPaneRef.value.getBoundingClientRect()
    const availableWidth = Math.max(paneRect.width - 28, 120)
    const availableHeight = Math.max(paneRect.height - 28, 120)
    const fitScale = Math.min(
      availableWidth / baseViewport.width,
      availableHeight / baseViewport.height,
    )
    const cssScale = Math.max(fitScale * zoom.value, 0.1)
    const cssViewport = page.getViewport({ scale: cssScale })
    const outputScale = Math.min(window.devicePixelRatio || 1, 2)
    const renderViewport = page.getViewport({ scale: cssScale * outputScale })
    const canvas = pdfCanvasRef.value
    const context = canvas.getContext('2d')

    canvas.width = Math.floor(renderViewport.width)
    canvas.height = Math.floor(renderViewport.height)
    canvas.style.width = `${cssViewport.width}px`
    canvas.style.height = `${cssViewport.height}px`
    renderWidth.value = cssViewport.width
    renderHeight.value = cssViewport.height

    pdfRenderTask = page.render({
      canvasContext: context,
      viewport: renderViewport,
    })
    await pdfRenderTask.promise
    if (sequence !== renderSequence) return
    pdfReady.value = true
  } catch (error) {
    if (error?.name !== 'RenderingCancelledException') {
      pdfError.value = `第 ${currentPage.value} 页渲染失败：${error.message}`
    }
  } finally {
    if (sequence === renderSequence) pdfLoading.value = false
  }
}

function zoomBy(delta) {
  zoom.value = Math.min(3, Math.max(0.5, zoom.value + delta))
}

function resetZoom() {
  zoom.value = 1
}

onMounted(() => {
  loadPdf(props.file)
  resizeObserver = new ResizeObserver(() => renderCurrentPage())
  if (pdfPaneRef.value) resizeObserver.observe(pdfPaneRef.value)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  pdfRenderTask?.cancel()
  pdfLoadingTask?.destroy()
  pdfDocument?.destroy()
})

watch(() => props.file, (file) => {
  currentPage.value = 1
  resetZoom()
  loadPdf(file)
})

// ── Page tracking ──────────────────────────────────
watch(currentPage, () => {
  isNewPage.value = props.isStreaming
  searchQuery.value = ''
  hoveredIdx.value = -1
  activeIdx.value = -1
  lineEls.value = {}
  renderCurrentPage()
  if (props.isStreaming) setTimeout(() => { isNewPage.value = false }, 600)
})

watch(zoom, () => renderCurrentPage())

watch(() => props.pagesReceived, (received) => {
  if (props.isStreaming && received > 0) currentPage.value = received
})

// ── Computed ──────────────────────────────────────
const effectiveTotal = computed(() =>
  props.pagesTotal || props.pages.length || props.totalPages || 0
)

const currentPageData = computed(() =>
  props.pages[currentPage.value - 1] ?? { texts: [], scores: [], width: 0, height: 0 }
)

const currentPageReady = computed(() => {
  const d = currentPageData.value
  return d && d.texts !== undefined
})

const currentLines = computed(() => currentPageData.value.texts?.length ?? 0)

const currentAvgScore = computed(() => {
  const scores = currentPageData.value.scores ?? []
  if (!scores.length) return '0.0'
  const avg = scores.reduce((a, s) => a + (s ?? 0), 0) / scores.length
  return (avg * 100).toFixed(1)
})

const pageWidth  = computed(() => currentPageData.value.width  ?? 0)
const pageHeight = computed(() => currentPageData.value.height ?? 0)

const allCurrentLines = computed(() => {
  const texts  = currentPageData.value.texts  ?? []
  const scores = currentPageData.value.scores ?? []
  const boxes  = currentPageData.value.boxes  ?? []
  return texts.map((text, i) => ({
    text,
    score: scores[i] ?? 0,
    box: boxes[i] ?? null,
    origIdx: i,
  }))
})

const filteredLines = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return allCurrentLines.value.filter(l => {
    if (filterLowConf.value && l.score >= 0.8) return false
    if (q && !l.text.toLowerCase().includes(q)) return false
    return true
  })
})

function parseBoxPolygon(box) {
  if (!box || !box.length) return null
  if (Array.isArray(box[0])) {
    return box.map(point => `${point[0]},${point[1]}`).join(' ')
  }
  if (box.length === 4) {
    const [x1, y1, x2, y2] = box
    return `${x1},${y1} ${x2},${y1} ${x2},${y2} ${x1},${y2}`
  }
  if (box.length === 8) {
    const points = []
    for (let i = 0; i < 8; i += 2) points.push(`${box[i]},${box[i + 1]}`)
    return points.join(' ')
  }
  return null
}

const boxPolygons = computed(() =>
  allCurrentLines.value.map(line => parseBoxPolygon(line.box))
)

function isLowConf(index) {
  return (allCurrentLines.value[index]?.score ?? 1) < 0.8
}

function setHover(index) {
  hoveredIdx.value = index
  if (index < 0) return
  nextTick(() => {
    lineEls.value[index]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

function selectLine(index) {
  activeIdx.value = activeIdx.value === index ? -1 : index
  copyLine(allCurrentLines.value[index]?.text ?? '')
}

// ── Helpers ───────────────────────────────────────
function scoreClass(score) {
  const s = score ?? 0
  if (s >= 0.95) return 'score-high'
  if (s >= 0.80) return 'score-mid'
  return 'score-low'
}

function jumpTo(e) {
  const v = parseInt(e.target.value, 10)
  if (v >= 1 && v <= effectiveTotal.value) currentPage.value = v
}

function highlight(text) {
  const q = searchQuery.value.trim()
  if (!q) return escHtml(text)
  return escHtml(text).replace(
    new RegExp(escRe(q), 'gi'),
    m => `<mark class="hl">${m}</mark>`
  )
}
function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}
function escRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 1800)
}

async function copyLine(text) {
  try {
    await navigator.clipboard.writeText(text)
    showToast('已复制到剪贴板')
  } catch { showToast('复制失败') }
}

async function copyCurrentPage() {
  const all = (currentPageData.value.texts ?? []).join('\n')
  try {
    await navigator.clipboard.writeText(all)
    showToast(`已复制第 ${currentPage.value} 页`)
  } catch { showToast('复制失败') }
}

async function copyAllPages() {
  const all = props.pages
    .filter(Boolean)
    .map(p => (p.texts ?? []).join('\n'))
    .join('\n\n')
  try {
    await navigator.clipboard.writeText(all)
    copiedAll.value = true
    setTimeout(() => { copiedAll.value = false }, 2000)
  } catch { showToast('复制失败') }
}

function exportTxt() {
  const text = props.pages
    .filter(Boolean)
    .map((p, i) => `=== 第 ${i + 1} 页 ===\n${(p.texts ?? []).join('\n')}`)
    .join('\n\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url
  a.download = 'ocr-result.txt'
  a.click()
  URL.revokeObjectURL(url)
  showToast('已下载 TXT')
}
</script>

<style scoped>
.pdf-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  overflow: hidden;
}

/* ── Split body ──────────────────────────────────── */
.result-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.result-body.split {
  flex-direction: row;
  gap: 10px;
  background: transparent;
}

/* ── PDF preview pane ────────────────────────────── */
.pdf-pane {
  flex: 0 0 52%;
  min-width: 0;
  overflow: hidden;
  background:
    linear-gradient(rgba(94,216,210,.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(94,216,210,.025) 1px, transparent 1px),
    var(--bg-surface);
  background-size: 24px 24px;
  position: relative;
  display: flex;
  align-items: stretch;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
}
.pdf-page-stage {
  width: 100%;
  height: 100%;
  overflow: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px;
}
.pdf-page-wrap {
  position: relative;
  flex: 0 0 auto;
  background: #fff;
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.28);
}
.pdf-canvas {
  display: block;
  width: 100%;
  height: 100%;
}
.boxes-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.boxes-svg polygon {
  pointer-events: all;
}
.box-poly {
  fill: rgba(232, 168, 64, 0.08);
  stroke: var(--accent-dim);
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
  cursor: pointer;
  transition: fill 0.15s, stroke 0.15s;
}
.box-poly.hovered {
  fill: rgba(232, 168, 64, 0.22);
  stroke: var(--accent);
  stroke-width: 2;
}
.box-poly.active {
  fill: rgba(232, 168, 64, 0.32);
  stroke: var(--accent);
  stroke-width: 2.5;
}
.box-poly.low-conf {
  stroke: var(--warning);
}
.zoom-controls {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px 4px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  box-shadow: var(--shadow-md);
  opacity: 0.68;
  transition: opacity 0.2s;
}
.pdf-pane:hover .zoom-controls {
  opacity: 1;
}
.zoom-btn {
  width: 25px;
  height: 25px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
}
.zoom-btn:hover,
.zoom-btn.active {
  color: var(--accent);
  background: var(--bg-hover);
}
.zoom-label {
  min-width: 38px;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
}
.pdf-pane-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  justify-content: center;
  background: var(--bg-surface);
  color: var(--text-muted);
  font-size: 0.78rem;
}
.pdf-pane-error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: var(--error);
  font-size: 0.82rem;
  text-align: center;
}

/* ── Text pane ───────────────────────────────────── */
.text-pane {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: color-mix(in srgb, var(--bg-deep) 76%, transparent);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 4px;
}

/* ── Header ───────────────────────────────────────── */
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
  padding: 0 2px 10px;
  border-bottom: 1px solid var(--border-subtle);
}
.header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.result-title {
  font-size: 1.28rem;
  font-weight: 600;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.page-info {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 400;
}
.streaming-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  color: var(--accent);
  padding: 2px 8px;
  background: rgba(232,168,64,0.08);
  border-radius: 10px;
  border: 1px solid rgba(232,168,64,0.2);
}
.streaming-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse-glow 1.5s ease-in-out infinite;
}

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
.action-btn:hover:not(:disabled) {
  color: var(--text-primary);
  border-color: var(--border-active);
  background: var(--bg-hover);
}
.action-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.action-btn.success  { color: var(--success); border-color: rgba(91,154,107,0.4); }

/* ── Search bar ───────────────────────────────────── */
.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
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

/* ── Page navigation ──────────────────────────────── */
.page-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 7px 10px;
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  flex-shrink: 0;
}
.nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 13px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: all 0.2s;
}
.nav-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
.nav-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.page-jump {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.85rem;
  color: var(--text-secondary);
}
.page-input {
  width: 48px;
  padding: 4px 6px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.85rem;
  text-align: center;
  transition: border-color 0.2s;
}
.page-input:focus { outline: none; border-color: var(--accent); }

/* ── Page stats ───────────────────────────────────── */
.page-stats {
  font-size: 0.78rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.page-stats strong { color: var(--text-secondary); font-weight: 500; }
.stat-sep { opacity: 0.4; }
.stat-dim { color: var(--text-muted); }

/* ── Page loading ─────────────────────────────────── */
.page-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: var(--text-muted);
  font-size: 0.85rem;
}
.loading-ring {
  width: 28px;
  height: 28px;
  border: 2px solid var(--border-subtle);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Text lines ───────────────────────────────────── */
.text-lines {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1;
  padding: 4px 4px 4px 0;
}
.text-line {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  animation: fade-stagger 0.3s ease both;
  border: 1px solid transparent;
  position: relative;
}
.text-line:hover,
.text-line:focus-visible {
  background: var(--bg-elevated);
  border-color: var(--border-subtle);
  outline: none;
}
.text-line.newly-arrived {
  border-color: rgba(232,168,64,0.25);
  background: rgba(232,168,64,0.04);
}
.text-line.hovered {
  background: rgba(232,168,64,0.08);
  border-color: rgba(232,168,64,0.24);
}
.text-line.active {
  background: rgba(232,168,64,0.14);
  border-color: rgba(232,168,64,0.42);
}
.text-line.low-conf {
  border-left: 2px solid var(--warning);
}

.line-index {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--text-muted);
  flex-shrink: 0;
  width: 22px;
  text-align: right;
}
.line-text {
  font-family: var(--font-ui);
  font-size: 0.9rem;
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
.score-low  { color: var(--error);   }

/* ── Search highlight ─────────────────────────────── */
:deep(.hl) {
  background: rgba(232,168,64,0.35);
  color: var(--text-primary);
  border-radius: 2px;
  padding: 0 1px;
}

/* ── Empty ────────────────────────────────────────── */
.result-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-style: italic;
}

/* ── Toast ────────────────────────────────────────── */
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

@keyframes spin { to { transform: rotate(360deg); } }
</style>
