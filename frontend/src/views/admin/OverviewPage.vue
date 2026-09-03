<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Cpu, Database, Activity, Server, ShieldCheck } from 'lucide-vue-next'

const { api } = useApi()
const runtime = ref<any>(null)
const loading = ref(true)

async function loadRuntime() {
  loading.value = true
  try {
    runtime.value = await api('/api/v1/admin/runtime')
  } catch (e: any) {
    console.error('Failed to load runtime:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRuntime()
})

function duration(s: number | null): string {
  if (s == null) return '--'
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

function esc(v: any = ''): string {
  return String(v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}
</script>

<template>
  <div class="space-y-4">
    <!-- Guide -->
    <div class="flex items-center justify-between">
      <div>
        <p class="text-xs text-[#707E94] font-mono">从服务、数据、决策和配置状态开始；出现异常时再进入对应页面处理。</p>
      </div>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2.5 py-1 rounded border border-blue-500/20">日常运行 · 1/4</span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]">
      <RefreshCw class="w-5 h-5 animate-spin mx-auto mb-2 text-blue-400" />
      正在拉取运行态...
    </div>

    <!-- Metrics -->
    <template v-else-if="runtime">
      <!-- 4 Metric Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 mb-2">
            <Server class="w-4 h-4 text-emerald-400" />
            <span class="text-[11px] text-[#707E94] font-mono">服务状态</span>
          </div>
          <div class="text-xl font-bold text-emerald-400 font-mono">ONLINE</div>
          <div class="text-[10px] text-[#707E94] font-mono mt-1">PID {{ runtime.service?.pid || '--' }}</div>
        </div>

        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 mb-2">
            <Activity class="w-4 h-4 text-blue-400" />
            <span class="text-[11px] text-[#707E94] font-mono">运行时间</span>
          </div>
          <div class="text-xl font-bold text-white font-mono">{{ duration(runtime.service?.uptime_seconds) }}</div>
          <div class="text-[10px] text-[#707E94] font-mono mt-1">R20 standalone</div>
        </div>

        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 mb-2">
            <Database class="w-4 h-4 text-amber-400" />
            <span class="text-[11px] text-[#707E94] font-mono">数据异常</span>
          </div>
          <div class="text-xl font-bold font-mono" :class="(runtime.data_health?.filter((x: any) => !x.fresh).length || 0) === 0 ? 'text-emerald-400' : 'text-rose-400'">
            {{ runtime.data_health?.filter((x: any) => !x.fresh).length || 0 }}
          </div>
          <div class="text-[10px] text-[#707E94] font-mono mt-1">
            {{ (runtime.data_health?.filter((x: any) => !x.fresh).length || 0) === 0 ? '全部新鲜' : '存在过期链路' }}
          </div>
        </div>

        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 mb-2">
            <ShieldCheck class="w-4 h-4 text-purple-400" />
            <span class="text-[11px] text-[#707E94] font-mono">持仓追踪器</span>
          </div>
          <div class="text-xl font-bold text-white font-mono">{{ runtime.trackers || 0 }}</div>
          <div class="text-[10px] text-[#707E94] font-mono mt-1">本地运行态</div>
        </div>
      </div>

      <!-- Dual Column: Latest AI Decisions + Data Health -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <!-- AI Decisions -->
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
            <div class="flex items-center space-x-2">
              <Cpu class="w-4 h-4 text-blue-400" />
              <h2 class="text-xs font-bold text-white font-mono uppercase">最新 AI 决策</h2>
            </div>
            <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">{{ runtime.decisions?.length || 0 }} ASSETS</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs font-mono">
              <thead>
                <tr class="text-[#707E94] border-b border-[#1A2232]">
                  <th class="pb-2">标的</th>
                  <th class="pb-2">动作</th>
                  <th class="pb-2">置信度</th>
                  <th class="pb-2">更新时间</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[#1A2232]/50">
                <tr v-for="(d, i) in runtime.decisions" :key="i" class="hover:bg-[#121824]/50">
                  <td class="py-2 text-white font-bold">{{ d.instId?.replace('-USDT-SWAP', '') }}</td>
                  <td class="py-2" :class="d.action === 'WAIT' ? 'text-[#707E94]' : d.action?.includes('LONG') ? 'text-emerald-400' : 'text-rose-400'">
                    {{ d.action }}
                  </td>
                  <td class="py-2 text-zinc-300">{{ d.confidence }}%</td>
                  <td class="py-2 text-[#707E94]">{{ d.updated_at }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Data Health -->
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
            <div class="flex items-center space-x-2">
              <Database class="w-4 h-4 text-emerald-400" />
              <h2 class="text-xs font-bold text-white font-mono uppercase">数据链路健康</h2>
            </div>
            <span class="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">REALTIME</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs font-mono">
              <thead>
                <tr class="text-[#707E94] border-b border-[#1A2232]">
                  <th class="pb-2">数据源</th>
                  <th class="pb-2">状态</th>
                  <th class="pb-2">更新时间差</th>
                  <th class="pb-2">大小</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[#1A2232]/50">
                <tr v-for="(x, i) in runtime.data_health" :key="i" class="hover:bg-[#121824]/50">
                  <td class="py-2 text-white">{{ x.name }}</td>
                  <td class="py-2" :class="x.fresh ? 'text-emerald-400' : 'text-rose-400'">{{ x.fresh ? '正常' : '过期/缺失' }}</td>
                  <td class="py-2 text-[#707E94]">{{ duration(x.age_seconds) }}</td>
                  <td class="py-2 text-[#707E94]">{{ x.bytes ? Math.round(x.bytes / 1024) + ' KB' : '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Security Config Cards -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <ShieldCheck class="w-4 h-4 text-purple-400" />
            <h2 class="text-xs font-bold text-white font-mono uppercase">安全配置状态</h2>
          </div>
          <span class="text-[10px] font-mono text-[#707E94]">敏感值只显示配置状态，不回显原文</span>
        </div>
        <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <div v-for="(v, k) in runtime.configuration" :key="k" class="bg-[#080B10] border border-[#1A2232] rounded-lg p-3">
            <div class="text-[11px] text-[#707E94] font-mono">{{ k }}</div>
            <div class="text-sm text-white font-mono mt-1">{{ v || '未配置' }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script lang="ts">
import { RefreshCw } from 'lucide-vue-next'
</script>
