<template>
  <div class="app">
    <!-- Toolbar -->
    <StatusBar :status="healthStatus" :info="healthInfo" @settings="settingsOpen = true" />
    <SettingsDialog :open="settingsOpen" @close="settingsOpen = false" />

    <!-- Main layout -->
    <main class="main-layout">
      <!-- Left: Upload + History panel -->
      <section class="panel panel-left">
        <div class="workspace-intro">
          <span class="workspace-kicker">OPTICAL INPUT / 01</span>
          <h1>文档识别工作台</h1>
          <p class="app-desc">导入图像或 PDF，执行高精度版面识别与文字提取。</p>
        </div>

        <ModelSwitcher
          :models="models.profiles.value"
          :selected-id="models.selectedId.value"
          :loaded-id="models.loadedId.value"
          :switching="models.switching.value"
          :disabled="ocr.loading.value"
          @select="onSelectModel"
        />

        <FileUpload
          :file="ocr.file.value"
          :preview-url="ocr.previewUrl.value"
          :file-name="ocr.fileName.value"
          :file-size="ocr.fileSize.value"
          :loading="ocr.loading.value"
          :dpi="ocr.dpi.value"
          :max-pages="ocr.maxPages.value"
          @update:file="(f, url) => ocr.setFile(f, url)"
          @clear="onClear"
          @run="ocr.run()"
          @update:dpi="ocr.dpi.value = $event"
          @update:max-pages="ocr.maxPages.value = $event"
        />

        <!-- Error display -->
        <Transition name="slide-up">
          <div v-if="ocr.error.value || models.error.value" class="error-banner" role="alert" aria-live="assertive">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="2" stroke-linecap="round">
              <circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/>
            </svg>
            <span>{{ ocr.error.value || models.error.value }}</span>
          </div>
        </Transition>

        <!-- History panel (fills blank space) -->
        <HistoryPanel
          :entries="history.entries.value"
          :active-id="activeHistoryId"
          @restore="onRestoreHistory"
          @remove="history.remove"
          @clear="history.clear"
        />
      </section>

      <!-- Center: Result panel -->
      <section class="panel panel-center">
        <div class="panel-coordinate" aria-hidden="true">
          <span>VIEWPORT / OCR</span>
          <span>X 052 · Y 018</span>
        </div>
        <!-- Loading skeleton (images only — PDFs show progressive result) -->
        <div v-if="ocr.loading.value && ocr.mode.value !== 'pdf'" class="loading-state">
          <div class="loading-animation">
            <div class="loading-ring"></div>
            <span class="loading-label">检测与识别中…</span>
          </div>
          <div class="skeleton-lines">
            <div class="skeleton-line" v-for="i in 6" :key="i"
              :style="{ width: `${55 + (i * 7) % 40}%`, animationDelay: `${i * 0.12}s` }">
            </div>
          </div>
        </div>

        <!-- PDF progressive loading -->
        <PdfResult
          v-else-if="ocr.result.value && ocr.mode.value === 'pdf'"
          :pages="ocr.result.value.pages"
          :total-pages="ocr.result.value.total_pages"
          :is-streaming="ocr.isStreaming.value"
          :pages-received="ocr.progressivePagesReceived.value"
          :pages-total="ocr.progressivePagesTotal.value"
          :file="ocr.file.value"
        />

        <!-- Image result with overlay -->
        <OverlayResult
          v-else-if="ocr.result.value && ocr.mode.value !== 'pdf'"
          :pages="ocr.result.value.pages"
          :preview-url="ocr.previewUrl.value"
        />

        <!-- History result (restored, no live file) -->
        <OverlayResult
          v-else-if="historyResult && historyMode === 'image'"
          :pages="historyResult.pages"
          :preview-url="null"
        />
        <PdfResult
          v-else-if="historyResult && historyMode === 'pdf'"
          :pages="historyResult.pages"
          :total-pages="historyResult.total_pages"
          :is-streaming="false"
          :file="null"
        />

        <!-- Empty state -->
        <div v-else class="empty-state">
          <div class="empty-icon">
            <svg width="56" height="56" viewBox="0 0 56 56" fill="none">
              <rect x="6" y="10" width="44" height="36" rx="3" stroke="currentColor" stroke-width="1.5" opacity="0.25"/>
              <path d="M6 18h44" stroke="currentColor" stroke-width="1.5" opacity="0.15"/>
              <path d="M20 34l6-5 6 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.3"/>
              <circle cx="20" cy="28" r="2" fill="currentColor" opacity="0.3"/>
              <rect x="16" y="36" width="24" height="2" rx="1" fill="currentColor" opacity="0.1"/>
              <rect x="16" y="40" width="18" height="2" rx="1" fill="currentColor" opacity="0.08"/>
            </svg>
          </div>
          <p class="empty-title">等待文件</p>
          <p class="empty-hint">上传图片或 PDF 以开始文字识别</p>
        </div>
      </section>

      <!-- Right: Log panel -->
      <LogPanel :is-streaming="ocr.isStreaming.value" ref="logPanelRef" />
    </main>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import StatusBar    from './components/StatusBar.vue'
import FileUpload   from './components/FileUpload.vue'
import OverlayResult from './components/OverlayResult.vue'
import PdfResult    from './components/PdfResult.vue'
import LogPanel     from './components/LogPanel.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import ModelSwitcher from './components/ModelSwitcher.vue'
import SettingsDialog from './components/SettingsDialog.vue'
import { useOcr, useHealth, useModelProfiles } from './composables/useOcr.js'
import { useHistory }        from './composables/useHistory.js'

const models = useModelProfiles()
const ocr = useOcr(models.selectedId, models.loadedId)
const { status: healthStatus, info: healthInfo, check: checkHealth } = useHealth()
const history = useHistory()
const logPanelRef = ref(null)
const settingsOpen = ref(false)

// ── History state ──────────────────────────────────
const activeHistoryId = ref(null)
const historyResult   = ref(null)
const historyMode     = ref('image')

// Save to history when OCR finishes successfully
watch(
  () => ocr.result.value,
  (result) => {
    if (!result || ocr.isStreaming.value) return
    if (result.status === 'success' || (result.pages?.filter(Boolean).length > 0)) {
      history.save({
        fileName: ocr.fileName.value,
        fileSize: ocr.fileSize.value,
        fileType: ocr.mode.value,
        result,
      })
      activeHistoryId.value = null  // clear history highlight when new result is live
      historyResult.value   = null
    }
  }
)

function onRestoreHistory(entry) {
  // Clear any live OCR result and show the history result
  ocr.clear()
  historyResult.value   = history.toResult(entry)
  historyMode.value     = entry.fileType
  activeHistoryId.value = entry.id
}

function onClear() {
  ocr.clear()
  historyResult.value   = null
  activeHistoryId.value = null
}

async function onSelectModel(modelId) {
  try {
    await models.select(modelId)
    await checkHealth()
  } catch {
    // Model switch errors are rendered in the shared error banner.
  }
}

onMounted(() => {
  models.load()
  checkHealth()
  setInterval(checkHealth, 60_000)
})
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  isolation: isolate;
}

/* ── Main layout ──────────────────────────────── */
.main-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 350px minmax(460px, 1fr) auto;
  gap: 10px;
  padding: 10px;
  background: transparent;
  overflow: hidden;
  animation: workstation-in .55s cubic-bezier(.16,1,.3,1) both;
}
@media (max-width: 1100px) {
  .main-layout { grid-template-columns: 300px 1fr auto; }
}
@media (max-width: 860px) {
  .main-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
  }
}

.panel {
  background: color-mix(in srgb, var(--bg-surface) 88%, transparent);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(18px);
  overflow-y: auto;
  padding: 22px;
}
.panel-center {
  background:
    linear-gradient(rgba(94,216,210,.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(94,216,210,.025) 1px, transparent 1px),
    radial-gradient(ellipse at 70% 20%, var(--signal-glow) 0%, transparent 45%),
    color-mix(in srgb, var(--bg-surface) 86%, transparent);
  background-size: 28px 28px, 28px 28px, auto, auto;
  overflow: hidden;
  position: relative;
  padding-top: 34px;
}

/* ── Left panel ───────────────────────────────── */
.workspace-intro {
  padding: 2px 2px 20px;
}
.workspace-kicker,
.panel-coordinate {
  font-family: var(--font-mono);
  font-size: .62rem;
  letter-spacing: .14em;
  color: var(--signal);
}
.workspace-intro h1 {
  margin-top: 8px;
  font-size: 1.55rem;
  line-height: 1.25;
  letter-spacing: -.035em;
}
.app-desc {
  max-width: 290px;
  margin-top: 8px;
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.75;
}
.panel-coordinate {
  position: absolute;
  top: 11px;
  left: 20px;
  right: 20px;
  display: flex;
  justify-content: space-between;
  color: var(--text-muted);
  opacity: .58;
  pointer-events: none;
}

/* ── Error banner ─────────────────────────────── */
.error-banner {
  margin-top: 12px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(194,85,77,0.08);
  border: 1px solid rgba(194,85,77,0.25);
  border-radius: var(--radius-md);
  color: var(--error);
  font-size: 0.82rem;
  line-height: 1.5;
}
.error-banner svg { flex-shrink: 0; margin-top: 1px; }

/* ── Loading state ────────────────────────────── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 32px;
}
.loading-animation {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.loading-ring {
  width: 48px;
  height: 48px;
  border: 2px solid var(--border-subtle);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-label {
  font-family: var(--font-display);
  font-size: 0.9rem;
  color: var(--text-secondary);
}
.skeleton-lines {
  width: 260px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.skeleton-line {
  height: 13px;
  background: linear-gradient(
    90deg,
    var(--bg-surface) 0%,
    var(--bg-elevated) 40%,
    var(--bg-surface) 80%
  );
  background-size: 200% 100%;
  animation: shimmer 1.8s ease-in-out infinite;
  border-radius: 3px;
}

/* ── Empty state ──────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  position: relative;
}
.empty-state::before {
  content: '';
  width: 220px;
  height: 220px;
  position: absolute;
  border: 1px solid var(--border-subtle);
  border-radius: 50%;
  box-shadow:
    0 0 0 28px rgba(94,216,210,.018),
    0 0 0 56px rgba(94,216,210,.012);
  animation: signal-breathe 4s ease-in-out infinite;
}
.empty-icon {
  color: var(--signal);
  z-index: 1;
  filter: drop-shadow(0 0 18px var(--signal-glow));
}
.empty-title {
  font-family: var(--font-display);
  font-size: 1.1rem;
  color: var(--text-primary);
  z-index: 1;
}
.empty-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  z-index: 1;
}

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 1100px) {
  .main-layout { grid-template-columns: 310px minmax(420px, 1fr) auto; }
}

@media (max-width: 860px) {
  .main-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(520px, 1fr) auto;
    overflow-y: auto;
  }
  .panel { border-radius: 14px; }
}
</style>
