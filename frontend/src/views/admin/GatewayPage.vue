<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Zap, RefreshCw, RotateCcw, Server, Clock, AlertTriangle } from 'lucide-vue-next'

const { api } = useApi()
const gw = ref<any>(null)
const loading = ref(true)
const bannerMsg = ref<{ text: string; type: 'ok' | 'err' } | null>(null)

const deliveredCount = computed(() => (gw.value?.stats?.delivered ?? 0) + (gw.value?.stats?.accepted ?? 0))
const deliveryTotal = computed(() => Object.values(gw.value?.stats || {}).reduce((a: number, b: any) => a + Number(b || 0), 0))
const overdueCount = computed(() => (gw.value?.scheduler?.jobs || []).filter((j: any) => j.overdue).length)

async function load() {
  loading.value = true
  try {
    gw.value = await api('/api/v1/admin/gateway?limit=50')
  } catch (e: any) {
    bannerMsg.value = { text: `加载失败：${e.message}`, type: 'err' }
  } finally {
    loading.value = false
  }
}

async function replayDelivery(id: number) {
  const phrase = prompt(`重放投递 #${id} 需精确输入确认短语：REPLAY ${id}`)
  if (!phrase) return
  try {
    await api(`/api/v1/admin/gateway/deliveries/${id}/replay`, {
      method: 'POST',
      body: JSON.stringify({ confirmation: phrase.trim().toUpperCase() }),
    })
    bannerMsg.value = { text: `投递 #${id} 已重新入队`, type: 'ok' }
    await load()
  } catch (e: any) {
    bannerMsg.value = { text: `重放失败：${e.message}`, type: 'err' }
  }
}

function statusColor(s: string) {
  if (s === 'success' || s === 'delivered' || s === 'ok') return 'text-emerald-400'
  if (s === 'dead' || s === 'failed' || s === 'error') return 'text-rose-400'
  if (s === 'pending' || s === 'retrying') return 'text-amber-400'
  return 'text-zinc-300'
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">调度任务、事件投递队列与死信重放；Gateway 仅记录无内容遥测。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">日常运行 · 4/4</span>
    </div>

    <div v-if="bannerMsg" class="p-3 rounded-lg text-xs font-mono border" :class="bannerMsg.type === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'">{{ bannerMsg.text }}</div>

    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]"><RefreshCw class="w-5 h-5 animate-spin inline mr-1.5 text-blue-400" />正在加载网关状态...</div>

    <template v-else-if="gw">
      <!-- Worker & Stats Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 text-[11px] text-[#707E94] font-mono mb-2"><Server class="w-4 h-4 text-emerald-400" /><span>Gateway 进程</span></div>
          <div class="text-lg font-black font-mono" :class="gw.running ? 'text-emerald-400' : 'text-rose-400'">{{ gw.running ? 'ONLINE' : 'OFFLINE' }}</div>
          <div class="text-[10px] text-[#707E94] font-mono mt-1">PID {{ gw.pid || '--' }} · v{{ gw.version }}</div>
        </div>
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 text-[11px] text-[#707E94] font-mono mb-2"><Zap class="w-4 h-4 text-blue-400" /><span>投递队列</span></div>
          <div class="text-lg font-black font-mono text-white">{{ deliveredCount }}<span class="text-xs text-[#707E94]"> / {{ deliveryTotal }}</span></div>
          <div class="text-[10px] text-[#707E94] font-mono mt-1">待处理 {{ gw.stats?.pending ?? 0 }} · 重试 {{ gw.stats?.retry ?? 0 }}</div>
        </div>
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 text-[11px] text-[#707E94] font-mono mb-2"><AlertTriangle class="w-4 h-4 text-amber-400" /><span>死信 / 关键事件</span></div>
          <div class="text-lg font-black font-mono" :class="(gw.stats?.dead ?? 0) > 0 ? 'text-rose-400' : 'text-emerald-400'">{{ gw.stats?.dead ?? 0 }}<span class="text-xs text-[#707E94]"> / {{ gw.event_health?.critical_total ?? 0 }}</span></div>
          <div class="text-[10px] text-[#707E94] font-mono mt-1">关键未达 {{ gw.event_health?.critical_unmet ?? 0 }} · 失败 {{ gw.event_health?.critical_failed ?? 0 }}</div>
        </div>
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 text-[11px] text-[#707E94] font-mono mb-2"><Clock class="w-4 h-4 text-purple-400" /><span>调度任务</span></div>
          <div class="text-lg font-black font-mono text-white">{{ gw.scheduler?.jobs?.length ?? 0 }}</div>
          <div class="text-[10px] font-mono mt-1" :class="overdueCount > 0 ? 'text-rose-400' : 'text-emerald-400'">{{ overdueCount > 0 ? overdueCount + ' 个任务逾期!' : '无逾期任务' }}</div>
        </div>
      </div>

      <!-- Scheduler Jobs -->
      <div v-if="gw.scheduler?.jobs?.length" class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <h2 class="text-xs font-bold text-white font-mono uppercase mb-3">本地调度计划（北京时间）</h2>
        <table class="w-full text-left text-xs font-mono">
          <thead><tr class="text-[#707E94] border-b border-[#1A2232]"><th class="pb-2">任务</th><th class="pb-2">脚本</th><th class="pb-2">触发</th><th class="pb-2">最近调度</th><th class="pb-2">状态</th></tr></thead>
          <tbody class="divide-y divide-[#1A2232]/50">
            <tr v-for="j in gw.scheduler.jobs" :key="j.name">
              <td class="py-2 text-white font-bold">{{ j.name }}</td>
              <td class="py-2 text-zinc-300 text-[10px]">{{ j.script }}</td>
              <td class="py-2 text-zinc-300">{{ j.schedule }}</td>
              <td class="py-2 text-[#707E94]">{{ j.last_scheduled_at || '尚未调度' }}</td>
              <td class="py-2 font-bold" :class="j.overdue ? 'text-rose-400' : 'text-emerald-400'">{{ j.overdue ? '⚠ 逾期' : '正常' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Deliveries -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs font-bold text-white font-mono uppercase">事件投递队列 (最近 50 条)</h2>
          <button @click="load" class="flex items-center space-x-1 px-2.5 py-1 rounded bg-[#111c2a] border border-[#33445b] text-[10px] font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]"><RefreshCw class="w-3 h-3" /><span>刷新</span></button>
        </div>
        <div class="overflow-x-auto max-h-[420px] overflow-y-auto">
          <table class="w-full text-left text-xs font-mono">
            <thead class="sticky top-0 bg-[#0D121B]"><tr class="text-[#707E94] border-b border-[#1A2232]"><th class="pb-2">#</th><th class="pb-2">事件</th><th class="pb-2">通道</th><th class="pb-2">状态</th><th class="pb-2">尝试</th><th class="pb-2">时间</th><th class="pb-2 text-right">操作</th></tr></thead>
            <tbody class="divide-y divide-[#1A2232]/50">
              <tr v-for="d in gw.deliveries" :key="d.id">
                <td class="py-2 text-[#707E94]">{{ d.id }}</td>
                <td class="py-2 text-white">{{ d.event_type || d.topic || '--' }}</td>
                <td class="py-2 text-zinc-300">{{ d.channel || '--' }}</td>
                <td class="py-2 font-bold" :class="statusColor(d.status)">{{ d.status }}</td>
                <td class="py-2 text-zinc-300">{{ d.attempts ?? d.attempt_count ?? 1 }}</td>
                <td class="py-2 text-[#707E94]">{{ d.created_at || d.time || '--' }}</td>
                <td class="py-2 text-right">
                  <button v-if="d.status === 'dead'" @click="replayDelivery(d.id)" class="flex items-center space-x-1 ml-auto px-2 py-1 rounded bg-amber-600/20 border border-amber-500/30 text-[10px] font-mono text-amber-400 cursor-pointer hover:bg-amber-600/30">
                    <RotateCcw class="w-3 h-3" /><span>重放</span>
                  </button>
                </td>
              </tr>
              <tr v-if="!gw.deliveries || gw.deliveries.length === 0"><td colspan="7" class="py-6 text-center text-[#707E94]">暂无投递记录</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
