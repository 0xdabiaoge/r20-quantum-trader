<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Brain, Terminal, RefreshCw } from 'lucide-vue-next'

const { api } = useApi()
const loading = ref(true)
const logs = ref<string[]>([])
const activeLogTab = ref<'trader' | 'backend' | 'scheduler'>('trader')
const logContent = ref<string>('')
const logLoading = ref(false)

async function loadDecisions() {
  loading.value = true
  try {
    const res = await api('/api/v1/admin/runtime')
    logs.value = res.recent_logs || []
    await fetchLogStream('trader')
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function fetchLogStream(type: 'trader' | 'backend' | 'scheduler') {
  activeLogTab.value = type
  logLoading.value = true
  try {
    const res = await api(`/api/v1/admin/logs?source=${type}&lines=100`)
    logContent.value = res.content || res.lines?.join('\n') || '无实时日志'
  } catch (e: any) {
    logContent.value = `获取日志失败: ${e.message}`
  } finally {
    logLoading.value = false
  }
}

onMounted(() => {
  loadDecisions()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">核对 AI 宏观基调与逐币动作，并审查多路实时日志流。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">日常运行 · 3/4</span>
    </div>

    <!-- 3-Way Log Streams -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
      <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
        <div class="flex items-center space-x-2">
          <Terminal class="w-4 h-4 text-purple-400" />
          <h2 class="text-xs font-bold text-white font-mono uppercase">系统实时日志流</h2>
        </div>
        <!-- Log Selector Tabs -->
        <div class="flex space-x-1 bg-[#080B10] p-1 rounded-lg border border-[#1A2232]">
          <button
            @click="fetchLogStream('trader')"
            class="px-2.5 py-1 rounded text-xs font-mono font-bold cursor-pointer transition-colors"
            :class="activeLogTab === 'trader' ? 'bg-blue-600 text-white' : 'text-[#707E94] hover:text-white'"
          >
            交易巡检 (Trader)
          </button>
          <button
            @click="fetchLogStream('backend')"
            class="px-2.5 py-1 rounded text-xs font-mono font-bold cursor-pointer transition-colors"
            :class="activeLogTab === 'backend' ? 'bg-blue-600 text-white' : 'text-[#707E94] hover:text-white'"
          >
            控制面服务 (Backend)
          </button>
          <button
            @click="fetchLogStream('scheduler')"
            class="px-2.5 py-1 rounded text-xs font-mono font-bold cursor-pointer transition-colors"
            :class="activeLogTab === 'scheduler' ? 'bg-blue-600 text-white' : 'text-[#707E94] hover:text-white'"
          >
            任务调度器 (Scheduler)
          </button>
        </div>
      </div>

      <div class="relative">
        <div v-if="logLoading" class="absolute inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center text-xs font-mono text-blue-400">
          <RefreshCw class="w-4 h-4 animate-spin mr-1.5" />
          <span>正在拉取最新日志流...</span>
        </div>
        <pre class="bg-[#080B10] border border-[#1A2232]/80 rounded-lg p-3 text-xs font-mono text-zinc-300 max-h-[500px] overflow-y-auto whitespace-pre-wrap leading-relaxed">{{ logContent }}</pre>
      </div>
    </div>
  </div>
</template>
