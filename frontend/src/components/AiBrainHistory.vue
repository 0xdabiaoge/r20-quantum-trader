<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Brain, ChevronDown, Users, Shield, Zap, Cpu } from 'lucide-vue-next'
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
        <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">AI 宏观多周期推演基调与决策审计</h2>
        <p class="text-xs text-[#707E94] font-mono">每 15 分钟 LLM 决策周期的宏观研判、多模型辩论实录与在途持仓管理指令</p>
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
            <span
              v-if="item.council_transcript"
              class="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30 shrink-0"
            >
              🏛️ 委员会协作
            </span>
            <span class="text-[11px] text-zinc-400 font-sans truncate">{{ item.macro_assessment || '宏观中性震荡' }}</span>
          </div>
          <ChevronDown class="w-3.5 h-3.5 text-[#707E94] shrink-0 transition-transform" :class="expanded.has(i) ? 'rotate-180' : ''" />
        </button>

        <div v-if="expanded.has(i)" class="mt-2.5 space-y-2.5 border-t border-[#161D2B] pt-2.5">
          <!-- Macro Summary -->
          <div>
            <div class="text-[10px] font-bold text-[#8997aa] font-mono uppercase mb-0.5">宏观研判总结:</div>
            <p class="text-xs text-zinc-300 font-sans leading-relaxed">{{ item.macro_assessment || '宏观中性震荡' }}</p>
          </div>

          <!-- Multi-Agent Council Transcript (if this round was done via council) -->
          <div v-if="item.council_transcript" class="p-3 rounded-lg bg-[#0A0D15] border border-purple-500/30 space-y-2 font-mono">
            <div class="flex items-center justify-between border-b border-[#1A2232] pb-1.5">
              <div class="flex items-center space-x-1.5 text-purple-400 text-xs font-bold">
                <Users class="w-3.5 h-3.5" />
                <span>【多角色模型现场辩论纪要】</span>
              </div>
              <span class="text-[10px] text-[#707E94]">
                协作总时延: {{ item.council_transcript.total_duration_ms }}ms
              </span>
            </div>

            <!-- Advisors viewpoints -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-2 pt-1">
              <div
                v-for="(adv, advKey) in item.council_transcript.advisors || {}"
                :key="advKey"
                class="p-2 rounded bg-[#06080E] border border-[#1A2232] space-y-1 text-[11px]"
              >
                <div class="flex items-center justify-between font-bold">
                  <span class="text-zinc-200">{{ adv.role_name }}</span>
                  <span class="text-[9px] text-purple-400">{{ adv.model_used }}</span>
                </div>
                <p class="text-zinc-400 text-[10px] leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto pr-0.5">
                  {{ adv.content }}
                </p>
              </div>
            </div>

            <!-- Arbitrator summary -->
            <div class="mt-1 pt-1.5 border-t border-[#1A2232] text-[11px] text-emerald-400 flex items-center justify-between">
              <span>⚖️ 首席仲裁官裁决收口: 采纳专家参谋核心论点，生成统一发单指令</span>
              <span class="text-[9px] text-[#707E94]">
                终审模型: {{ item.council_transcript.arbitrator?.model_used }}
              </span>
            </div>
          </div>

          <!-- In-flight Position Management Instructions -->
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
