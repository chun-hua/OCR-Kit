<template>
  <aside class="log-panel" :class="{ collapsed }">
    <!-- Header — button for keyboard accessibility -->
    <button
      type="button"
      class="log-header"
      :aria-expanded="!collapsed"
      aria-controls="log-body"
      @click="collapsed = !collapsed"
    >
      <div class="log-header-left">
        <div class="log-dot" :class="{ connected, pulse: connected && isStreaming }"></div>
        <span class="log-title">日志流</span>
        <span class="log-count" v-if="logs.length && collapsed">{{ logs.length }}</span>
      </div>
      <div class="log-header-right">
        <span class="log-status" v-if="connected && !collapsed">
          <span class="status-text">实时</span>
        </span>
        <button
          v-if="!collapsed"
          class="log-action"
          title="清空日志"
          @click.stop="clearLogs"
        >清空</button>
        <svg
          class="log-chevron"
          :class="{ flipped: !collapsed }"
          width="14" height="14" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round"
        >
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </div>
    </button>

    <!-- Body -->
    <Transition name="log-expand">
      <div v-if="!collapsed" class="log-body" id="log-body">
        <!-- Progress bar (visible when progress data exists) -->
        <div v-if="progressPct > 0" class="log-progress-section">
          <div class="log-progress-track">
            <div
              class="log-progress-fill"
              :style="{ width: progressPct + '%' }"
              :class="{ complete: progressPct >= 100 }"
            ></div>
            <div class="log-progress-glow" :style="{ left: progressPct + '%' }"></div>
          </div>
          <div class="log-progress-text">
            <span>{{ progressLabel }}</span>
            <span class="log-progress-pct">{{ progressPct.toFixed(0) }}%</span>
          </div>
        </div>

        <!-- Log entries -->
        <div class="log-entries" ref="entriesEl">
          <!-- Empty state -->
          <div v-if="logs.length === 0" class="log-empty">
            <div class="log-empty-icon">
              <span class="prompt-symbol">▸</span>
            </div>
            <p class="log-empty-text">等待任务开始...</p>
            <p class="log-empty-hint">上传文件后日志将在此显示</p>
          </div>

          <!-- Log lines -->
          <TransitionGroup name="log-entry" tag="div" class="log-lines">
            <div
              v-for="(log, i) in visibleLogs"
              :key="log.id"
              class="log-line"
              :class="'level-' + log.level"
            >
              <span class="log-prompt">{{ i === visibleLogs.length - 1 && isStreaming ? '▸' : '·' }}</span>
              <span class="log-time">{{ log.timestamp }}</span>
              <span class="log-stage" :class="'stage-' + log.stage">{{ log.stage_label }}</span>
              <span class="log-msg">{{ log.message }}</span>
              <!-- Detail popover for debug -->
              <span v-if="log.detail && log.level === 'debug'" class="log-detail-badge" :title="JSON.stringify(log.detail, null, 2)">ⓘ</span>
            </div>
          </TransitionGroup>
        </div>

        <!-- Footer: connection status -->
        <div class="log-footer">
          <template v-if="connectionStatus === 'connected'">
            <span class="log-footer-ok">● 已连接</span>
          </template>
          <template v-else-if="connectionStatus === 'reconnecting'">
            <span class="log-footer-warn">◉ 重连中...</span>
          </template>
          <template v-else-if="connectionStatus === 'closed'">
            <span class="log-footer-error">{{ connectError || '✕ 连接关闭' }}</span>
          </template>
          <template v-else>
            <span class="log-footer-wait">◎ 等待连接...</span>
          </template>
        </div>
      </div>
    </Transition>
  </aside>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { connectLogStream } from '../api/sse.js'

const props = defineProps({
  /** Whether the OCR task is currently running (controls streaming indicator) */
  isStreaming: { type: Boolean, default: false },
})

const emit = defineEmits(['log-event'])

// ── State ──
const collapsed = ref(false)
const connected = ref(false)
const connectError = ref('')
const logs = ref([])
const progressPct = ref(0)
const progressCurrent = ref(0)
const progressTotal = ref(0)
const entriesEl = ref(null)

let logIdCounter = 0
let sseConnection = null
let autoCollapseTimer = null

// ── Computed ──
const visibleLogs = computed(() => {
  // Show last 200 entries max for perf
  if (logs.value.length <= 200) return logs.value
  return logs.value.slice(-200)
})

const progressLabel = computed(() => {
  if (progressTotal.value > 0) {
    return `${progressCurrent.value} / ${progressTotal.value}`
  }
  return ''
})

// ── Methods ──
function addLog(event) {
  logIdCounter++
  logs.value.push({ ...event, id: logIdCounter })

  // Track progress
  if (event.progress_pct != null) {
    progressPct.value = event.progress_pct
  }
  if (event.progress_current != null) {
    progressCurrent.value = event.progress_current
  }
  if (event.progress_total != null) {
    progressTotal.value = event.progress_total
  }

  // If done or error, finish progress
  if (event.stage === 'done' || event.stage === 'error') {
    progressPct.value = event.stage === 'done' ? 100 : progressPct.value
  }

  // Emit for parent composable
  emit('log-event', event)

  // Auto-open panel when streaming starts
  if (collapsed.value && event.stage !== 'init') {
    collapsed.value = false
  }

  // Auto-collapse 5s after completion
  if (event.stage === 'done') {
    clearTimeout(autoCollapseTimer)
    autoCollapseTimer = setTimeout(() => {
      if (!props.isStreaming) collapsed.value = true
    }, 5000)
  }
}

function clearLogs() {
  logs.value = []
  progressPct.value = 0
  progressCurrent.value = 0
  progressTotal.value = 0
  logIdCounter = 0
}

// ── Auto-scroll ──
watch(
  () => logs.value.length,
  async () => {
    await nextTick()
    if (entriesEl.value) {
      entriesEl.value.scrollTop = entriesEl.value.scrollHeight
    }
  }
)

// ── SSE Connection ──
const connectionStatus = ref('waiting') // 'waiting' | 'connected' | 'reconnecting' | 'closed'

function startSSE() {
  sseConnection = connectLogStream({
    onEvent: addLog,
    onConnected: () => {
      connected.value = true
      connectionStatus.value = 'connected'
      connectError.value = ''
    },
    onReconnecting: () => {
      connected.value = false
      connectionStatus.value = 'reconnecting'
    },
    onDisconnected: () => {
      connected.value = false
      connectionStatus.value = 'closed'
    },
    onError: (err) => {
      connectError.value = err.message
      connected.value = false
      connectionStatus.value = 'closed'
    },
  })
}

function stopSSE() {
  if (sseConnection) {
    sseConnection.close()
    sseConnection = null
  }
  connected.value = false
}

// ── Lifecycle ──
onMounted(() => {
  startSSE()
})

onUnmounted(() => {
  stopSSE()
  clearTimeout(autoCollapseTimer)
})

// Expose for parent
defineExpose({ clearLogs })
</script>

<style scoped>
/* ═══════════════════════════════════════════════════
   LogPanel · Terminal/Cyberpunk Darkroom
   ═══════════════════════════════════════════════════ */

.log-panel {
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(180deg, var(--signal-glow), transparent 24%),
    color-mix(in srgb, var(--bg-surface) 90%, transparent);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.65;
  overflow: hidden;
  transition: width 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  width: 330px;
  min-width: 0;
  position: relative;
}

@media (max-width: 860px) {
  .log-panel {
    width: 100% !important;
    max-height: 220px;
    border-left: none;
    border-top: 1px solid var(--border-subtle);
  }
  .log-panel.collapsed {
    max-height: 36px;
  }
  .log-panel.collapsed .log-header {
    writing-mode: horizontal-tb;
    padding: 6px 14px;
    flex-direction: row;
    gap: 8px;
  }
  .log-panel.collapsed .log-header-left { flex-direction: row; }
}

/* Subtle scanline overlay */
.log-panel::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 10;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.03) 2px,
    rgba(0, 0, 0, 0.03) 4px
  );
}

.log-panel.collapsed {
  width: 44px;
}

/* ── Header ───────────────────────────────── */

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 11px;
  background: color-mix(in srgb, var(--bg-elevated) 68%, transparent);
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
  z-index: 11;
  position: relative;
  /* reset <button> */
  width: 100%;
  text-align: left;
  border-radius: 0;
  font-family: inherit;
  font-size: inherit;
  color: inherit;
}
.log-header:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.log-panel.collapsed .log-header {
  writing-mode: vertical-lr;
  padding: 12px 8px;
  gap: 8px;
  justify-content: flex-start;
}

.log-header-left {
  display: flex;
  align-items: center;
  gap: 7px;
}

.log-panel.collapsed .log-header-left {
  flex-direction: column;
  gap: 6px;
  align-items: center;
}

.log-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
  transition: background 0.3s, box-shadow 0.3s;
}
.log-dot.connected {
  background: var(--signal);
  box-shadow: 0 0 8px var(--signal);
}
.log-dot.pulse {
  animation: log-pulse 1.5s ease-in-out infinite;
}

.log-title {
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--text-primary);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.log-panel.collapsed .log-title {
  font-size: 0.68rem;
  letter-spacing: 0.1em;
}

.log-count {
  font-size: 0.68rem;
  background: var(--bg-elevated);
  color: var(--text-muted);
  padding: 1px 5px;
  border-radius: 8px;
}

.log-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-panel.collapsed .log-header-right {
  gap: 4px;
}

.log-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.68rem;
  color: var(--signal);
}
.status-text {
  animation: log-pulse 2s ease-in-out infinite;
}

.log-action {
  font-size: 0.68rem;
  color: var(--text-muted);
  padding: 2px 6px;
  border-radius: 3px;
  transition: all 0.2s;
}
.log-action:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.log-chevron {
  color: var(--text-muted);
  transition: transform 0.3s;
  flex-shrink: 0;
}
.log-chevron.flipped {
  transform: rotate(180deg);
}

/* ── Body ────────────────────────────────── */

.log-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

/* ── Progress ────────────────────────────── */

.log-progress-section {
  padding: 8px 12px 4px;
  flex-shrink: 0;
}
.log-progress-track {
  height: 3px;
  background: var(--bg-elevated);
  border-radius: 2px;
  position: relative;
  overflow: visible;
}
.log-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--signal-dim), var(--signal));
  border-radius: 2px;
  transition: width 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
}
.log-progress-fill.complete {
  background: var(--success);
  box-shadow: 0 0 8px rgba(91, 154, 107, 0.4);
}
.log-progress-glow {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--signal);
  box-shadow: 0 0 10px var(--signal), 0 0 20px var(--signal-glow);
  transition: left 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.log-progress-text {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 0.7rem;
  color: var(--text-muted);
}
.log-progress-pct {
  color: var(--signal);
  font-weight: 500;
}

/* ── Log Entries ─────────────────────────── */

.log-entries {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 6px 8px;
  scroll-behavior: smooth;
}

.log-entries::-webkit-scrollbar {
  width: 4px;
}
.log-entries::-webkit-scrollbar-track {
  background: transparent;
}
.log-entries::-webkit-scrollbar-thumb {
  background: rgba(96, 92, 82, 0.2);
  border-radius: 2px;
}

/* Empty state */
.log-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 120px;
  gap: 6px;
  opacity: 0.4;
}
.log-empty-icon {
  font-size: 1.2rem;
  color: var(--accent-dim);
  animation: log-pulse 2.5s ease-in-out infinite;
}
.log-empty-text {
  font-size: 0.7rem;
  color: var(--text-muted);
}
.log-empty-hint {
  font-size: 0.6rem;
  color: var(--text-muted);
  opacity: 0.6;
}

/* Individual log line */
.log-lines {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.log-line {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  padding: 2px 4px;
  border-radius: 3px;
  transition: background 0.2s;
  word-break: break-all;
}
.log-line:hover {
  background: rgba(255, 255, 255, 0.02);
}

.log-prompt {
  flex-shrink: 0;
  width: 10px;
  font-size: 0.6rem;
  color: var(--accent-dim);
  margin-top: 1px;
}
.log-line.level-error .log-prompt {
  color: var(--error);
}

.log-time {
  flex-shrink: 0;
  color: var(--text-muted);
  font-size: 0.68rem;
  opacity: 0.7;
  margin-top: 1px;
  min-width: 62px;
}

.log-stage {
  flex-shrink: 0;
  font-size: 0.64rem;
  padding: 0 5px;
  border-radius: 2px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  line-height: 1.6;
  margin-top: 1px;
  white-space: nowrap;
}

/* Stage colors */
.log-stage.stage-init         { background: rgba(155, 137, 119, 0.15); color: #b0a090; }
.log-stage.stage-preprocess   { background: rgba(100, 149, 237, 0.12); color: #7ea8e0; }
.log-stage.stage-detection    { background: rgba(232, 168, 64, 0.12);  color: #d4a040; }
.log-stage.stage-recognition  { background: rgba(91, 154, 107, 0.12);  color: #6dae7e; }
.log-stage.stage-postprocess  { background: rgba(150, 120, 180, 0.12); color: #b898d0; }
.log-stage.stage-progress     { background: rgba(130, 130, 130, 0.1);  color: #999; }
.log-stage.stage-done         { background: rgba(91, 154, 107, 0.15);  color: #7cc08a; }
.log-stage.stage-error        { background: rgba(194, 85, 77, 0.15);   color: #d47068; }

.log-msg {
  flex: 1;
  min-width: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}
.log-line.level-debug .log-msg  { opacity: 0.55; font-style: italic; }
.log-line.level-warn .log-msg   { color: var(--warning); }
.log-line.level-error .log-msg  { color: var(--error); font-weight: 500; }
.log-line.level-info .log-msg   { color: var(--text-secondary); }

.log-detail-badge {
  flex-shrink: 0;
  font-size: 0.68rem;
  color: var(--text-muted);
  cursor: help;
  opacity: 0.5;
  margin-top: 1px;
}
.log-detail-badge:hover {
  opacity: 1;
  color: var(--accent-dim);
}

/* ── Footer ──────────────────────────────── */

.log-footer {
  padding: 4px 10px;
  border-top: 1px solid var(--border-subtle);
  font-size: 0.7rem;
  color: var(--text-muted);
  flex-shrink: 0;
  background: color-mix(in srgb, var(--bg-elevated) 72%, transparent);
  letter-spacing: .03em;
}
.log-footer-ok   { color: var(--success); }
.log-footer-warn { color: var(--warning); }
.log-footer-error { color: var(--error); }
.log-footer-wait  { opacity: 0.4; }

/* ── Transitions ─────────────────────────── */

.log-expand-enter-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}
.log-expand-leave-active {
  transition: all 0.15s ease-in;
  overflow: hidden;
}
.log-expand-enter-from,
.log-expand-leave-to {
  opacity: 0;
  max-height: 0;
}

/* Log entry animations */
.log-entry-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.log-entry-leave-active {
  transition: all 0.15s ease-in;
}
.log-entry-enter-from {
  opacity: 0;
  transform: translateX(12px);
}
.log-entry-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}
.log-entry-move {
  transition: transform 0.25s ease;
}

/* ── Keyframes ───────────────────────────── */

@keyframes log-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}
</style>
