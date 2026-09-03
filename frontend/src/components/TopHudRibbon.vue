<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Wallet, TrendingUp, Calendar, Activity } from 'lucide-vue-next'

const store = useDashboardStore()
const account = computed(() => store.data?.account || {})
const today = computed(() => store.data?.today_stats || {})

const totalEq = computed(() => Number(account.value.total_eq || 0).toFixed(2))
const availEq = computed(() => Number(account.value.avail_eq || 0).toFixed(2))
const marginUsage = computed(() => Number(account.value.margin_usage_pct || 0).toFixed(1))

const benchmarkNetPnl = computed(() => Number(account.value.cum_net_pnl || 0).toFixed(2))
const benchmarkRoi = computed(() => Number(account.value.cum_roi_pct || 0).toFixed(2))
const initialCap = computed(() => Number(account.value.initial_capital || 0).toFixed(2))
const cumRealizedPnl = computed(() => Number(account.value.cum_realized_pnl || 0).toFixed(2))

const todayNet = computed(() => Number(today.value.net_realized ?? today.value.total_pnl ?? 0).toFixed(2))
const todayWinrate = computed(() => Number(today.value.win_rate || 0).toFixed(1))
const todayTrades = computed(() => (today.value.win_trades || 0) + (today.value.loss_trades || 0))

// 当前持仓浮动盈亏与风控统计
const posUplNum = computed(() => Number(account.value.pos_upl_total ?? account.value.upl ?? 0))
const posUplStr = computed(() => posUplNum.value.toFixed(2))

const longCount = computed(() => store.positions.filter((p) => p.side === 'long').length)
const shortCount = computed(() => store.positions.filter((p) => p.side === 'short').length)

const totalPosMargin = computed(() => {
  const sum = store.positions.reduce((acc, p) => acc + Number((p as any).margin_usdt ?? p.margin ?? 0), 0)
  return sum.toFixed(2)
})

const posUplRatio = computed(() => {
  const margin = Number(totalPosMargin.value)
  if (margin > 0) {
    return (posUplNum.value / margin * 100).toFixed(2)
  }
  return '0.00'
})

const allProtected = computed(() =>
  store.positions.length > 0 &&
  store.positions.every((p) => p.protectionStatus === 'fully_protected' || Number(p.protectionCoveragePct || 0) >= 100)
)
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3.5 sm:gap-4.5">
    <!-- Card 1: 官方账户总权益 -->
    <div class="quantum-card p-4 sm:p-5 flex flex-col justify-between group">
      <!-- Top Accent Line -->
      <div class="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-cyan-400 opacity-80 group-hover:opacity-100 transition-opacity"></div>

      <div>
        <div class="flex items-center justify-between text-slate-400 text-xs font-mono mb-2.5">
          <div class="flex items-center space-x-2">
            <div class="w-6 h-6 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Wallet class="w-3.5 h-3.5" />
            </div>
            <span class="font-bold text-slate-300">官方账户总权益</span>
          </div>
          <span class="text-[10px] font-mono px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20 font-bold">
            OKX V5 DIRECT
          </span>
        </div>

        <div class="text-2xl sm:text-3xl 2xl:text-4xl font-black text-white font-mono tracking-tight num-tabular mt-1 flex items-baseline space-x-1.5">
          <span>${{ totalEq }}</span>
          <span class="text-xs text-slate-400 font-medium tracking-normal">USDT</span>
        </div>
      </div>

      <div class="flex items-center justify-between text-[11px] font-mono mt-3.5 pt-2.5 border-t border-[#182644] text-slate-400">
        <span>可用: <strong class="text-white">${{ availEq }}</strong></span>
        <span>保证金占用: <strong :class="Number(marginUsage) > 50 ? 'text-amber-400 font-bold' : 'text-slate-300'">{{ marginUsage }}%</strong></span>
      </div>
    </div>

    <!-- Card 2: 基准净盈亏水线 (vs 初始 4061.04) -->
    <div class="quantum-card p-4 sm:p-5 flex flex-col justify-between group">
      <!-- Top Accent Line -->
      <div class="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-emerald-500 via-teal-400 to-cyan-400 opacity-80 group-hover:opacity-100 transition-opacity"></div>

      <div>
        <div class="flex items-center justify-between text-slate-400 text-xs font-mono mb-2.5">
          <div class="flex items-center space-x-2">
            <div class="w-6 h-6 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <TrendingUp class="w-3.5 h-3.5" />
            </div>
            <span class="font-bold text-slate-300">基准净盈亏水线</span>
          </div>
          <span class="text-[10px] text-slate-400 font-mono">基准 ${{ initialCap }}</span>
        </div>

        <div
          class="text-2xl sm:text-3xl 2xl:text-4xl font-black font-mono tracking-tight num-tabular mt-1 flex items-baseline space-x-1.5"
          :class="Number(benchmarkNetPnl) >= 0 ? 'text-emerald-400 text-glow-emerald' : 'text-rose-400 text-glow-rose'"
        >
          <span>{{ Number(benchmarkNetPnl) >= 0 ? '+' : '' }}{{ benchmarkNetPnl }}</span>
          <span class="text-xs font-bold px-1.5 py-0.5 rounded-md border tracking-normal ml-1" :class="Number(benchmarkRoi) >= 0 ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-rose-500/15 text-rose-300 border-rose-500/30'">
            {{ Number(benchmarkRoi) >= 0 ? '+' : '' }}{{ benchmarkRoi }}%
          </span>
        </div>
      </div>

      <div class="flex items-center justify-between text-[11px] font-mono mt-3.5 pt-2.5 border-t border-[#182644] text-slate-400">
        <span>已结净额: <strong :class="Number(cumRealizedPnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ Number(cumRealizedPnl) >= 0 ? '+' : '' }}{{ cumRealizedPnl }} U</strong></span>
        <span>真实扣费: <strong class="text-slate-300">100%</strong></span>
      </div>
    </div>

    <!-- Card 3: 今日已结净盈亏 (UTC+8) -->
    <div class="quantum-card p-4 sm:p-5 flex flex-col justify-between group">
      <!-- Top Accent Line -->
      <div class="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-purple-500 via-indigo-500 to-blue-400 opacity-80 group-hover:opacity-100 transition-opacity"></div>

      <div>
        <div class="flex items-center justify-between text-slate-400 text-xs font-mono mb-2.5">
          <div class="flex items-center space-x-2">
            <div class="w-6 h-6 rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Calendar class="w-3.5 h-3.5" />
            </div>
            <span class="font-bold text-slate-300">今日已结净盈亏 (UTC+8)</span>
          </div>
          <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border" :class="Number(todayNet) >= 0 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'">
            胜率 {{ todayWinrate }}%
          </span>
        </div>

        <div
          class="text-2xl sm:text-3xl 2xl:text-4xl font-black font-mono tracking-tight num-tabular mt-1 flex items-baseline space-x-1.5"
          :class="Number(todayNet) >= 0 ? 'text-emerald-400 text-glow-emerald' : 'text-rose-400 text-glow-rose'"
        >
          <span>{{ Number(todayNet) >= 0 ? '+' : '' }}{{ todayNet }}</span>
          <span class="text-xs text-slate-400 font-medium tracking-normal">USDT</span>
        </div>
      </div>

      <div class="flex items-center justify-between text-[11px] font-mono mt-3.5 pt-2.5 border-t border-[#182644] text-slate-400">
        <span>已结: <strong class="text-white">{{ todayTrades }} 笔 ({{ today.win_trades || 0 }}胜/{{ today.loss_trades || 0 }}负)</strong></span>
        <span>手续费: <strong class="text-slate-300">{{ today.fees_paid || 0 }} U</strong></span>
      </div>
    </div>

    <!-- Card 4: 当前持仓净盈亏 -->
    <div class="quantum-card p-4 sm:p-5 flex flex-col justify-between group">
      <!-- Top Accent Line -->
      <div class="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-500 opacity-80 group-hover:opacity-100 transition-opacity"></div>

      <div>
        <div class="flex items-center justify-between text-slate-400 text-xs font-mono mb-2.5">
          <div class="flex items-center space-x-2">
            <div class="w-6 h-6 rounded-lg bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Activity class="w-3.5 h-3.5" />
            </div>
            <span class="font-bold text-slate-300">当前持仓净盈亏</span>
          </div>
          <span class="text-[10px] font-mono px-2 py-0.5 rounded-md border font-bold" :class="store.positions.length > 0 ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/25' : 'bg-slate-800 text-slate-400 border-slate-700'">
            持仓 {{ store.positions.length }}/6 (多{{ longCount }}/空{{ shortCount }})
          </span>
        </div>

        <div
          class="text-2xl sm:text-3xl 2xl:text-4xl font-black font-mono tracking-tight num-tabular mt-1 flex items-baseline space-x-1.5"
          :class="posUplNum >= 0 ? (posUplNum > 0 ? 'text-emerald-400 text-glow-emerald' : 'text-slate-200') : 'text-rose-400 text-glow-rose'"
        >
          <span>{{ posUplNum > 0 ? '+' : '' }}{{ posUplStr }}</span>
          <span class="text-xs text-slate-400 font-medium tracking-normal">USDT</span>
          <span v-if="store.positions.length > 0" class="text-xs font-bold px-1.5 py-0.5 rounded-md border tracking-normal ml-1" :class="posUplNum >= 0 ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-rose-500/15 text-rose-300 border-rose-500/30'">
            {{ Number(posUplRatio) > 0 ? '+' : '' }}{{ posUplRatio }}%
          </span>
        </div>
      </div>

      <div class="flex items-center justify-between text-[11px] font-mono mt-3.5 pt-2.5 border-t border-[#182644] text-slate-400">
        <span>占用保证金: <strong class="text-white">${{ totalPosMargin }} U</strong></span>
        <span v-if="store.positions.length > 0">
          云端防线:
          <strong :class="allProtected ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'">
            {{ allProtected ? '100% OCO' : '待复核' }}
          </strong>
        </span>
        <span v-else>
          状态: <strong class="text-slate-400 font-medium">空仓待机中</strong>
        </span>
      </div>
    </div>
  </div>
</template>
