<script setup lang="ts">
import { ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import {
  LayoutGrid,
  Cpu,
  Newspaper,
  Sparkles,
  Receipt,
  RefreshCw,
  ShieldCheck,
  ExternalLink,
} from 'lucide-vue-next'

const store = useDashboardStore()
const isRotating = ref(false)

const tabs = [
  { id: 'trading', label: '实盘矩阵', icon: LayoutGrid },
  { id: 'factors', label: 'AI全景推演', icon: Cpu },
  { id: 'news', label: '全网舆情', icon: Newspaper },
  { id: 'lab', label: 'AI自进化', icon: Sparkles },
  { id: 'history', label: '交易台账', icon: Receipt },
] as const

function handleManualRefresh() {
  if (isRotating.value) return
  isRotating.value = true
  store.fetchDashboard(false).finally(() => {
    setTimeout(() => {
      isRotating.value = false
    }, 600)
  })
}
</script>

<template>
  <header class="sticky top-0 z-40 bg-[#0A0D14]/90 backdrop-blur-md border-b border-[#1A2232] px-4 py-2.5">
    <div class="max-w-[1720px] mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-3">
      <!-- Left: Brand & Network -->
      <div class="flex items-center space-x-3 shrink-0">
        <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20 ring-1 ring-white/20">
          <span class="text-white font-black text-base tracking-wider">R</span>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="font-extrabold text-sm tracking-wide text-white font-sans">
              R20 QUANTUM TRADER
            </h1>
            <span class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              v6.2.1
            </span>
            <span v-if="store.isStale" class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse">
              DEGRADED
            </span>
          </div>
          <p class="text-[11px] text-[#707E94] font-mono flex items-center gap-1.5">
            <span class="inline-block w-1.5 h-1.5 rounded-full" :class="store.isConnected ? 'bg-emerald-400' : 'bg-rose-500'"></span>
            <span>高频微积分动能 · 100% 交易所云端 OCO 全覆盖</span>
          </p>
        </div>
      </div>

      <!-- Center: 5-Tab Segmented Switcher -->
      <nav class="flex items-center bg-[#0D121B] p-1 rounded-xl border border-[#1A2232] overflow-x-auto">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="store.activeTab = tab.id as any"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer whitespace-nowrap"
          :class="store.activeTab === tab.id
            ? 'bg-gradient-to-b from-[#23304A] to-[#1C2436] text-white border border-[#3875F6] shadow-sm shadow-blue-500/30'
            : 'text-[#707E94] hover:text-white border border-transparent'"
        >
          <component :is="tab.icon" class="w-3.5 h-3.5" />
          <span>{{ tab.label }}</span>
        </button>
      </nav>

      <!-- Right: Equity summary & Action buttons -->
      <div class="flex items-center space-x-3 shrink-0 text-xs font-mono">
        <div class="hidden xl:flex items-center space-x-2 bg-[#0D121B] px-3 py-1.5 rounded-lg border border-[#1A2232]">
          <span class="text-[#707E94]">总权益:</span>
          <span class="text-white font-bold">{{ store.account ? store.account.total_eq.toFixed(2) : '--' }}</span>
          <span
            class="font-bold"
            :class="(store.account?.benchmark_net_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            ({{ (store.account?.benchmark_net_pnl ?? 0) >= 0 ? '+' : '' }}{{ store.account ? store.account.benchmark_net_pnl.toFixed(2) : '--' }}U)
          </span>
        </div>

        <a
          href="/admin"
          target="_blank"
          class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-[#0D121B] hover:bg-[#141B26] border border-[#1A2232] text-xs font-mono text-[#707E94] hover:text-white transition-colors"
        >
          <ShieldCheck class="w-3.5 h-3.5 text-blue-400" />
          <span>控制面</span>
          <ExternalLink class="w-3 h-3 text-[#707E94]" />
        </a>

        <button
          @click="handleManualRefresh"
          class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-medium shadow-md shadow-blue-500/10 transition-all cursor-pointer"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isRotating || store.isRefreshing }" />
          <span>刷新</span>
        </button>
      </div>
    </div>
  </header>
</template>
