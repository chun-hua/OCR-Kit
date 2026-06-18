/**
 * SSE (Server-Sent Events) client for the OCR server.
 *
 * Two streams:
 *   GET /ocr/logs    — structured log events (progress, status)
 *   GET /ocr/results — partial OCR results (page data as it completes)
 *
 * EventSource handles reconnection natively — no manual retry loop.
 * Callbacks: onConnected (open), onEvent (message), onReconnecting (transient
 * error, browser is retrying), onDisconnected + onError (permanent close).
 *
 * Usage:
 *   import { connectLogStream, connectResultStream } from './api/sse.js'
 *
 *   const logs = connectLogStream({
 *     onEvent: (log) => console.log(log),
 *     onConnected: () => {},
 *     onReconnecting: () => {},
 *     onDisconnected: () => {},
 *     onError: (err) => console.error(err),
 *   })
 *
 *   const results = connectResultStream({
 *     onEvent: (result) => console.log(result),
 *     ...
 *   })
 */

const BASE = '' // proxied by Vite in dev

/**
 * @typedef {Object} LogEvent
 * @property {string} timestamp      - "14:23:05.123"
 * @property {'info'|'debug'|'warn'|'error'} level
 * @property {string} stage
 * @property {string} stage_label
 * @property {string} message
 * @property {Object} [detail]
 * @property {number} [progress_pct]
 * @property {number} [progress_current]
 * @property {number} [progress_total]
 */

/**
 * @typedef {Object} ResultEvent
 * @property {'connected'|'page'|'done'|'error'} type
 * @property {string} [message]
 * @property {number} [page]
 * @property {string[]} [texts]
 * @property {number[]} [scores]
 * @property {number[][]} [boxes]
 * @property {number} [width]
 * @property {number} [height]
 */

/**
 * @typedef {Object} StreamOptions
 * @property {(event: any) => void} onEvent
 * @property {() => void} [onConnected]
 * @property {() => void} [onReconnecting]
 * @property {() => void} [onDisconnected]
 * @property {(error: Error) => void} [onError]
 */

/**
 * Create an SSE connection to a given path.
 * @param {string} path - e.g. '/ocr/logs' or '/ocr/results'
 * @param {StreamOptions} opts
 * @returns {{ close: () => void }}
 */
function _createSSE(path, opts) {
  const { onEvent, onConnected, onReconnecting, onDisconnected, onError } = opts

  const es = new EventSource(`${BASE}${path}`)
  let wasEverConnected = false

  es.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data)
      onEvent(event)
    } catch (e) {
      if (msg.data.trim() && !msg.data.startsWith(':')) {
        console.warn(`[SSE ${path}] Unparseable event:`, msg.data)
      }
    }
  }

  es.onopen = () => {
    wasEverConnected = true
    onConnected?.()
  }

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      onDisconnected?.()
      onError?.(new Error(`SSE ${path} 连接已关闭（服务器不可达或网络中断）`))
    } else {
      if (wasEverConnected) {
        onReconnecting?.()
      }
    }
  }

  return {
    close() {
      es.close()
    },
  }
}

/**
 * Connect to the OCR log SSE stream.
 * @param {StreamOptions} opts
 * @returns {{ close: () => void }}
 */
export function connectLogStream(opts) {
  return _createSSE('/ocr/logs', opts)
}

/**
 * Connect to the OCR results SSE stream (progressive page output).
 * @param {StreamOptions} opts
 * @returns {{ close: () => void }}
 */
export function connectResultStream(opts) {
  return _createSSE('/ocr/results', opts)
}
