<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Brain, Terminal, RefreshCw, Sparkles, Plus, Trash2, CheckCircle2, AlertCircle } from 'lucide-vue-next'

const { api } = useApi()
const loading = ref(true)
const logs = ref<string[]>([])
const activeLogTab = ref<'trader' | 'backend' | 'scheduler'>('trader')
const logContent = ref<string>('')
const logLoading = ref(false)

// Memory items state
const memoryItems = ref<string[]>([])
const memoryLoading = ref(false)
const newMemoryText = ref('')
const memoryBusy = ref(false)
const memoryBanner = ref<{ text: string; type: 'ok' | 'err' } | null>(null)

async function loadDecisions() {
  loading.value = true
  try {
    const res = await api('/api/v1/admin/runtime')
    logs.value = res.recent_logs || []
    await Promise.all([fetchLogStream('trader'), loadMemoryItems()])
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadMemoryItems() {
  memoryLoading.value = true
  try {
    const res = await api('/api/v1/admin/memory')
    memoryItems.value = res.items || []
  } catch (e: any) {
    console.error('加载记忆失败:', e)
  } finally {
    memoryLoading.value = false
  }
}

async function addMemoryItem() {
  const text = newMemoryText.value.trim()
  if (!text) return
  memoryBusy.value = true
  memoryBanner.value = null
  try {
    const res = await api('/api/v1/admin/memory', {
      method: 'POST',
      body: JSON.stringify({ text })
    })
    memoryItems.value = res.items || []
    newMemoryText.value = ''
    memoryBanner.value = { text: '✅ 自进化实战心法已新增并写入大模型注入层', type: 'ok' }
  } catch (e: any) {
    memoryBanner.value = { text: `新增失败: ${e.message}`, type: 'err' }
  } finally {
    memoryBusy.value = false
  }
}

async function deleteMemoryItem(index: number) {
  if (!confirm('确定删除此条自进化心法吗？删除后大模型推演将不再参考本条规则。')) return
  memoryBusy.value = true
  memoryBanner.value = null
  try {
    const res = await api(`/api/v1/admin/memory/${index}`, {
      method: 'DELETE'
    })
    memoryItems.value = res.items || []
    memoryBanner.value = { text: '✅ 该条自进化心法已删除', type: 'ok' }
  } catch (e: any) {
    memoryBanner.value = { text: `删除失败: ${e.message}`, type: 'err' }
  } finally {
    memoryBusy.value = false
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
  <div class="space-y-4 max-w-[2160px] mx-auto">
    <div class="flex items-center justify-between">
      <p class="text-xs font-mono" style="color: var(--text-muted);">核对 AI 宏观基调与逐币动作，管理大模型自进化长期心法记忆，并审查多路实时日志流。</p>
      <span
        class="text-[10px] font-mono px-2 py-1 rounded border font-bold"
        style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
      >
        日常运行 · 3/4
      </span>
    </div>

    <!-- AI Self-Improvement Heuristic Memory Management Card -->
    <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
        <div class="flex items-center space-x-2">
          <Brain class="w-4 h-4 text-emerald-400" />
          <h2 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">AI 自进化长期实战心法记忆 ({{ memoryItems.length }})</h2>
        </div>
        <div class="flex items-center space-x-2 text-[10px] font-mono" style="color: var(--text-faint);">
          <Sparkles class="w-3.5 h-3.5 text-amber-400" />
          <span>每 6 小时自动复盘提炼 · 实时注入 AI 交易决策 System Prompt</span>
        </div>
      </div>

      <div v-if="memoryBanner" class="p-2.5 mb-3 rounded-lg text-xs font-mono border" :class="memoryBanner.type === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'">
        <div class="flex items-center gap-2">
          <CheckCircle2 v-if="memoryBanner.type === 'ok'" class="w-3.5 h-3.5 shrink-0" />
          <AlertCircle v-else class="w-3.5 h-3.5 shrink-0" />
          <span>{{ memoryBanner.text }}</span>
        </div>
      </div>

      <!-- Add New Memory Rule -->
      <div class="flex flex-col sm:flex-row gap-2 mb-4">
        <input
          v-model="newMemoryText"
          @keydown.enter="addMemoryItem"
          placeholder="输入新提炼的实战心法（例如：【箱体边界高胜率】箱体震荡区间下沿触及强支撑果断低吸...）"
          class="flex-1 rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors"
          style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
        />
        <button
          @click="addMemoryItem"
          :disabled="memoryBusy || !newMemoryText.trim()"
          class="flex items-center justify-center space-x-1 px-4 py-2 rounded-lg text-xs font-mono font-bold cursor-pointer disabled:opacity-40 transition-all shadow-xs shrink-0"
          style="background-color: var(--text-main); color: var(--bg-card);"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>{{ memoryBusy ? '添加中...' : '添加心法' }}</span>
        </button>
      </div>

      <!-- Memory Items List -->
      <div class="space-y-2">
        <div v-if="memoryLoading" class="py-6 text-center text-xs font-mono" style="color: var(--text-muted);">
          <RefreshCw class="w-4 h-4 animate-spin inline mr-1.5" style="color: var(--color-brand);" />
          正在加载自进化心法...
        </div>
        <template v-else-if="memoryItems.length">
          <div
            v-for="(item, idx) in memoryItems"
            :key="idx"
            class="flex items-start justify-between gap-3 p-3 rounded-lg border transition-colors group"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
          >
            <div class="flex items-start space-x-2.5 flex-1 min-w-0">
              <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border shrink-0 mt-0.5" style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--color-brand);">#{{ idx + 1 }}</span>
              <p class="text-xs font-mono leading-relaxed select-text" style="color: var(--text-main);">{{ item }}</p>
            </div>
            <button
              @click="deleteMemoryItem(idx)"
              class="p-1 rounded hover:bg-rose-500/20 text-rose-400 opacity-60 group-hover:opacity-100 transition-opacity cursor-pointer shrink-0"
              title="删除此条心法"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </template>
        <div v-else class="py-6 text-center text-xs font-mono border rounded-lg border-dashed" style="border-color: var(--border-subtle); color: var(--text-faint);">
          暂无自进化长期心法记忆，可手动添加或等待每 6 小时自动复盘提炼
        </div>
      </div>
    </div>

    <!-- 3-Way Log Streams -->
    <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
        <div class="flex items-center space-x-2">
          <Terminal class="w-4 h-4 text-purple-400" />
          <h2 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">系统实时日志流</h2>
        </div>
        <!-- Log Selector Tabs -->
        <div class="flex flex-wrap gap-1 p-1 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <button
            @click="fetchLogStream('trader')"
            class="px-2.5 py-1 rounded text-xs font-mono font-bold cursor-pointer transition-colors"
            :style="activeLogTab === 'trader' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { color: 'var(--text-muted)' }"
          >
            交易巡检 (Trader)
          </button>
          <button
            @click="fetchLogStream('backend')"
            class="px-2.5 py-1 rounded text-xs font-mono font-bold cursor-pointer transition-colors"
            :style="activeLogTab === 'backend' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { color: 'var(--text-muted)' }"
          >
            控制面服务 (Backend)
          </button>
          <button
            @click="fetchLogStream('scheduler')"
            class="px-2.5 py-1 rounded text-xs font-mono font-bold cursor-pointer transition-colors"
            :style="activeLogTab === 'scheduler' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { color: 'var(--text-muted)' }"
          >
            任务调度器 (Scheduler)
          </button>
        </div>
      </div>

      <div class="relative">
        <div v-if="logLoading" class="absolute inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center text-xs font-mono" style="color: var(--color-brand);">
          <RefreshCw class="w-4 h-4 animate-spin mr-1.5" />
          <span>正在拉取最新日志流...</span>
        </div>
        <pre class="border rounded-lg p-3 text-xs font-mono max-h-[520px] overflow-y-auto whitespace-pre-wrap leading-relaxed select-text" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-main);">{{ logContent }}</pre>
      </div>
    </div>
  </div>
</template>
