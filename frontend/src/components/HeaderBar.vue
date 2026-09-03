<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import {
  LayoutGrid,
  Cpu,
  Newspaper,
  Sparkles,
  Receipt,
  ShieldCheck,
  ExternalLink,
} from 'lucide-vue-next'

const store = useDashboardStore()

// Null-safe numeric accessors: /api/all only exposes cum_net_pnl for benchmark PnL.
const totalEq = computed(() => Number(store.account?.total_eq ?? 0).toFixed(2))
const benchmarkNetPnl = computed(() => Number(store.account?.cum_net_pnl ?? 0))

const tabs = [
  { id: 'trading', label: '实盘矩阵', icon: LayoutGrid },
  { id: 'factors', label: 'AI全景推演', icon: Cpu },
  { id: 'news', label: '全网舆情', icon: Newspaper },
  { id: 'lab', label: 'AI自进化', icon: Sparkles },
  { id: 'history', label: '交易台账', icon: Receipt },
] as const
</script>

<template>
  <header class="fixed top-0 left-0 right-0 z-40 bg-[#0A0D14]/95 backdrop-blur-md border-b border-[#1A2232] px-3 sm:px-4 py-1.5">
    <div class="max-w-[1720px] mx-auto flex items-center justify-between gap-2 sm:gap-4">
      <!-- Left: Brand & Network -->
      <div class="flex items-center space-x-2.5 shrink-0">
        <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20 ring-1 ring-white/20">
          <span class="text-white font-black text-sm tracking-wider">R</span>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="font-extrabold text-xs sm:text-sm tracking-wide text-white font-sans">
              R20 QUANTUM TRADER
            </h1>
            <span class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              v6.2.1
            </span>
            <span v-if="store.isStale" class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse">
              DEGRADED
            </span>
          </div>
          <p class="hidden sm:flex text-[10px] text-[#707E94] font-mono items-center gap-1.5">
            <span class="inline-block w-1.5 h-1.5 rounded-full" :class="store.isConnected ? 'bg-emerald-400' : 'bg-rose-500'"></span>
            <span>高频微积分动能 · 100% 交易所云端 OCO 全覆盖</span>
          </p>
        </div>
      </div>

      <!-- Center: 5-Tab Segmented Switcher (desktop only; Android has the bottom nav) -->
      <nav class="hidden md:flex items-center bg-[#0D121B] p-1 rounded-xl border border-[#1A2232] overflow-x-auto min-w-0 shrink">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="store.activeTab = tab.id as any"
          class="flex items-center space-x-1 sm:space-x-1.5 px-2 sm:px-3 py-1 sm:py-1.5 rounded-md sm:rounded-lg text-[11px] sm:text-xs font-mono font-bold transition-all cursor-pointer whitespace-nowrap"
          :class="store.activeTab === tab.id
            ? 'bg-gradient-to-b from-[#23304A] to-[#1C2436] text-white border border-[#3875F6] shadow-sm shadow-blue-500/30'
            : 'text-[#707E94] hover:text-white border border-transparent'"
        >
          <component :is="tab.icon" class="w-3 h-3 sm:w-3.5 sm:h-3.5" />
          <span>{{ tab.label }}</span>
        </button>
      </nav>

      <!-- Right: Equity summary & Action buttons -->
      <div class="flex items-center space-x-3 shrink-0 text-xs font-mono">
        <div class="hidden xl:flex items-center space-x-2 bg-[#0D121B] px-3 py-1.5 rounded-lg border border-[#1A2232]">
          <span class="text-[#707E94]">总权益:</span>
          <span class="text-white font-bold">{{ totalEq }}</span>
          <span
            class="font-bold"
            :class="benchmarkNetPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            ({{ benchmarkNetPnl >= 0 ? '+' : '' }}{{ benchmarkNetPnl.toFixed(2) }}U)
          </span>
        </div>

        <a
          href="/admin"
          target="_blank"
          class="flex items-center space-x-1 px-2.5 sm:px-3 py-1 rounded-lg bg-[#0D121B] hover:bg-[#141B26] border border-[#1A2232] text-xs font-mono text-[#707E94] hover:text-white transition-colors"
        >
          <ShieldCheck class="w-3.5 h-3.5 text-blue-400" />
          <span>控制面</span>
          <ExternalLink class="w-3 h-3 text-[#707E94]" />
        </a>
      </div>
    </div>
  </header>
</template>
