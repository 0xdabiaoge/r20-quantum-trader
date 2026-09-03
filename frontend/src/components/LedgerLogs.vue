<script setup lang="ts">
import { useDashboardStore } from '../stores/dashboard'
import { Terminal } from 'lucide-vue-next'

const store = useDashboardStore()
</script>

<template>
  <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center space-x-2">
        <Terminal class="w-4 h-4 text-purple-400" />
        <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">系统巡检日志流 (15分钟周期)</h2>
      </div>
      <span class="text-xs text-[#707E94] font-mono">实时滚动</span>
    </div>

    <div class="bg-[#080B10] border border-[#1A2232]/80 rounded-lg p-3 max-h-56 overflow-y-auto font-mono text-[11px] space-y-1.5">
      <div
        v-for="(log, idx) in store.logs"
        :key="idx"
        class="text-zinc-300 border-l-2 border-blue-500/40 pl-2 py-0.5 leading-relaxed hover:bg-[#121824]/40"
      >
        {{ log }}
      </div>
      <div v-if="store.logs.length === 0" class="text-[#707E94] text-center py-4">
        暂无巡检日志
      </div>
    </div>
  </div>
</template>
