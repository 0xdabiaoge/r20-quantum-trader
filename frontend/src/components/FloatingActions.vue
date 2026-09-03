<script setup lang="ts">
import { ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { RefreshCw, Terminal, X, Copy } from 'lucide-vue-next'

const store = useDashboardStore()
const isRotating = ref(false)
const promptModalOpen = ref(false)
const promptCopied = ref(false)

function manualRefresh() {
  if (isRotating.value) return
  isRotating.value = true
  store.fetchDashboard(false).finally(() => {
    setTimeout(() => { isRotating.value = false }, 600)
  })
}

function copyPrompt() {
  const text = store.data?.ai_last_prompt || ''
  if (!text) return
  navigator.clipboard.writeText(text)
  promptCopied.value = true
  setTimeout(() => { promptCopied.value = false }, 1500)
}
</script>

<template>
  <!-- ⚡ Global Floating Actions (bottom-right: refresh + realtime prompt) -->
  <div class="fixed bottom-20 right-4 sm:bottom-6 sm:right-6 z-40 flex flex-col items-end space-y-2.5">
    <!-- Floating Refresh (pure circular icon button) -->
    <button
      @click="manualRefresh"
      title="立即刷新全量数据"
      class="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-[#0E121B]/95 hover:bg-[#141A26] text-[#EAECEF] hover:text-white shadow-2xl border border-[#1A2232] hover:border-[#3875F6] transition transform hover:-translate-y-0.5 active:scale-90 backdrop-blur-md cursor-pointer flex items-center justify-center"
    >
      <RefreshCw class="w-4 h-4 text-[#3875F6]" :class="{ 'animate-spin': isRotating || store.isRefreshing }" />
    </button>

    <!-- Realtime Prompt Floating Button -->
    <button
      @click="promptModalOpen = true"
      title="点击展开实时 AI 大脑提示词"
      class="flex items-center space-x-2 px-3.5 py-2 sm:px-4 sm:py-2.5 rounded-full bg-[#0E121B]/95 hover:bg-[#141A26] text-white shadow-2xl border border-[#1A2232] hover:border-[#3875F6] transition transform hover:-translate-y-0.5 active:scale-95 backdrop-blur-md cursor-pointer"
    >
      <div class="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold">
        <Terminal class="w-3 h-3" />
      </div>
      <span class="text-xs font-mono font-bold tracking-wide">实时提示词</span>
      <span class="w-2 h-2 rounded-full bg-[#0ECB81] animate-pulse"></span>
    </button>
  </div>

  <!-- 🪟 Realtime Prompt Audit Modal -->
  <div
    v-if="promptModalOpen"
    class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md"
    @click.self="promptModalOpen = false"
  >
    <div class="bg-[#0E121B] border border-[#1A2232] rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden font-mono">
      <!-- Modal Header -->
      <div class="px-5 py-4 border-b border-[#1A2232] flex items-center justify-between bg-[#080B10] shrink-0">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-blue-500/15 border border-blue-500/25 text-blue-400 flex items-center justify-center">
            <Terminal class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-white">实时 AI 大脑提示词审计</h3>
            <p class="text-[10px] text-[#707E94]">当前轮次真实发往大模型网关的完整 System + User Prompt 原文</p>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <button
            @click="copyPrompt"
            class="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-xs text-[#b8c4d4] cursor-pointer"
          >
            <Copy class="w-3.5 h-3.5" />
            <span>{{ promptCopied ? '已复制 ✓' : '复制全文' }}</span>
          </button>
          <button
            @click="promptModalOpen = false"
            class="p-1.5 rounded-lg text-[#707E94] hover:text-white hover:bg-[#151D2C] cursor-pointer"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Modal Body -->
      <div class="flex-1 overflow-y-auto p-5">
        <pre class="text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">{{ store.data?.ai_last_prompt || '等待下一次 15 分钟交易周期写入实发提示词...' }}</pre>
      </div>
    </div>
  </div>
</template>
