/**
 * useHistory — localStorage-backed OCR session history.
 *
 * Each entry stores metadata + extracted texts (boxes omitted for space).
 * The result object is saved as-is but capped: if serialised size exceeds
 * MAX_RESULT_BYTES, only texts are stored (no scores/boxes).
 */

const STORAGE_KEY  = 'ppocr-history'
const MAX_ENTRIES  = 30
const MAX_RESULT_BYTES = 500_000  // 500 KB per entry

import { ref } from 'vue'

function load() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

function persist(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
  } catch {
    // QuotaExceededError — try saving without result blobs
  }
}

export function useHistory() {
  const entries = ref(load())

  function refresh() {
    entries.value = load()
  }

  /**
   * Save a completed OCR session to history.
   * @param {{ fileName, fileSize, fileType, result }} opts
   */
  function save({ fileName, fileSize, fileType, result }) {
    if (!result?.pages?.length) return

    const pages  = result.pages.filter(Boolean)
    const lines  = pages.reduce((a, p) => a + (p.texts?.length ?? 0), 0)
    const scores = pages.flatMap(p => p.scores ?? [])
    const avg    = scores.length
      ? (scores.reduce((a, s) => a + s, 0) / scores.length * 100).toFixed(1)
      : '0.0'

    // Build compact result payload (strip boxes to save space, keep scores)
    const compactPages = pages.map(p => ({
      page:   p.page,
      width:  p.width,
      height: p.height,
      texts:  p.texts  ?? [],
      scores: p.scores ?? [],
    }))

    let resultPayload = compactPages
    // If still too large, strip scores too
    const asJson = JSON.stringify(compactPages)
    if (asJson.length > MAX_RESULT_BYTES) {
      resultPayload = pages.map(p => ({
        page:   p.page,
        texts:  p.texts ?? [],
        scores: [],
      }))
    }

    const entry = {
      id:       Date.now(),
      fileName,
      fileSize,
      fileType: fileType || 'image',
      date:     new Date().toISOString(),
      summary: {
        pages:    pages.length,
        lines,
        avgScore: avg,
      },
      pages: resultPayload,
    }

    const list = [entry, ...load()].slice(0, MAX_ENTRIES)
    persist(list)
    entries.value = list
  }

  /**
   * Remove one entry by id.
   */
  function remove(id) {
    const list = load().filter(e => e.id !== id)
    persist(list)
    entries.value = list
  }

  /**
   * Clear all history.
   */
  function clear() {
    localStorage.removeItem(STORAGE_KEY)
    entries.value = []
  }

  /**
   * Convert a history entry back into a result object compatible with the OCR result format.
   */
  function toResult(entry) {
    return {
      status: 'success',
      pages:  entry.pages,
      total_pages: entry.summary.pages,
      processed_pages: entry.summary.pages,
    }
  }

  return { entries, save, remove, clear, toResult, refresh }
}
