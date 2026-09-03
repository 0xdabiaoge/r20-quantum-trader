<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Brain, ChevronDown } from 'lucide-vue-next'
import { ref } from 'vue'

const store = useDashboardStore()
const history = computed<any[]>(() => (store.data?.ai_brain_history || []).slice(0, 24))
const expanded = ref<Set<number>>(new Set())

function toggle(i: number) {
  const s = new Set(expanded.value)
  s.has(i) ? s.delete(i) : s.add(i)
  expanded.value = s
}
</script>

<template>
  <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
    <div class="flex items-center space-x-3 mb-4">
      <div class="p-2 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
        <Brain class="w-5 h-5" />
      </div>
      <div>
        <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">AI 宏观多周期推演基调</h2>
        <p class="text-xs text-[#707E94] font-mono">每 15 分钟 LLM 决策周期的宏观评估与在途持仓管理指令留痕</p>
      </div>
    </div>

    <div v-if="history.length === 0" class="py-10 text-center text-xs font-mono text-[#707E94] border border-dashed border-[#1A2232] rounded-lg">
      暂无历史决策记录，等待下一次 15 分钟推演周期
    </div>

    <div v-else class="space-y-2.5 max-h-[640px] overflow-y-auto pr-1">
      <div v-for="(item, i) in history" :key="i" class="rounded-lg bg-[#080B10] border border-[#161D2B] p-3">
        <button @click="toggle(i)" class="w-full flex items-center justify-between text-left cursor-pointer gap-2">
          <div class="flex items-center space-x-2 min-w-0">
            <span class="text-blue-400 font-bold text-[11px] font-mono shrink-0">{{ item.time }}</span>
            <span class="text-[11px] text-zinc-400 font-sans truncate">{{ item.macro_assessment || '宏观中性震荡' }}</span>
          </div>
          <ChevronDown class="w-3.5 h-3.5 text-[#707E94] shrink-0 transition-transform" :class="expanded.has(i) ? 'rotate-180' : ''" />
        </button>
        <div v-if="expanded.has(i)" class="mt-2.5 space-y-2 border-t border-[#161D2B] pt-2.5">
          <p class="text-xs text-zinc-300 font-sans leading-relaxed">{{ item.macro_assessment || '宏观中性震荡' }}</p>
          <div v-if="item.position_management?.length" class="p-2 rounded-lg bg-[#0A0F18] border border-[#161D2B] space-y-1.5 font-mono text-[11px]">
            <span class="text-[10px] font-bold text-blue-400 block uppercase">在途持仓管理指令</span>
            <div v-for="(p, j) in item.position_management" :key="j" class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[#9db0c6]">
              <strong class="text-white">{{ p.instId }}</strong>
              <span class="px-1.5 py-0.2 rounded bg-[#141B26] text-blue-300 font-bold border border-[#1A2232] text-[10px]">{{ p.action }}</span>
              <span class="text-[10px]">{{ p.reason }}</span>
            </div>
          </div>
          <div v-else class="text-[10px] font-mono text-[#556677]">本轮无在途持仓管理指令</div>
        </div>
      </div>
    </div>
  </div>
</template>
