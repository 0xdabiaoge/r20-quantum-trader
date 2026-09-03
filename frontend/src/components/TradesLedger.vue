<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Receipt, Search } from 'lucide-vue-next'

const store = useDashboardStore()
const allTrades = computed<any[]>(() => store.data?.trades || [])
const filter = ref<'all' | 'active' | 'closed'>('all')
const keyword = ref('')

const trades = computed<any[]>(() => {
  let list = allTrades.value
  if (filter.value === 'active') list = list.filter((t) => t.status === 'holding')
  else if (filter.value === 'closed') list = list.filter((t) => t.status !== 'holding')
  const kw = keyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter((t) =>
      [t.inst, t.strategy, t.side, t.exit_reason, t.status].join(' ').toLowerCase().includes(kw)
    )
  }
  return list.slice(0, 80)
})

const holdingCount = computed(() => allTrades.value.filter((t) => t.status === 'holding').length)
const closedCount = computed(() => allTrades.value.length - holdingCount.value)

function num(v: any): number {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''))
  return Number.isFinite(n) ? n : 0
}
function formatPx(val: any): string {
  if (val === undefined || val === null || val === '--' || !Number.isFinite(Number(val))) return val || '--'
  const n = Number(val)
  if (n >= 1000) return n.toFixed(2)
  if (n >= 10) return n.toFixed(3)
  return n.toFixed(4)
}
function clean(text: string, fallback: string) {
  const v = String(text || '').replace(/^[^\u4e00-\u9fa5a-zA-Z0-9]+/, '').trim()
  return v || fallback
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center space-x-3">
        <div class="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
          <Receipt class="w-5 h-5" />
        </div>
        <div>
          <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">完整成交台账与生命周期履历</h2>
          <p class="text-xs text-[#707E94] font-mono">真实撮合成交记录，扣除交易所手续费与资金费率净额</p>
        </div>
      </div>
      <div class="text-xs font-mono text-zinc-400">
        持仓 <strong class="text-blue-400">{{ holdingCount }}</strong> · 已平仓 <strong class="text-white">{{ closedCount }}</strong>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-3 flex flex-wrap items-center gap-2">
      <div class="flex rounded-lg bg-[#080B10] border border-[#1A2232] p-0.5 font-mono text-xs">
        <button @click="filter = 'all'" class="px-3 py-1 rounded-md cursor-pointer transition" :class="filter === 'all' ? 'bg-blue-600 text-white font-bold' : 'text-[#707E94] hover:text-white'">全部</button>
        <button @click="filter = 'active'" class="px-3 py-1 rounded-md cursor-pointer transition" :class="filter === 'active' ? 'bg-blue-600 text-white font-bold' : 'text-[#707E94] hover:text-white'">持仓中</button>
        <button @click="filter = 'closed'" class="px-3 py-1 rounded-md cursor-pointer transition" :class="filter === 'closed' ? 'bg-blue-600 text-white font-bold' : 'text-[#707E94] hover:text-white'">已平仓</button>
      </div>
      <div class="flex items-center space-x-1.5 flex-1 min-w-[160px] max-w-[280px] bg-[#080B10] border border-[#1A2232] rounded-lg px-2.5 py-1.5">
        <Search class="w-3.5 h-3.5 text-[#707E94] shrink-0" />
        <input v-model="keyword" placeholder="搜索币种 / 策略 / 平仓原因..." class="flex-1 bg-transparent text-xs font-mono text-white outline-none min-w-0" />
      </div>
    </div>

    <!-- Trades Table -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
      <div v-if="trades.length === 0" class="py-12 text-center text-xs font-mono text-[#707E94]">
        无匹配交易台账记录
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs font-mono">
          <thead>
            <tr class="text-[#707E94] border-b border-[#1A2232]">
              <th class="pb-2 pr-2">标的/方向</th>
              <th class="pb-2 pr-2">策略</th>
              <th class="pb-2 pr-2">保证金</th>
              <th class="pb-2 pr-2">开仓价 / 时间</th>
              <th class="pb-2 pr-2">平仓价 / 时间</th>
              <th class="pb-2 pr-2 text-right">净盈亏 / ROI</th>
              <th class="pb-2 pr-2 text-center">时长</th>
              <th class="pb-2">状态 / 平仓原因</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#1A2232]/50">
            <tr v-for="(t, idx) in trades" :key="t.id || idx" class="hover:bg-[#121824]/50">
              <td class="py-2.5 pr-2 whitespace-nowrap">
                <span class="font-bold text-white">{{ t.inst }}</span>
                <span class="ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold border" :class="t.side === '多' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border-rose-500/30'">{{ t.side }} {{ t.lever || '3x' }}</span>
              </td>
              <td class="py-2.5 pr-2">
                <span class="px-2 py-0.5 rounded bg-[#141B26] text-[#9db0c6] border border-[#1A2232] text-[11px] whitespace-nowrap">{{ clean(t.strategy, '观望') }}</span>
              </td>
              <td class="py-2.5 pr-2 text-white font-bold whitespace-nowrap">{{ t.margin ? num(t.margin).toFixed(1) + ' U' : '--' }}</td>
              <td class="py-2.5 pr-2 whitespace-nowrap">
                <span class="text-zinc-300">{{ formatPx(t.open_px) }}</span>
                <span class="text-[10px] text-[#707E94] ml-1">({{ (t.open_time || '--').substring(5, 19) }})</span>
              </td>
              <td class="py-2.5 pr-2 whitespace-nowrap">
                <span :class="t.status === 'holding' ? 'text-blue-400 font-bold' : 'text-white'">{{ t.status === 'holding' ? '盯盘中' : formatPx(t.close_px) }}</span>
                <span class="text-[10px] text-[#707E94] ml-1">({{ t.status === 'holding' ? '--' : (t.close_time || '--').substring(5, 19) }})</span>
              </td>
              <td class="py-2.5 pr-2 text-right whitespace-nowrap">
                <span class="font-bold" :class="num(t.pnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ num(t.pnl) >= 0 ? '+' : '' }}{{ num(t.pnl).toFixed(2) }} U</span>
                <span class="text-[10px] ml-1" :class="num(t.roi_pct) >= 0 ? 'text-emerald-400' : 'text-rose-400'">({{ num(t.roi_pct) >= 0 ? '+' : '' }}{{ num(t.roi_pct).toFixed(1) }}%{{ t.status === 'holding' ? ' 浮' : '' }})</span>
              </td>
              <td class="py-2.5 pr-2 text-center text-[#707E94] whitespace-nowrap">{{ t.duration || '--' }}</td>
              <td class="py-2.5">
                <span class="px-2 py-0.5 rounded text-[10px] border whitespace-nowrap" :class="t.status === 'holding' ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' : num(t.pnl) >= 0 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border-rose-500/30'">
                  {{ clean(t.exit_reason, t.status === 'holding' ? '实时监控中' : '平仓完成') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
