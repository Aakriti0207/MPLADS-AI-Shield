import { useCallback, useEffect, useState } from 'react'

/**
 * Tiny data-loading hook for the public portal.
 *
 * - aborts the in-flight request when deps change or the page unmounts
 * - keeps the previous `data` visible while a new request is loading
 *   (`refreshing` is true then) so lists do not flash blank
 * - exposes `retry()` for the "Try again" button
 */
export default function usePublicQuery(fetcher, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    setState(prev => ({ data: prev.data, error: null, loading: true }))

    fetcher({ signal: controller.signal })
      .then(data => { if (active) setState({ data, error: null, loading: false }) })
      .catch(error => {
        if (!active || error?.name === 'AbortError') return
        setState({ data: null, error, loading: false })
      })

    return () => {
      active = false
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt])

  const retry = useCallback(() => setAttempt(n => n + 1), [])

  return {
    data: state.data,
    error: state.error,
    loading: state.loading,
    refreshing: state.loading && state.data !== null,
    retry,
  }
}