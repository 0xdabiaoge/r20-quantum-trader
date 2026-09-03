<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import AboutModal from './AboutModal.vue'
import {
  LayoutGrid,
  Cpu,
  Newspaper,
  Sparkles,
  Receipt,
  ShieldCheck,
  ExternalLink,
  BookOpen,
} from 'lucide-vue-next'

const store = useDashboardStore()

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
  <header class="fixed top-0 left-0 right-0 z-40 bg-[#060B18]/90 backdrop-blur-xl border-b border-[#162444] px-4 sm:px-6 h-[62px] flex items-center shadow-lg shadow-black/40">
    <div class="max-w-[2160px] w-full mx-auto flex items-center justify-between gap-3 sm:gap-6">
      <!-- Left: Brand Logo & System Live Status -->
      <div class="flex items-center space-x-3 shrink-0">
        <div class="relative flex items-center justify-center">
          <div class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/25 ring-1 ring-white/20">
            <span class="text-white font-black text-base sm:text-lg tracking-wider font-mono">R</span>
          </div>
          <span class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-[#060B18]" :class="store.isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'"></span>
        </div>

        <div>
          <div class="flex items-center space-x-2">
            <h1 class="font-black text-sm sm:text-base tracking-wider text-white font-mono bg-gradient-to-r from-white via-slate-200 to-blue-200 bg-clip-text text-transparent">
              R20 QUANTUM
            </h1>
            <button
              @click="store.showAboutModal = true"
              class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30 hover:bg-blue-500/25 hover:border-blue-400 transition-all cursor-pointer shadow-xs"
              title="点击查看项目架构、交流群与开源信息"
            >
              v6.5.1
            </button>
            <span v-if="store.isStale" class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 animate-pulse">
              DEGRADED
            </span>
          </div>
          <p class="hidden sm:flex text-[11px] text-slate-400 font-mono items-center gap-1.5 leading-none mt-0.5">
            <span class="text-cyan-400 font-bold">高频因果动力学</span>
            <span class="text-slate-600">•</span>
            <span>100% 交易所云端 OCO 全覆盖</span>
          </p>
        </div>
      </div>

      <!-- Center: 5-Tab Segmented Navigation (Desktop) -->
      <nav class="hidden md:flex items-center bg-[#0A1124] p-1.5 rounded-2xl border border-[#1B2A4A] shadow-inner shrink-0">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="store.activeTab = tab.id as any"
          class="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-mono font-bold transition-all duration-200 cursor-pointer whitespace-nowrap relative"
          :class="store.activeTab === tab.id
            ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md shadow-blue-600/30 border border-blue-400/40'
            : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent'"
        >
          <component :is="tab.icon" class="w-3.5 h-3.5" :class="store.activeTab === tab.id ? 'text-cyan-200' : 'text-slate-400'" />
          <span>{{ tab.label }}</span>
        </button>
      </nav>

      <!-- Right: Asset Pill & Links -->
      <div class="flex items-center space-x-2.5 sm:space-x-3 shrink-0 text-xs font-mono">
        <!-- Live Equity Pill -->
        <div class="hidden xl:flex items-center space-x-2 bg-[#0A1124] px-3.5 py-1.5 rounded-xl border border-[#1E2D4A] shadow-sm">
          <span class="text-slate-400 font-medium">总权益:</span>
          <span class="text-white font-bold text-sm tracking-tight font-mono">${{ totalEq }}</span>
          <span
            class="font-bold text-xs"
            :class="benchmarkNetPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            {{ benchmarkNetPnl >= 0 ? '+' : '' }}{{ benchmarkNetPnl.toFixed(2) }}U
          </span>
        </div>

        <!-- Documentation Link -->
        <a
          href="/docs"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#0A1124] hover:bg-[#121E3E] border border-[#1E2D4A] hover:border-cyan-500/50 text-slate-300 hover:text-white transition-all shadow-xs"
          title="系统架构与使用文档"
        >
          <BookOpen class="w-3.5 h-3.5 text-cyan-400" />
          <span class="hidden sm:inline font-bold">文档</span>
        </a>

        <!-- Admin Control Plane Link -->
        <a
          href="/admin"
          target="_blank"
          class="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-[#0E172E] to-[#121E3E] hover:from-[#142244] hover:to-[#1A2C5A] border border-[#233860] hover:border-blue-400/60 text-white font-bold transition-all shadow-sm group"
        >
          <ShieldCheck class="w-3.5 h-3.5 text-blue-400 group-hover:text-blue-300 transition-colors" />
          <span>控制面</span>
          <ExternalLink class="w-3 h-3 text-slate-400 group-hover:text-white transition-colors" />
        </a>
      </div>
    </div>

    <!-- About Modal -->
    <AboutModal
      :visible="store.showAboutModal"
      @close="store.showAboutModal = false"
    />
  </header>
</template>
