<template>
  <section v-if="entries.length" class="history-panel">
    <div class="history-header">
      <span class="history-title">历史记录</span>
      <span class="history-count">{{ entries.length }}</span>
      <button class="history-clear" @click="confirmClear" title="清空历史">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6l-1 14H6L5 6"/>
          <path d="M10 11v6M14 11v6"/>
          <path d="M9 6V4h6v2"/>
        </svg>
      </button>
    </div>

    <ul class="history-list" role="list">
      <li
        v-for="entry in entries"
        :key="entry.id"
        class="history-item"
        :class="{ active: activeId === entry.id }"
        role="listitem"
        tabindex="0"
        :aria-label="`恢复 ${entry.fileName}`"
        @click="restore(entry)"
        @keydown.enter.space.prevent="restore(entry)"
      >
        <div class="item-icon" aria-hidden="true">
          <!-- PDF icon -->
          <svg v-if="entry.fileType === 'pdf'" width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <text x="12" y="18" text-anchor="middle" font-size="5" font-weight="700"
              fill="currentColor" stroke="none" font-family="monospace">PDF</text>
          </svg>
          <!-- Image icon -->
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
        </div>

        <div class="item-body">
          <span class="item-name" :title="entry.fileName">{{ entry.fileName }}</span>
          <span class="item-meta">
            <span>{{ entry.summary.pages > 1 ? entry.summary.pages + ' 页 · ' : '' }}{{ entry.summary.lines }} 行</span>
            <span class="meta-sep">·</span>
            <span :class="scoreClass(entry.summary.avgScore)">{{ entry.summary.avgScore }}%</span>
            <span class="meta-sep">·</span>
            <span class="item-date">{{ relDate(entry.date) }}</span>
          </span>
        </div>

        <button
          class="item-del"
          :title="`删除 ${entry.fileName}`"
          @click.stop="remove(entry.id)"
          aria-label="删除此记录"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  entries:  { type: Array,  default: () => [] },
  activeId: { type: Number, default: null },
})

const emit = defineEmits(['restore', 'remove', 'clear'])

function restore(entry) { emit('restore', entry) }
function remove(id)     { emit('remove', id) }

function confirmClear() {
  if (confirm('确定清空所有历史记录？')) emit('clear')
}

function relDate(iso) {
  const d    = new Date(iso)
  const now  = new Date()
  const diff = now - d
  const mins = Math.floor(diff / 60_000)
  if (mins < 1)  return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs  < 24) return `${hrs} 小时前`
  const days = Math.floor(hrs / 24)
  if (days < 7)  return `${days} 天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function scoreClass(avg) {
  const n = parseFloat(avg)
  if (n >= 95) return 'sc-high'
  if (n >= 80) return 'sc-mid'
  return 'sc-low'
}
</script>

<style scoped>
.history-panel {
  margin-top: 20px;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 12px 10px 10px;
  background: color-mix(in srgb, var(--bg-elevated) 48%, transparent);
}

/* ── Header ───────────────────────────────────────── */
.history-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.history-title {
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  flex: 1;
}
.history-count {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
  background: var(--bg-elevated);
  padding: 1px 5px;
  border-radius: 8px;
}
.history-clear {
  color: var(--text-muted);
  padding: 3px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.5;
}
.history-clear:hover { opacity: 1; color: var(--error); }

/* ── List ─────────────────────────────────────────── */
.history-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 320px;
  overflow-y: auto;
  padding-right: 2px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 8px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
  position: relative;
}
.history-item:hover,
.history-item:focus-visible {
  background: var(--bg-elevated);
  border-color: var(--border-subtle);
  outline: none;
}
.history-item.active {
  background: linear-gradient(90deg, var(--accent-glow), transparent);
  border-color: color-mix(in srgb, var(--accent) 34%, transparent);
  box-shadow: inset 2px 0 var(--accent);
}

/* ── Icon ─────────────────────────────────────────── */
.item-icon {
  flex-shrink: 0;
  color: var(--signal);
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  background: var(--signal-glow);
}

/* ── Body ─────────────────────────────────────────── */
.item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.item-name {
  font-size: 0.8rem;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.68rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}
.meta-sep { opacity: 0.4; }
.item-date { opacity: 0.7; }

.sc-high { color: var(--success); }
.sc-mid  { color: var(--warning); }
.sc-low  { color: var(--error);   }

/* ── Delete btn ───────────────────────────────────── */
.item-del {
  flex-shrink: 0;
  opacity: 0;
  color: var(--text-muted);
  padding: 3px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s;
}
.history-item:hover .item-del { opacity: 0.5; }
.item-del:hover { opacity: 1 !important; color: var(--error); background: rgba(194,85,77,0.12); }
</style>
