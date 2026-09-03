import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { DashboardResponse, InstrumentFactor, PositionItem, PendingOrderItem } from '../types/dashboard'

export const useDashboardStore = defineStore('dashboard', () => {
  const activeTab = ref<'trading' | 'factors' | 'news' | 'lab' | 'history'>('trading')
  const data = ref<DashboardResponse | null>(null)
  const loading = ref<boolean>(false)
  const isRefreshing = ref<boolean>(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)
  const isConnected = ref<boolean>(true)
  const pollingTimer = ref<any>(null)

  // Getters
  const account = computed(() => data.value?.account || null)
  const positions = computed<PositionItem[]>(() => data.value?.positions_summary?.items || [])
  const pendingOrders = computed<PendingOrderItem[]>(() => data.value?.pending_orders || [])
  const factors = computed<InstrumentFactor[]>(() => data.value?.factors || [])
  const macroAssessment = computed(() => data.value?.macro_assessment || '全市场宏观多周期多因子矩阵扫描中...')
  const llmRuntime = computed(() => data.value?.llm_runtime || {
    model: 'gemini-3.8-flash-high',
    provider_name: 'Google Gemini',
    reasoning_effort: 'high',
    api_format: 'openai_chat',
  })
  const logs = computed(() => data.value?.logs || [])
  const isStale = computed(() => data.value?.is_stale ?? false)

  // Actions
  async function fetchDashboard(silent = false) {
    if (!silent) {
      isRefreshing.value = true
    }
    try {
      const resp = await fetch('/api/all')
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`)
      }
      const json: DashboardResponse = await resp.json()
      data.value = json
      lastUpdated.value = new Date()
      isConnected.value = true
      error.value = null
    } catch (err: any) {
      console.error('[DashboardStore] fetch failed:', err)
      error.value = err.message || '获取数据失败'
      isConnected.value = false
    } finally {
      loading.value = false
      if (!silent) {
        setTimeout(() => {
          isRefreshing.value = false
        }, 500)
      }
    }
  }

  function startPolling(intervalMs = 3000) {
    stopPolling()
    fetchDashboard(false)
    pollingTimer.value = setInterval(() => {
      fetchDashboard(true)
    }, intervalMs)
  }

  function stopPolling() {
    if (pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
    }
  }

  return {
    activeTab,
    data,
    loading,
    isRefreshing,
    error,
    lastUpdated,
    isConnected,
    account,
    positions,
    pendingOrders,
    factors,
    macroAssessment,
    llmRuntime,
    logs,
    isStale,
    fetchDashboard,
    startPolling,
    stopPolling,
  }
})
