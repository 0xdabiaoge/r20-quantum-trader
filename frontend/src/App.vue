<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from './stores/dashboard'
import HeaderBar from './components/HeaderBar.vue'
import InstrumentMatrix from './components/InstrumentMatrix.vue'
import PositionList from './components/PositionList.vue'
import PendingOrders from './components/PendingOrders.vue'
import LedgerLogs from './components/LedgerLogs.vue'
import NewsIntelligence from './components/NewsIntelligence.vue'
import SelfEvolutionLab from './components/SelfEvolutionLab.vue'
import TradesLedger from './components/TradesLedger.vue'

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
    <!-- Top Nav Ribbon with 5 Tabs -->
    <HeaderBar />

    <!-- Dynamic Main Content Based on Active Tab -->
    <main class="flex-1 max-w-[1720px] w-full mx-auto px-3 sm:px-6 py-4 space-y-4">
      <!-- TAB 1: 实盘矩阵 (TRADING) -->
      <div v-show="store.activeTab === 'trading'" class="space-y-4">
        <!-- Dual Column: Positions & In-flight Maker Orders -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <PositionList />
          <PendingOrders />
        </div>
        <!-- 6-Asset Grid -->
        <InstrumentMatrix />
        <!-- System Logs -->
        <LedgerLogs />
      </div>

      <!-- TAB 2: AI全景推演 (FACTORS) -->
      <div v-show="store.activeTab === 'factors'" class="space-y-4">
        <InstrumentMatrix />
        <LedgerLogs />
      </div>

      <!-- TAB 3: 全网舆情 (NEWS) -->
      <div v-show="store.activeTab === 'news'" class="space-y-4">
        <NewsIntelligence />
      </div>

      <!-- TAB 4: 自进化实验室 (LAB) -->
      <div v-show="store.activeTab === 'lab'" class="space-y-4">
        <SelfEvolutionLab />
      </div>

      <!-- TAB 5: 交易台账与生命周期 (HISTORY) -->
      <div v-show="store.activeTab === 'history'" class="space-y-4">
        <TradesLedger />
        <LedgerLogs />
      </div>
    </main>

    <!-- Global Cyber Footer -->
    <footer class="border-t border-[#1A2232] bg-[#0A0D14] py-3 text-center text-xs font-mono text-[#707E94]">
      <div class="flex items-center justify-center space-x-2">
        <span>R20 QUANTUM TRADER v6.2.1</span>
        <span>•</span>
        <span>VUE 3 + VITE + TAILWIND CSS 现代化重构</span>
        <span>•</span>
        <a href="https://github.com/555cute/r20-quantum-trader" target="_blank" class="hover:text-blue-400">GitHub</a>
      </div>
    </footer>
  </div>
</template>
