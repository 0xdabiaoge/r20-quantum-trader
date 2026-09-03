<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Brain, ChevronDown, Users } from 'lucide-vue-next'
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
  <div class="quantum-card p-4 sm:p-5">
    <div class="flex items-center space-x-3 mb-4">
      <div class="p-2.5 rounded-xl bg-purple-500/15 border border-purple-500/30 text-purple-400">
        <Brain class="w-5 h-5" />
      </div>
      <div>
        <h2 class="text-sm font-black text-white font-mono uppercase tracking-wide">AI 宏观多周期推演基调与决策审计</h2>
        <p class="text-xs text-slate-400 font-mono">每 15 分钟 LLM 决策周期的宏观研判、多模型辩论实录与在途持仓管理指令</p>
      </div>
    </div>

    <div v-if="history.length === 0" class="py-12 text-center text-xs font-mono text-slate-400 border border-dashed border-[#182644] rounded-2xl bg-[#070D1C]/50">
      暂无历史决策记录，等待下一次 15 分钟推演周期
    </div>

    <div v-else class="space-y-3 max-h-[680px] overflow-y-auto pr-1">
      <div v-for="(item, i) in history" :key="i" class="rounded-xl bg-[#070D1C] border border-[#162444] p-3.5 transition-all hover:border-blue-500/40">
        <button @click="toggle(i)" class="w-full flex items-center justify-between text-left cursor-pointer gap-2">
          <div class="flex items-center space-x-2.5 min-w-0">
            <span class="text-cyan-400 font-black text-xs font-mono shrink-0 num-tabular">{{ item.time }}</span>
            <span
              v-if="item.council_transcript"
              class="px-2 py-0.5 rounded-md text-[9px] font-mono font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30 shrink-0"
            >
              🏛️ 委员会协作
            </span>
            <span class="text-xs text-slate-300 font-sans truncate">{{ item.macro_assessment || '宏观中性震荡' }}</span>
          </div>
          <ChevronDown class="w-4 h-4 text-slate-400 shrink-0 transition-transform" :class="expanded.has(i) ? 'rotate-180' : ''" />
        </button>

        <div v-if="expanded.has(i)" class="mt-3 space-y-3 border-t border-[#182644] pt-3">
          <!-- Macro Summary -->
          <div>
            <div class="text-[10px] font-bold text-slate-400 font-mono uppercase mb-1">宏观研判总结:</div>
            <p class="text-xs text-slate-200 font-sans leading-relaxed">{{ item.macro_assessment || '宏观中性震荡' }}</p>
          </div>

          <!-- Multi-Agent Council Transcript -->
          <div v-if="item.council_transcript" class="p-3.5 rounded-xl bg-[#0B1020] border border-purple-500/30 space-y-2.5 font-mono">
            <div class="flex items-center justify-between border-b border-[#182644] pb-2">
              <div class="flex items-center space-x-2 text-purple-300 text-xs font-bold">
                <Users class="w-4 h-4" />
                <span>【多角色模型现场辩论纪要】</span>
              </div>
              <span class="text-[10px] text-slate-400 font-mono">
                协作总时延: {{ item.council_transcript.total_duration_ms }}ms
              </span>
            </div>

            <!-- Advisors viewpoints -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-2.5 pt-1">
              <div
                v-for="(adv, advKey) in item.council_transcript.advisors || {}"
                :key="advKey"
                class="p-2.5 rounded-lg bg-[#070D1C] border border-[#1A284A] space-y-1 text-xs"
              >
                <div class="flex items-center justify-between font-bold">
                  <span class="text-white">{{ adv.role_name }}</span>
                  <span class="text-[10px] text-purple-400">{{ adv.model_used }}</span>
                </div>
                <p class="text-slate-300 text-[11px] leading-relaxed whitespace-pre-wrap max-h-36 overflow-y-auto pr-0.5 select-text">
                  {{ adv.content }}
                </p>
              </div>
            </div>

            <!-- Arbitrator summary -->
            <div class="mt-1 pt-2 border-t border-[#182644] text-xs text-emerald-400 font-bold flex items-center justify-between">
              <span>⚖️ 首席仲裁官裁决收口: 采纳专家参谋核心论点，生成统一发单指令</span>
              <span class="text-[10px] text-slate-400 font-normal">
                终审模型: {{ item.council_transcript.arbitrator?.model_used }}
              </span>
            </div>
          </div>

          <!-- In-flight Position Management Instructions -->
          <div v-if="item.position_management?.length" class="p-2.5 rounded-xl bg-[#080E1E] border border-[#162444] space-y-1.5 font-mono text-xs">
            <span class="text-[10px] font-bold text-cyan-400 block uppercase">在途持仓管理指令</span>
            <div v-for="(p, j) in item.position_management" :key="j" class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-slate-300">
              <strong class="text-white">{{ p.instId }}</strong>
              <span class="px-2 py-0.5 rounded bg-[#0D1832] text-cyan-300 font-bold border border-cyan-500/25 text-[10px]">{{ p.action }}</span>
              <span v-if="p.reason" class="text-slate-400 text-[11px]">{{ p.reason }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
