<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Wallet, TrendingUp, TrendingDown, Calendar, Activity, ShieldCheck } from 'lucide-vue-next'

const store = useDashboardStore()
const account = computed(() => store.data?.account || {})
const today = computed(() => store.data?.today_stats || {})
const perf = computed(() => store.data?.performance || {})

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
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
    <!-- Card 1: 官方账户总权益 -->
    <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-col justify-between shadow-lg">
      <div class="flex items-center justify-between text-[#707E94] text-xs font-mono mb-2">
        <div class="flex items-center space-x-1.5">
          <Wallet class="w-4 h-4 text-blue-400" />
          <span>官方账户总权益</span>
        </div>
      </div>
      <div>
        <div class="text-2xl sm:text-3xl font-black text-white font-mono tracking-tight">
          ${{ totalEq }}
          <span class="text-xs text-[#707E94] font-normal">USDT</span>
        </div>
        <div class="flex items-center justify-between text-[11px] font-mono mt-2 pt-2 border-t border-[#1A2232]/80 text-[#707E94]">
          <span>可用: <strong class="text-zinc-200">${{ availEq }}</strong></span>
          <span>保证金占用: <strong :class="Number(marginUsage) > 50 ? 'text-amber-400' : 'text-zinc-200'">{{ marginUsage }}%</strong></span>
        </div>
      </div>
    </div>

    <!-- Card 2: 基准净盈亏水线 (vs 初始 4061.04) -->
    <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-col justify-between shadow-lg">
      <div class="flex items-center justify-between text-[#707E94] text-xs font-mono mb-2">
        <div class="flex items-center space-x-1.5">
          <TrendingUp class="w-4 h-4 text-emerald-400" />
          <span>基准净盈亏水线</span>
        </div>
        <span class="text-[10px] text-[#707E94] font-mono">基准 ${{ initialCap }}</span>
      </div>
      <div>
        <div
          class="text-2xl sm:text-3xl font-black font-mono tracking-tight"
          :class="Number(benchmarkNetPnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
        >
          {{ Number(benchmarkNetPnl) >= 0 ? '+' : '' }}{{ benchmarkNetPnl }}
          <span class="text-xs font-semibold">({{ Number(benchmarkRoi) >= 0 ? '+' : '' }}{{ benchmarkRoi }}%)</span>
        </div>
        <div class="flex items-center justify-between text-[11px] font-mono mt-2 pt-2 border-t border-[#1A2232]/80 text-[#707E94]">
          <span>已结净额: <strong :class="Number(cumRealizedPnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ Number(cumRealizedPnl) >= 0 ? '+' : '' }}{{ cumRealizedPnl }} U</strong></span>
          <span>真实手续费扣除: <strong class="text-zinc-300">100%</strong></span>
        </div>
      </div>
    </div>

    <!-- Card 3: 今日已结净盈亏 (UTC+8) -->
    <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-col justify-between shadow-lg">
      <div class="flex items-center justify-between text-[#707E94] text-xs font-mono mb-2">
        <div class="flex items-center space-x-1.5">
          <Calendar class="w-4 h-4 text-purple-400" />
          <span>今日已结净盈亏 (UTC+8)</span>
        </div>
        <span class="text-[10px] font-mono" :class="Number(todayNet) >= 0 ? 'text-emerald-400' : 'text-rose-400'">
          胜率 {{ todayWinrate }}%
        </span>
      </div>
      <div>
        <div
          class="text-2xl sm:text-3xl font-black font-mono tracking-tight"
          :class="Number(todayNet) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
        >
          {{ Number(todayNet) >= 0 ? '+' : '' }}{{ todayNet }}
          <span class="text-xs text-[#707E94] font-normal">USDT</span>
        </div>
        <div class="flex items-center justify-between text-[11px] font-mono mt-2 pt-2 border-t border-[#1A2232]/80 text-[#707E94]">
          <span>已结交易: <strong class="text-zinc-200">{{ todayTrades }} 笔 ({{ today.win_trades || 0 }}胜/{{ today.loss_trades || 0 }}负)</strong></span>
          <span>手续费: <strong class="text-zinc-300">{{ today.fees_paid || 0 }} U</strong></span>
        </div>
      </div>
    </div>

    <!-- Card 4: 当前持仓净盈亏 -->
    <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-col justify-between shadow-lg">
      <div class="flex items-center justify-between text-[#707E94] text-xs font-mono mb-2">
        <div class="flex items-center space-x-1.5">
          <Activity class="w-4 h-4 text-cyan-400" />
          <span>当前持仓净盈亏</span>
        </div>
        <span class="text-[10px] font-mono" :class="store.positions.length > 0 ? 'text-cyan-400' : 'text-[#707E94]'">
          持仓 {{ store.positions.length }}/6 (多{{ longCount }}/空{{ shortCount }})
        </span>
      </div>
      <div>
        <div
          class="text-2xl sm:text-3xl font-black font-mono tracking-tight"
          :class="posUplNum >= 0 ? (posUplNum > 0 ? 'text-emerald-400' : 'text-zinc-200') : 'text-rose-400'"
        >
          {{ posUplNum > 0 ? '+' : '' }}{{ posUplStr }}
          <span class="text-xs font-normal text-[#707E94]">USDT</span>
          <span v-if="store.positions.length > 0" class="text-xs font-semibold ml-1.5" :class="posUplNum >= 0 ? 'text-emerald-400' : 'text-rose-400'">
            ({{ Number(posUplRatio) > 0 ? '+' : '' }}{{ posUplRatio }}%)
          </span>
        </div>
        <div class="flex items-center justify-between text-[11px] font-mono mt-2 pt-2 border-t border-[#1A2232]/80 text-[#707E94]">
          <span>占用保证金: <strong class="text-zinc-200">${{ totalPosMargin }} U</strong></span>
          <span v-if="store.positions.length > 0">
            云端防线:
            <strong :class="allProtected ? 'text-emerald-400' : 'text-amber-400'">
              {{ allProtected ? '100% OCO' : '待复核' }}
            </strong>
          </span>
          <span v-else>
            状态: <strong class="text-zinc-400">空仓待机中</strong>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
