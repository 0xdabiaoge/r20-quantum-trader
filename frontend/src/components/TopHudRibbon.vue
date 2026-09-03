<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Wallet, TrendingUp, TrendingDown, Calendar, ShieldCheck, Activity } from 'lucide-vue-next'

const store = useDashboardStore()
const account = computed(() => store.data?.account || {})
const today = computed(() => store.data?.today_stats || {})
const perf = computed(() => store.data?.performance || {})

const totalEq = computed(() => Number(account.value.total_eq || 0).toFixed(2))
const availEq = computed(() => Number(account.value.avail_eq || 0).toFixed(2))
const marginUsage = computed(() => Number(account.value.margin_usage_pct || 0).toFixed(1))
const posUpl = computed(() => Number(account.value.pos_upl_total || account.value.upl || 0).toFixed(2))

const benchmarkNetPnl = computed(() => Number(account.value.cum_net_pnl || 0).toFixed(2))
const benchmarkRoi = computed(() => Number(account.value.cum_roi_pct || 0).toFixed(2))
const initialCap = computed(() => Number(account.value.initial_capital || 0).toFixed(2))

const todayNet = computed(() => Number(today.value.total_pnl ?? today.value.net_realized ?? 0).toFixed(2))
const todayWinrate = computed(() => Number(today.value.win_rate || 0).toFixed(1))
const todayTrades = computed(() => (today.value.win_trades || 0) + (today.value.loss_trades || 0))
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
          <span>浮动持仓: <strong :class="Number(posUpl) >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ Number(posUpl) >= 0 ? '+' : '' }}{{ posUpl }} U</strong></span>
          <span>真实手续费扣除: <strong class="text-zinc-300">100%</strong></span>
        </div>
      </div>
    </div>

    <!-- Card 3: 今日净盈亏与战报 (UTC+8) -->
    <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-col justify-between shadow-lg">
      <div class="flex items-center justify-between text-[#707E94] text-xs font-mono mb-2">
        <div class="flex items-center space-x-1.5">
          <Calendar class="w-4 h-4 text-purple-400" />
          <span>今日战报 (UTC+8)</span>
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

    <!-- Card 4: 机构级执行风控防御 -->
    <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-col justify-between shadow-lg">
      <div class="flex items-center justify-between text-[#707E94] text-xs font-mono mb-2">
        <div class="flex items-center space-x-1.5">
          <ShieldCheck class="w-4 h-4 text-emerald-400" />
          <span>机构级风控与云端保护</span>
        </div>
        <span class="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">FAIL-CLOSED</span>
      </div>
      <div>
        <div class="text-base sm:text-lg font-bold text-white font-mono flex items-center space-x-2">
          <span class="inline-block w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>100% 交易所云端 OCO 覆盖</span>
        </div>
        <div class="flex items-center justify-between text-[11px] font-mono mt-2 pt-2 border-t border-[#1A2232]/80 text-[#707E94]">
          <span>单向最大持仓: <strong class="text-zinc-200">6 笔 (当前 {{ store.positions.length }}/6)</strong></span>
          <span>时间止损: <strong class="text-zinc-300">8小时横盘强制平仓</strong></span>
        </div>
      </div>
    </div>
  </div>
</template>
