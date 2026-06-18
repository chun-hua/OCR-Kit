<template>
  <header class="toolbar">
    <!-- Left: brand -->
    <div class="toolbar-brand">
      <span class="brand-mark" aria-hidden="true">
        <span></span><span></span><span></span><span></span>
      </span>
      <span class="brand-word"><span class="brand-pp">PP</span><span class="brand-dash">/</span><span class="brand-name">OCR</span></span>
      <span class="brand-sub">OPTICAL WORKSTATION</span>
    </div>

    <!-- Center: service status -->
    <div class="toolbar-status">
      <span class="status-prefix">SYSTEM</span>
      <div class="status-dot" :class="status" :title="label"></div>
      <span class="status-label">{{ label }}</span>
      <span v-if="info" class="status-info">{{ info.engine }} · {{ info.model }}</span>
    </div>

    <!-- Right: global actions -->
    <div class="toolbar-actions">
      <button
        class="tool-btn"
        :title="isDark ? '切换浅色主题' : '切换深色主题'"
        @click="toggleTheme"
      >
        <!-- sun icon -->
        <svg v-if="isDark" width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
        <!-- moon icon -->
        <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
        </svg>
      </button>
      <span class="version-tag">V6 / ONNX</span>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  status: { type: String, default: 'checking' },
  info:   { type: Object, default: null },
})

const label = computed(() => {
  switch (props.status) {
    case 'ok':       return '服务就绪'
    case 'error':    return '服务离线'
    case 'checking': return '检查中…'
    default:         return '未知'
  }
})

// ── Theme toggle ──────────────────────────────────
const isDark = ref(true)

function applyTheme(dark) {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  isDark.value = dark
  localStorage.setItem('ppocr-theme', dark ? 'dark' : 'light')
}

function toggleTheme() {
  applyTheme(!isDark.value)
}

onMounted(() => {
  const saved = localStorage.getItem('ppocr-theme')
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  applyTheme(saved ? saved === 'dark' : prefersDark)
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 14px 0 18px;
  height: 54px;
  background: color-mix(in srgb, var(--bg-surface) 88%, transparent);
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
  user-select: none;
  backdrop-filter: blur(18px);
  position: relative;
  z-index: 20;
}
.toolbar::after {
  content: '';
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: -1px;
  height: 1px;
  background: linear-gradient(90deg, var(--signal), transparent 26%, transparent 74%, var(--accent));
  opacity: .45;
}

/* ── Brand ──────────────────────────────────────── */
.toolbar-brand {
  display: flex;
  align-items: baseline;
  gap: 9px;
  font-family: var(--font-mono);
  font-size: 0.88rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  flex-shrink: 0;
}
.brand-mark {
  width: 25px;
  height: 25px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px;
  padding: 5px;
  border: 1px solid color-mix(in srgb, var(--signal) 42%, transparent);
  border-radius: 7px;
  background: var(--signal-glow);
  box-shadow: inset 0 0 12px var(--signal-glow);
}
.brand-mark span {
  border: 1px solid var(--signal);
  opacity: .8;
}
.brand-word { display: flex; gap: 2px; }
.brand-pp   { color: var(--accent); }
.brand-dash { color: var(--text-muted); font-weight: 400; }
.brand-name { color: var(--text-primary); }
.brand-sub  {
  font-family: var(--font-mono);
  font-size: 0.56rem;
  color: var(--text-muted);
  margin-left: 1px;
  font-weight: 400;
  letter-spacing: .14em;
}

/* ── Center status ──────────────────────────────── */
.toolbar-status {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 0.7rem;
  color: var(--text-muted);
  padding: 5px 10px;
  border: 1px solid var(--border-subtle);
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-elevated) 72%, transparent);
}
.status-prefix {
  font-family: var(--font-mono);
  font-size: .56rem;
  letter-spacing: .12em;
  color: var(--text-muted);
  padding-right: 3px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: background 0.4s;
  flex-shrink: 0;
}
.status-dot.ok      { background: var(--signal); box-shadow: 0 0 9px var(--signal); }
.status-dot.error   { background: var(--error);   box-shadow: 0 0 6px rgba(194,85,77,0.4); }
.status-dot.checking { background: var(--accent); animation: pulse-glow 1.5s infinite; }
.status-label { font-weight: 500; color: var(--text-secondary); }
.status-info  { opacity: 0.55; }

/* ── Right actions ──────────────────────────────── */
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.version-tag {
  height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 9px;
  border-left: 1px solid var(--border-subtle);
  font-family: var(--font-mono);
  font-size: .58rem;
  letter-spacing: .08em;
  color: var(--text-muted);
}
.tool-btn {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.tool-btn:hover {
  color: var(--text-primary);
  background: var(--bg-elevated);
  border-color: var(--border-subtle);
}

@media (max-width: 680px) {
  .brand-sub, .status-info, .status-prefix, .version-tag { display: none; }
  .toolbar { height: 48px; }
}
</style>
