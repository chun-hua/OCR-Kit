/**
 * PP-OCR API client — thin wrapper around the FastAPI backend.
 *
 * Endpoints:
 *   POST /ocr/image   — OCR on image file
 *   POST /ocr/pdf     — OCR on PDF file
 *   POST /ocr/text    — OCR on image, plain text only
 *   GET  /health      — server health check
 */

const BASE = '' // proxied by Vite in dev

/**
 * @typedef {Object} TextLine
 * @property {string} text
 * @property {number} score
 * @property {number[]} box — [x1, y1, x2, y2]
 */

/**
 * @typedef {Object} OcrPage
 * @property {number} [page]
 * @property {string[]} texts
 * @property {number[]} scores
 * @property {number[][]} boxes
 */

/**
 * @typedef {Object} OcrResult
 * @property {string} status
 * @property {OcrPage[]} pages
 * @property {number} [total_pages]
 * @property {number} [processed_pages]
 */

/** Check server health. */
export async function checkHealth() {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
  return res.json()
}

/**
 * OCR an image file. Returns full result with texts, scores, boxes.
 * @param {File} file
 * @returns {Promise<OcrResult>}
 */
export async function ocrImage(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/ocr/image`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `OCR failed: ${res.status}`)
  }
  return res.json()
}

/**
 * OCR a PDF file.
 * @param {File} file
 * @param {{ dpi?: number, max_pages?: number }} [opts]
 * @returns {Promise<OcrResult>}
 */
export async function ocrPdf(file, { dpi = 200, max_pages = 0 } = {}) {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ dpi: String(dpi), max_pages: String(max_pages) })
  const res = await fetch(`${BASE}/ocr/pdf?${params}`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `PDF OCR failed: ${res.status}`)
  }
  return res.json()
}

/**
 * OCR an image, returning only the concatenated plain text.
 * @param {File} file
 * @returns {Promise<{ status: string, text: string }>}
 */
export async function ocrText(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/ocr/text`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `OCR failed: ${res.status}`)
  }
  return res.json()
}
