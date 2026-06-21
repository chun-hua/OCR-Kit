<template>
  <Teleport to="body">
    <div v-if="open" class="settings-backdrop" @click.self="$emit('close')">
      <section class="settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <header>
          <div>
            <span class="kicker">SYSTEM CONFIGURATION</span>
            <h2 id="settings-title">运行与存储设置</h2>
          </div>
          <button class="close-btn" type="button" aria-label="关闭" @click="$emit('close')">×</button>
        </header>

        <div v-if="loading" class="settings-loading">正在读取系统配置…</div>
        <form v-else-if="form" @submit.prevent="save">
          <div class="hardware-card">
            <div>
              <span>CPU</span>
              <strong>{{ hardware.processor || '未识别处理器' }}</strong>
              <small>{{ hardware.logical_cpus }} 个逻辑处理器</small>
            </div>
            <div>
              <span>内存</span>
              <strong>{{ hardware.memory_gb ? `${hardware.memory_gb} GB` : '未知' }}</strong>
              <small>{{ hardware.gpus?.join(' / ') || '未检测到独立显卡' }}</small>
            </div>
          </div>

          <p class="recommendation">
            系统建议：<strong>{{ profileLabel(hardware.recommended_profile) }}</strong>
            <span>{{ hardware.recommendation_reason }}</span>
          </p>

          <fieldset>
            <legend>性能档位</legend>
            <label
              v-for="profile in profiles"
              :key="profile.id"
              class="profile-option"
              :class="{ selected: form.performance_profile === profile.id, disabled: profile.id === 'cuda' && !hardware.cuda_available }"
            >
              <input
                v-model="form.performance_profile"
                type="radio"
                name="performance-profile"
                :value="profile.id"
                :disabled="profile.id === 'cuda' && !hardware.cuda_available"
                @change="applyProfile(profile)"
              />
              <span>
                <strong>
                  {{ profile.label }}
                  <em v-if="hardware.recommended_profile === profile.id">推荐</em>
                </strong>
                <small>{{ profile.description }}</small>
              </span>
            </label>
          </fieldset>

          <div class="path-grid">
            <label>
              <span>模型存放目录</span>
              <input v-model.trim="form.model_dir" required />
              <small>模型下载、转换缓存和推理缓存均存放在这里。</small>
            </label>
            <label>
              <span>项目数据目录</span>
              <input v-model.trim="form.project_dir" required />
              <small>用于日志、导出结果和后续项目文件；升级程序不会覆盖。</small>
            </label>
          </div>

          <div class="tuning-grid">
            <label>
              <span>默认模型</span>
              <select v-model="form.default_model">
                <option value="tiny">Tiny（低占用）</option>
                <option value="small">Small（均衡）</option>
                <option value="medium">Medium（高精度）</option>
              </select>
            </label>
            <label>
              <span>CPU 线程数</span>
              <input v-model.number="form.cpu_threads" type="number" min="1" max="64" />
            </label>
            <label>
              <span>推理设备</span>
              <select v-model="form.device">
                <option value="cpu">CPU</option>
                <option value="gpu" :disabled="!hardware.cuda_available">NVIDIA CUDA GPU</option>
              </select>
            </label>
          </div>

          <p v-if="!hardware.cuda_available && hardware.gpus?.length" class="gpu-note">
            已检测到显卡，但当前程序未加载 CUDAExecutionProvider，因此不会错误地启用 GPU。
            如需 GPU 加速，请安装 CUDA 版发行包并使用兼容驱动。
          </p>
          <p v-if="message" class="save-message">{{ message }}</p>
          <p v-if="error" class="settings-error">{{ error }}</p>

          <footer>
            <button type="button" class="secondary" @click="$emit('close')">取消</button>
            <button type="submit" class="primary" :disabled="saving">
              {{ saving ? '保存中…' : '保存设置' }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getSettings, updateSettings } from '../api/ocr.js'

const props = defineProps({ open: { type: Boolean, default: false } })
defineEmits(['close'])

const loading = ref(false)
const saving = ref(false)
const form = ref(null)
const hardware = ref({})
const profiles = ref([])
const error = ref('')
const message = ref('')

watch(() => props.open, (value) => {
  if (value) load()
})

async function load() {
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    const data = await getSettings()
    hardware.value = data.hardware || {}
    profiles.value = data.settings?.profiles || []
    form.value = {
      model_dir: data.settings.model_dir,
      project_dir: data.settings.project_dir,
      performance_profile: data.settings.performance_profile,
      device: data.settings.device,
      cpu_threads: data.settings.cpu_threads,
      ocr_workers: data.settings.ocr_workers,
      default_model: data.settings.default_model,
      open_browser: data.settings.open_browser,
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function profileLabel(id) {
  return profiles.value.find((item) => item.id === id)?.label || id || '均衡模式'
}

function applyProfile(profile) {
  form.value.device = profile.device
  form.value.cpu_threads = profile.cpu_threads
  form.value.ocr_workers = profile.ocr_workers
  form.value.default_model = profile.model
}

async function save() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await updateSettings(form.value)
    message.value = result.restart_required
      ? '设置已保存。关闭并重新启动 OCR-Kit 后生效。'
      : '设置已保存。'
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.settings-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(5, 9, 14, .72);
  backdrop-filter: blur(10px);
}
.settings-dialog {
  width: min(760px, 100%);
  max-height: min(860px, calc(100vh - 48px));
  overflow: auto;
  padding: 24px;
  border: 1px solid var(--border-active);
  border-radius: 18px;
  background: var(--bg-surface);
  box-shadow: 0 24px 90px rgba(0, 0, 0, .45);
}
header, footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
header { margin-bottom: 20px; }
header h2 { margin-top: 4px; font-size: 1.25rem; }
.kicker { font: .58rem var(--font-mono); letter-spacing: .14em; color: var(--signal); }
.close-btn { width: 32px; height: 32px; font-size: 1.5rem; color: var(--text-muted); }
.settings-loading { padding: 48px; text-align: center; color: var(--text-muted); }
.hardware-card, .tuning-grid, .path-grid { display: grid; gap: 10px; }
.hardware-card { grid-template-columns: 1fr 1fr; margin-bottom: 12px; }
.hardware-card > div {
  display: grid; gap: 3px; padding: 12px;
  border: 1px solid var(--border-subtle); border-radius: 10px; background: var(--bg-elevated);
}
.hardware-card span, label > span { font-size: .72rem; color: var(--text-muted); }
.hardware-card strong { font-size: .8rem; color: var(--text-primary); }
small { font-size: .66rem; line-height: 1.45; color: var(--text-muted); }
.recommendation, .gpu-note, .save-message, .settings-error {
  margin: 10px 0 16px; padding: 10px 12px; border-radius: 9px; font-size: .74rem; line-height: 1.55;
}
.recommendation { background: var(--signal-glow); color: var(--text-secondary); }
.recommendation span { margin-left: 6px; color: var(--text-muted); }
fieldset { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 0 0 18px; border: 0; }
legend { grid-column: 1 / -1; margin-bottom: 8px; font-size: .78rem; font-weight: 600; }
.profile-option {
  display: flex; gap: 9px; padding: 11px; cursor: pointer;
  border: 1px solid var(--border-subtle); border-radius: 10px; background: var(--bg-elevated);
}
.profile-option.selected { border-color: var(--accent); background: var(--accent-glow); }
.profile-option.disabled { opacity: .48; cursor: not-allowed; }
.profile-option input { margin-top: 3px; }
.profile-option strong, .profile-option small { display: block; }
.profile-option strong { font-size: .76rem; }
.profile-option em {
  margin-left: 5px; padding: 1px 5px; border-radius: 4px;
  font: normal .5rem var(--font-mono); color: var(--signal); background: var(--signal-glow);
}
.path-grid { grid-template-columns: 1fr; margin-bottom: 14px; }
.path-grid label, .tuning-grid label { display: grid; gap: 6px; }
input, select {
  width: 100%; padding: 9px 10px; border: 1px solid var(--border-subtle);
  border-radius: 8px; color: var(--text-primary); background: var(--bg-elevated);
}
.tuning-grid { grid-template-columns: 1.2fr .8fr 1fr; margin-bottom: 12px; }
.gpu-note { background: rgba(213, 157, 64, .1); color: var(--text-secondary); }
.save-message { background: var(--signal-glow); color: var(--signal); }
.settings-error { background: rgba(194, 85, 77, .1); color: var(--error); }
footer { justify-content: flex-end; margin-top: 18px; }
footer button { padding: 9px 16px; border-radius: 8px; font-size: .76rem; }
.secondary { color: var(--text-secondary); border: 1px solid var(--border-subtle); }
.primary { color: #071012; background: var(--signal); font-weight: 700; }
@media (max-width: 640px) {
  .hardware-card, fieldset, .tuning-grid { grid-template-columns: 1fr; }
}
</style>
