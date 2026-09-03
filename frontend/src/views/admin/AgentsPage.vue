<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Package, Cpu, KeyRound, RefreshCw } from 'lucide-vue-next'

const { api } = useApi()
const data = ref<any>(null)
const loading = ref(true)
const errText = ref('')

async function load() {
  loading.value = true
  try {
    data.value = await api('/api/v1/admin/agents')
    errText.value = ''
  } catch (e: any) {
    errText.value = e.message
  } finally {
    loading.value = false
  }
}

function statusColor(s: string) {
  if (['success', 'running', 'online', 'idle'].includes(s)) return 'text-emerald-400'
  if (['failed', 'error', 'offline'].includes(s)) return 'text-rose-400'
  return 'text-amber-400'
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">受管 Worker 存活、密文库状态与大模型调用遥测。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">策略配置 · 3/3</span>
    </div>

    <div v-if="errText" class="p-3 rounded-lg text-xs font-mono bg-rose-500/10 border border-rose-500/20 text-rose-400">{{ errText }}</div>
    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]"><RefreshCw class="w-5 h-5 animate-spin inline mr-1.5 text-blue-400" />正在加载运行单元...</div>

    <template v-else-if="data">
      <!-- Agents -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center space-x-2"><Package class="w-4 h-4 text-blue-400" /><h2 class="text-xs font-bold text-white font-mono uppercase">受管 Worker</h2></div>
          <button @click="load" class="px-2.5 py-1 rounded bg-[#111c2a] border border-[#33445b] text-[10px] font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">刷新</button>
        </div>
        <table class="w-full text-left text-xs font-mono">
          <thead><tr class="text-[#707E94] border-b border-[#1A2232]"><th class="pb-2">Worker</th><th class="pb-2">职责</th><th class="pb-2">健康</th><th class="pb-2">最近运行</th><th class="pb-2">结果</th><th class="pb-2">产物时效</th></tr></thead>
          <tbody class="divide-y divide-[#1A2232]/50">
            <tr v-for="a in data.agents" :key="a.id">
              <td class="py-2 text-white font-bold">{{ a.name }}</td>
              <td class="py-2 text-zinc-300">{{ a.role }}</td>
              <td class="py-2 font-bold" :class="statusColor(a.health)">{{ a.health }}</td>
              <td class="py-2 text-[#707E94]">{{ a.last_run_at || '--' }}</td>
              <td class="py-2" :class="statusColor(a.last_run_status)">{{ a.last_run_status }}</td>
              <td class="py-2 text-zinc-300">{{ a.output_age_seconds != null ? Math.round(a.output_age_seconds / 60) + ' 分钟前' : (a.output ? '冷启动' : '无产物') }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Model Telemetry -->
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 mb-3"><Cpu class="w-4 h-4 text-purple-400" /><h2 class="text-xs font-bold text-white font-mono uppercase">模型调用遥测 (最近 50)</h2></div>
          <div class="text-[10px] text-[#707E94] font-mono mb-2 p-2 rounded bg-[#080B10] border border-[#1A2232]">{{ data.prompt_policy }}</div>
          <div class="grid grid-cols-3 gap-2 mb-3 text-center">
            <div class="bg-[#080B10] border border-[#1A2232] rounded-lg p-2"><div class="text-[10px] text-[#707E94] font-mono">总调用</div><div class="text-sm font-bold text-white font-mono">{{ data.model_stats?.total_calls ?? '--' }}</div></div>
            <div class="bg-[#080B10] border border-[#1A2232] rounded-lg p-2"><div class="text-[10px] text-[#707E94] font-mono">成功率</div><div class="text-sm font-bold" :class="(data.model_stats?.total_calls ?? 0) > 0 && (data.model_stats?.successful_calls ?? 0) < (data.model_stats?.total_calls ?? 0) ? 'text-amber-400' : 'text-emerald-400'">{{ (data.model_stats?.total_calls ?? 0) > 0 ? Math.round(100 * (data.model_stats?.successful_calls ?? 0) / data.model_stats.total_calls) + '%' : '--' }}</div></div>
            <div class="bg-[#080B10] border border-[#1A2232] rounded-lg p-2"><div class="text-[10px] text-[#707E94] font-mono">平均时延</div><div class="text-sm font-bold text-white font-mono">{{ data.model_stats?.avg_duration_ms ? Math.round(data.model_stats.avg_duration_ms) + 'ms' : '--' }}</div></div>
          </div>
          <div class="max-h-60 overflow-y-auto">
            <table class="w-full text-left text-xs font-mono">
              <thead><tr class="text-[#707E94] border-b border-[#1A2232]"><th class="pb-1.5">调用方</th><th class="pb-1.5">模型</th><th class="pb-1.5">状态</th><th class="pb-1.5">Tokens</th><th class="pb-1.5 text-right">耗时</th></tr></thead>
              <tbody class="divide-y divide-[#1A2232]/50">
                <tr v-for="c in (data.model_calls || []).slice(0, 30)" :key="c.id">
                  <td class="py-1.5 text-zinc-300">{{ c.caller || '--' }}</td>
                  <td class="py-1.5 text-[#707E94]">{{ c.model || '--' }}</td>
                  <td class="py-1.5 font-bold" :class="statusColor(c.status)">{{ c.status }}</td>
                  <td class="py-1.5 text-zinc-300">{{ c.total_tokens ?? '--' }}</td>
                  <td class="py-1.5 text-right text-zinc-300">{{ c.duration_ms ? Math.round(c.duration_ms) + 'ms' : '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Secret Store -->
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 mb-3"><KeyRound class="w-4 h-4 text-amber-400" /><h2 class="text-xs font-bold text-white font-mono uppercase">本机加密密文库</h2></div>
          <div class="space-y-1.5 text-xs font-mono">
            <div class="flex items-center justify-between bg-[#080B10] border border-[#1A2232] rounded-lg px-3 py-2">
              <span class="text-[#707E94]">加密库状态</span>
              <span :class="data.secret_store?.initialized ? 'text-emerald-400' : 'text-rose-400'">{{ data.secret_store?.initialized ? '已初始化 ✓' : '未初始化' }} · {{ data.secret_store?.count ?? 0 }} 项密文 · 文件权限 {{ data.secret_store?.store_mode || '--' }}</span>
            </div>
            <div class="flex items-center justify-between bg-[#080B10] border border-[#1A2232] rounded-lg px-3 py-2">
              <span class="text-[#707E94]">读取优先级</span><span class="text-white">{{ data.secret_store?.source_priority || 'encrypted-store-over-env' }}</span>
            </div>
            <div v-for="k in (data.secret_store?.keys || [])" :key="k" class="flex items-center justify-between bg-[#080B10] border border-[#1A2232] rounded-lg px-3 py-2">
              <span class="text-zinc-300">{{ k }}</span>
              <span class="text-emerald-400">已配置 ✓</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
