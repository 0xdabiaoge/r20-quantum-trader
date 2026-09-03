<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import HeaderBar from '../components/HeaderBar.vue'
import TopHudRibbon from '../components/TopHudRibbon.vue'
import InstrumentMatrix from '../components/InstrumentMatrix.vue'
import PositionList from '../components/PositionList.vue'
import PendingOrders from '../components/PendingOrders.vue'
import LedgerLogs from '../components/LedgerLogs.vue'
import NewsIntelligence from '../components/NewsIntelligence.vue'
import SelfEvolutionLab from '../components/SelfEvolutionLab.vue'
import TradesLedger from '../components/TradesLedger.vue'
import AiBrainHistory from '../components/AiBrainHistory.vue'
import FloatingActions from '../components/FloatingActions.vue'
import { LayoutGrid, Cpu, Newspaper, Sparkles, Receipt } from 'lucide-vue-next'

const store = useDashboardStore()

onMounted(() => {
  store.startPolling(3000)
})

onUnmounted(() => {
  store.stopPolling()
})
</script>

<template>
  <div class="min-h-screen bg-[#080B10] text-[#F3F4F6] flex flex-col selection:bg-blue-500 selection:text-white">
    <!-- Top Nav Ribbon with 5 Tabs (fixed: never scrolls away) -->
    <HeaderBar />

    <!-- Spacer for fixed header (slim single-row bar) -->
    <div class="h-[58px] shrink-0"></div>

    <!-- Dynamic Main Content Based on Active Tab -->
    <main class="flex-1 max-w-[2160px] w-full mx-auto px-3 sm:px-6 2xl:px-8 pb-24 sm:pb-6 space-y-4">
      <!-- TAB 1: 实盘矩阵 (TRADING) — home: HUD cards + positions + maker orders + 6-asset matrix -->
      <div v-show="store.activeTab === 'trading'" class="space-y-4">
        <!-- 1. Top HUD 4-Card Ribbon (Equity, Benchmark PnL, Today PnL, Cloud OCO) -->
        <TopHudRibbon />
        <!-- 2. Full-Width Current Positions & Risk Management (spacious layout) -->
        <PositionList />
        <!-- 3. In-flight Maker Orders Monitor (responsive & clean) -->
        <PendingOrders />
        <!-- 4. 6-Asset Grid with Calculus Dynamics & Drawer -->
        <InstrumentMatrix />
      </div>

      <!-- TAB 2: AI全景推演 (FACTORS) — Dedicated AI Decision & Evolution Workspace -->
      <div v-show="store.activeTab === 'factors'" class="space-y-4">
        <AiBrainHistory />
      </div>

      <!-- TAB 3: 全网舆情 (NEWS) -->
      <div v-show="store.activeTab === 'news'" class="space-y-4">
        <NewsIntelligence />
      </div>

      <!-- TAB 4: 自进化实验室 (LAB) -->
      <div v-show="store.activeTab === 'lab'" class="space-y-4">
        <SelfEvolutionLab />
      </div>

      <!-- TAB 5: 交易台账与生命周期 (HISTORY) — the only home of the patrol log stream -->
      <div v-show="store.activeTab === 'history'" class="space-y-4">
        <TradesLedger />
        <LedgerLogs />
      </div>
    </main>

    <!-- Global Cyber Footer -->
    <footer class="border-t border-[#1A2232] bg-[#0A0D14] py-3 text-center text-xs font-mono text-[#707E94]">
      <div class="flex items-center justify-center space-x-2">
        <button
          @click="store.showAboutModal = true"
          class="hover:text-blue-400 transition-colors cursor-pointer"
          title="点击查看开源仓库与项目信息"
        >
          R20 QUANTUM TRADER v6.3.0
        </button>
        <span>•</span>
        <span>VUE 3 + VITE + TAILWIND CSS</span>
        <span>•</span>
        <a
          href="https://github.com/555cute/r20-quantum-trader"
          target="_blank"
          rel="noopener noreferrer"
          class="hover:text-blue-400 transition-colors"
        >
          GitHub
        </a>
      </div>
    </footer>

    <!-- 🪟 Mobile Bottom Navigation Bar (md:hidden) -->
    <nav class="md:hidden fixed inset-x-0 bottom-0 z-50 bg-[#080B10]/95 backdrop-blur-xl border-t border-[#1A2232] px-2 py-1.5">
      <div class="max-w-md mx-auto flex items-center justify-around font-mono">
        <button
          @click="store.activeTab = 'trading'"
          class="flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer"
          :class="store.activeTab === 'trading' ? 'text-blue-400' : 'text-[#707E94] hover:text-white'"
        >
          <LayoutGrid class="w-4 h-4 mb-0.5" />
          <span class="text-[10px] font-bold">实盘</span>
        </button>
        <button
          @click="store.activeTab = 'factors'"
          class="flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer"
          :class="store.activeTab === 'factors' ? 'text-blue-400' : 'text-[#707E94] hover:text-white'"
        >
          <Cpu class="w-4 h-4 mb-0.5" />
          <span class="text-[10px] font-bold">AI推演</span>
        </button>
        <button
          @click="store.activeTab = 'news'"
          class="flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer"
          :class="store.activeTab === 'news' ? 'text-blue-400' : 'text-[#707E94] hover:text-white'"
        >
          <Newspaper class="w-4 h-4 mb-0.5" />
          <span class="text-[10px] font-bold">舆情</span>
        </button>
        <button
          @click="store.activeTab = 'lab'"
          class="flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer"
          :class="store.activeTab === 'lab' ? 'text-blue-400' : 'text-[#707E94] hover:text-white'"
        >
          <Sparkles class="w-4 h-4 mb-0.5" />
          <span class="text-[10px] font-bold">自进化</span>
        </button>
        <button
          @click="store.activeTab = 'history'"
          class="flex flex-col items-center justify-center flex-1 py-1 transition cursor-pointer"
          :class="store.activeTab === 'history' ? 'text-blue-400' : 'text-[#707E94] hover:text-white'"
        >
          <Receipt class="w-4 h-4 mb-0.5" />
          <span class="text-[10px] font-bold">台账</span>
        </button>
      </div>
    </nav>

    <!-- ⚡ Global Floating Actions: Refresh + Realtime Prompt -->
    <FloatingActions />
  </div>
</template>
