<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import HeaderBar from '../components/HeaderBar.vue'
import InstrumentMatrix from '../components/InstrumentMatrix.vue'
import PositionList from '../components/PositionList.vue'
import PendingOrders from '../components/PendingOrders.vue'
import LedgerLogs from '../components/LedgerLogs.vue'
import NewsIntelligence from '../components/NewsIntelligence.vue'
import SelfEvolutionLab from '../components/SelfEvolutionLab.vue'
import TradesLedger from '../components/TradesLedger.vue'
import { useRoute } from 'vue-router'

const store = useDashboardStore()
const route = useRoute()

onMounted(() => {
  store.startPolling(3000)
})

onUnmounted(() => {
  store.stopPolling()
})
</script>

<template>
  <div class="min-h-screen bg-[#080B10] text-[#F3F4F6] flex flex-col selection:bg-blue-500 selection:text-white">
    <HeaderBar />

    <main class="flex-1 max-w-[1720px] w-full mx-auto px-3 sm:px-6 py-4 space-y-4">
      <div v-show="store.activeTab === 'trading'" class="space-y-4">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <PositionList />
          <PendingOrders />
        </div>
        <InstrumentMatrix />
        <LedgerLogs />
      </div>

      <div v-show="store.activeTab === 'factors'" class="space-y-4">
        <InstrumentMatrix />
        <LedgerLogs />
      </div>

      <div v-show="store.activeTab === 'news'" class="space-y-4">
        <NewsIntelligence />
      </div>

      <div v-show="store.activeTab === 'lab'" class="space-y-4">
        <SelfEvolutionLab />
      </div>

      <div v-show="store.activeTab === 'history'" class="space-y-4">
        <TradesLedger />
        <LedgerLogs />
      </div>
    </main>

    <footer class="border-t border-[#1A2232] bg-[#0A0D14] py-3 text-center text-xs font-mono text-[#707E94]">
      <div class="flex items-center justify-center space-x-2">
        <span>R20 QUANTUM TRADER v6.2.1</span>
        <span>•</span>
        <span>VUE 3 + VITE + TAILWIND CSS</span>
        <span>•</span>
        <a href="https://github.com/555cute/r20-quantum-trader" target="_blank" class="hover:text-blue-400">GitHub</a>
      </div>
    </footer>
  </div>
</template>
