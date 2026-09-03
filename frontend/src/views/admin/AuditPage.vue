<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Scroll, RefreshCw, Search } from 'lucide-vue-next'

const { api } = useApi()
const records = ref<any[]>([])
const loading = ref(true)
const search = ref('')
const detailRec = ref<any | null>(null)

async function load() {
  loading.value = true
  try {
    const res = await api('/api/v1/admin/audit?limit=200')
    records.value = res.records || []
  } finally {
    loading.value = false
  }
}

function filtered() {
  const q = search.value.trim().toLowerCase()
  if (!q) return records.value
  return records.value.filter((r) =>
    [r.action, r.status, JSON.stringify(r.detail || '')].join(' ').toLowerCase().includes(q)
  )
}

function statusColor(s: string) {
  if (s === 'success' || s === 'completed' || s === 'accepted') return 'text-emerald-400'
  if (s === 'failed' || s === 'denied') return 'text-rose-400'
  return 'text-amber-400'
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">只追加的操作审计流水；登录、配置变更、交易动作全部留痕。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">治理 · 1/3</span>
    </div>

    <!-- Toolbar -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-3 flex items-center gap-3">
      <div class="flex items-center space-x-2 flex-1 bg-[#090f18] border border-[#1A2232] rounded-lg px-3 py-2">
        <Search class="w-3.5 h-3.5 text-[#707E94]" />
        <input v-model="search" placeholder="搜索动作 / 状态 / 账号 / 详情..." class="flex-1 bg-transparent text-xs font-mono text-white outline-none" />
      </div>
      <button @click="load" class="flex items-center space-x-1 px-3 py-2 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" /><span>刷新</span>
      </button>
    </div>

    <!-- Audit Rows -->
    <div class="rounded-xl border overflow-hidden shadow-xs" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
      <div class="px-4 py-3 border-b flex items-center justify-between" style="border-color: var(--border-subtle); background-color: var(--bg-card-subtle);">
        <div class="flex items-center space-x-2">
          <Scroll class="w-4 h-4 text-purple-400" />
          <h2 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">
            安全与操作审计流水 ({{ filtered().length }} 条)
          </h2>
        </div>
        <span class="text-[11px] font-mono" style="color: var(--text-faint);">点击任意行穿透查看原始参数 JSON</span>
      </div>

      <div class="overflow-x-auto max-h-[580px] overflow-y-auto">
        <table class="w-full text-left text-xs font-mono whitespace-nowrap">
          <thead class="sticky top-0 z-10">
            <tr class="border-b text-[11px] uppercase tracking-wider font-bold" style="border-color: var(--border-subtle); background-color: var(--bg-card-subtle); color: var(--text-muted);">
              <th class="py-2.5 px-4">时间戳</th>
              <th class="py-2.5 px-3">动作类型</th>
              <th class="py-2.5 px-3">执行结果</th>
              <th class="py-2.5 px-4">操作者与审计详情</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(r, i) in filtered()"
              :key="i"
              @click="detailRec = r"
              class="border-b last:border-b-0 hover:bg-[var(--bg-card-hover)] transition-colors cursor-pointer"
              style="border-color: var(--border-subtle);"
            >
              <td class="py-2.5 px-4 num-tabular" style="color: var(--text-faint);">{{ r.timestamp }}</td>
              <td class="py-2.5 px-3 font-bold" style="color: var(--color-brand);">{{ r.action }}</td>
              <td class="py-2.5 px-3 font-bold" :class="statusColor(r.status)">{{ r.status }}</td>
              <td class="py-2.5 px-4 max-w-[480px] truncate" style="color: var(--text-muted);">
                <strong style="color: var(--text-main);">{{ r.detail?.actor || r.detail?.username || 'system' }}</strong>
                <span class="ml-1 opacity-70">· {{ JSON.stringify(r.detail || {}) }}</span>
              </td>
            </tr>
            <tr v-if="filtered().length === 0">
              <td colspan="4" class="py-8 text-center" style="color: var(--text-faint);">暂无符合条件的审计记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="detailRec" class="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4" @click.self="detailRec = null">
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-5 w-full max-w-[640px] max-h-[88dvh] overflow-y-auto">
        <h3 class="text-sm font-bold text-white mb-3 font-mono">审计详情 · {{ detailRec.action }}</h3>
        <pre class="bg-[#080B10] border border-[#1A2232] rounded-lg p-3 text-xs font-mono text-zinc-300 whitespace-pre-wrap max-h-[400px] overflow-y-auto">{{ JSON.stringify(detailRec, null, 2) }}</pre>
        <div class="flex justify-end mt-4"><button @click="detailRec = null" class="px-4 py-2 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">关闭</button></div>
      </div>
    </div>
  </div>
</template>
