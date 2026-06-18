import { ref, computed, shallowRef } from 'vue'
import { ocrImage, ocrPdf, checkHealth } from '../api/ocr.js'
import { connectResultStream } from '../api/sse.js'

/**
 * Composable for OCR workflow state.
 * Tracks: file, mode (image/pdf), loading, result, error, streaming.
 *
 * For PDFs, results are accumulated progressively via SSE — pages appear
 * incrementally as they are processed, rather than all at once at the end.
 */
export function useOcr() {
  const file = ref(null)
  const previewUrl = ref(null)
  const loading = ref(false)
  /** @type {import('vue').Ref<null|{status:string, pages:any[], total_pages?:number, processed_pages?:number}>} */
  const result = shallowRef(null)
  const error = ref(null)
  const mode = ref('image') // 'image' | 'pdf'
  const dpi = ref(200)
  const maxPages = ref(0) // 0 = all
  const isStreaming = ref(false)

  // ── Progressive PDF state ──
  /** Number of pages received so far via SSE */
  const progressivePagesReceived = ref(0)
  /** Total pages expected (from 'done' or API response) */
  const progressivePagesTotal = ref(0)

  let _resultSSE = null

  const fileName = computed(() => file.value?.name ?? '')
  const fileSize = computed(() => {
    if (!file.value) return ''
    const kb = file.value.size / 1024
    return kb < 1024 ? `${kb.toFixed(1)} KB` : `${(kb / 1024).toFixed(1)} MB`
  })

  function setFile(f, preview) {
    revokePreview()
    file.value = f
    previewUrl.value = preview ?? null
    result.value = null
    error.value = null
    progressivePagesReceived.value = 0
    progressivePagesTotal.value = 0
    // auto-detect mode from extension
    if (f?.name?.toLowerCase().endsWith('.pdf')) {
      mode.value = 'pdf'
    } else {
      mode.value = 'image'
    }
  }

  function revokePreview() {
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value)
      previewUrl.value = null
    }
  }

  /**
   * Start listening to the results SSE stream.
   * Accumulates incoming page data into result.pages incrementally.
   */
  function _startResultSSE() {
    _stopResultSSE()
    _resultSSE = connectResultStream({
      onEvent: (evt) => {
        if (evt.type === 'page') {
          // Accumulate page into result
          if (!result.value) {
            result.value = { status: 'streaming', pages: [], total_pages: 0, processed_pages: 0 }
          }
          const pageData = {
            page: evt.page,
            width: evt.width,
            height: evt.height,
            texts: evt.texts || [],
            scores: evt.scores || [],
            boxes: evt.boxes || [],
          }
          // Insert into pages array at correct position (pages are 1-indexed, array 0-indexed)
          const idx = evt.page - 1
          if (result.value.pages.length <= idx) {
            // Extend array to fit
            while (result.value.pages.length <= idx) {
              result.value.pages.push(null)
            }
          }
          result.value.pages[idx] = pageData
          progressivePagesReceived.value = idx + 1
          // Server sends processed_pages with every page event — capture it immediately
          if (evt.processed_pages) progressivePagesTotal.value = evt.processed_pages

          // Trigger reactivity (shallowRef needs reassignment)
          result.value = { ...result.value }
        } else if (evt.type === 'done') {
          if (result.value) {
            result.value.total_pages = evt.total_pages
            result.value.processed_pages = evt.processed_pages
            progressivePagesTotal.value = evt.processed_pages
            result.value = { ...result.value }
          }
        } else if (evt.type === 'error') {
          error.value = evt.message
        }
      },
      onConnected: () => {
        // Results stream connected — ready to receive pages
      },
      onError: (err) => {
        console.warn('[Result SSE]', err.message)
      },
    })
  }

  function _stopResultSSE() {
    if (_resultSSE) {
      _resultSSE.close()
      _resultSSE = null
    }
  }

  async function run() {
    if (!file.value) return
    loading.value = true
    isStreaming.value = true
    error.value = null
    result.value = null
    progressivePagesReceived.value = 0
    progressivePagesTotal.value = 0

    try {
      if (mode.value === 'pdf') {
        // Start results SSE BEFORE the API call so we don't miss early pages
        _startResultSSE()

        const apiResult = await ocrPdf(file.value, {
          dpi: dpi.value,
          max_pages: maxPages.value,
        })

        // Merge SSE-accumulated result with the final API response.
        // SSE may have partial data (some pages null), so prefer the API's
        // complete payload for the final state. But if SSE pages arrived
        // (progressive mode worked), keep the progressive result — it's
        // already complete since `done` fires after all pages.
        if (result.value && result.value.pages.filter(Boolean).length > 0) {
          // Progressive mode worked — finalize status
          result.value.status = 'success'
          result.value.total_pages = apiResult.total_pages
          result.value.processed_pages = apiResult.processed_pages
          // Fill any gaps from the API response
          for (let i = 0; i < apiResult.pages.length; i++) {
            if (!result.value.pages[i] || !result.value.pages[i].texts) {
              result.value.pages[i] = apiResult.pages[i]
            }
          }
          result.value = { ...result.value }
        } else {
          // Fallback: SSE didn't work (e.g., started before server), use API result
          result.value = apiResult
        }
      } else {
        // Single image — fast enough that progressive isn't needed
        result.value = await ocrImage(file.value)
      }
    } catch (e) {
      error.value = e.message
      _stopResultSSE()
    } finally {
      loading.value = false
      isStreaming.value = false
      _stopResultSSE()
    }
  }

  function clear() {
    revokePreview()
    _stopResultSSE()
    file.value = null
    previewUrl.value = null
    result.value = null
    error.value = null
    isStreaming.value = false
    progressivePagesReceived.value = 0
    progressivePagesTotal.value = 0
  }

  return {
    // state
    file, previewUrl, loading, result, error, mode, dpi, maxPages, isStreaming,
    progressivePagesReceived, progressivePagesTotal,
    // computed
    fileName, fileSize,
    // actions
    setFile, run, clear, revokePreview,
  }
}

/**
 * Simple health-check composable.
 */
export function useHealth() {
  const status = ref('checking') // 'checking' | 'ok' | 'error'
  const info = ref(null)

  async function check() {
    status.value = 'checking'
    try {
      info.value = await checkHealth()
      status.value = 'ok'
    } catch {
      status.value = 'error'
    }
  }

  return { status, info, check }
}
