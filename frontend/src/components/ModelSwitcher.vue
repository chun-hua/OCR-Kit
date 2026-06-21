<template>
  <section class="model-switcher" aria-labelledby="model-switcher-title">
    <div class="model-heading">
      <div>
        <span class="model-kicker">INFERENCE PROFILE</span>
        <h2 id="model-switcher-title">识别模型</h2>
      </div>
      <span class="model-state" :class="{ active: loadedId }">
        <span></span>
        {{ switching ? '加载中' : loadedId ? `${loadedId} 已就绪` : '按需加载' }}
      </span>
    </div>

    <div class="model-grid" role="radiogroup" aria-label="PP-OCRv6 模型精度">
      <button
        v-for="model in models"
        :key="model.id"
        type="button"
        class="model-option"
        :class="{
          selected: selectedId === model.id,
          loaded: loadedId === model.id,
        }"
        :disabled="disabled || switching"
        role="radio"
        :aria-checked="selectedId === model.id"
        @click="$emit('select', model.id)"
      >
        <span class="option-topline">
          <span class="option-tier">{{ model.tier }}</span>
          <span v-if="model.id === 'small'" class="recommended">推荐</span>
          <span v-if="loadedId === model.id" class="loaded-mark">READY</span>
        </span>
        <strong>{{ model.name }}</strong>
        <span class="option-metrics">
          {{ model.model_size_mb }} MB · REC {{ model.accuracy.recognition }}
        </span>
      </button>
    </div>

    <p class="model-note">
      {{ activeModel?.description || '选择模型档位；首次切换会自动下载模型文件。' }}
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  models: { type: Array, default: () => [] },
  selectedId: { type: String, default: 'tiny' },
  loadedId: { type: String, default: null },
  switching: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

defineEmits(['select'])

const activeModel = computed(() =>
  props.models.find((model) => model.id === props.selectedId)
)
</script>

<style scoped>
.model-switcher {
  margin-bottom: 14px;
  padding: 13px;
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  background:
    linear-gradient(135deg, var(--signal-glow), transparent 48%),
    color-mix(in srgb, var(--bg-elevated) 62%, transparent);
}
.model-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.model-kicker {
  display: block;
  margin-bottom: 2px;
  font-family: var(--font-mono);
  font-size: .52rem;
  letter-spacing: .14em;
  color: var(--signal);
}
.model-heading h2 {
  font-family: var(--font-ui);
  font-size: .82rem;
  font-weight: 600;
}
.model-state {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: .54rem;
  color: var(--text-muted);
  text-transform: uppercase;
}
.model-state span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-muted);
}
.model-state.active span {
  background: var(--signal);
  box-shadow: 0 0 7px var(--signal);
}
.model-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.model-option {
  min-width: 0;
  padding: 9px 8px 8px;
  text-align: left;
  border: 1px solid var(--border-subtle);
  border-radius: 9px;
  background: color-mix(in srgb, var(--bg-surface) 76%, transparent);
  transition: border-color .2s, background .2s, transform .2s, box-shadow .2s;
}
.model-option:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: var(--border-active);
  background: var(--bg-elevated);
}
.model-option.selected {
  border-color: color-mix(in srgb, var(--accent) 72%, transparent);
  background: var(--accent-glow);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 14%, transparent);
}
.model-option.loaded {
  box-shadow: inset 0 -2px 0 var(--signal);
}
.model-option:disabled {
  cursor: wait;
  opacity: .66;
}
.option-topline {
  min-height: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 3px;
}
.option-tier {
  font-family: var(--font-mono);
  font-size: .51rem;
  letter-spacing: .08em;
  color: var(--text-muted);
  text-transform: uppercase;
}
.recommended,
.loaded-mark {
  margin-left: auto;
  padding: 1px 4px;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: .44rem;
  letter-spacing: .05em;
}
.recommended {
  color: var(--accent);
  background: var(--accent-glow);
}
.loaded-mark {
  color: var(--signal);
  background: var(--signal-glow);
}
.model-option strong {
  display: block;
  font-size: .78rem;
  font-weight: 600;
  color: var(--text-primary);
}
.option-metrics {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: .48rem;
  color: var(--text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-note {
  min-height: 2.8em;
  margin-top: 8px;
  font-size: .68rem;
  line-height: 1.4;
  color: var(--text-muted);
}
</style>
