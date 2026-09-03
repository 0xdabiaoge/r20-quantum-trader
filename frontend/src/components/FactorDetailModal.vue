<script setup lang="ts">
import { ref } from 'vue'
import { X, Cpu, FileText, CheckCircle2, ShieldAlert, Zap, TrendingUp, TrendingDown } from 'lucide-vue-next'

const props = defineProps<{
  visible: boolean
  instrument: any | null
  fullPromptText?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const activeTab = ref<'reasoning' | 'prompt'>('reasoning')

function copyPrompt() {
  if (!props.fullPromptText) return
  navigator.clipboard.writeText(props.fullPromptText)
  alert('实发 Prompt 原文已复制到剪贴板！')
}
</script>

<template>
  <div
    v-if="visible"
    class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex justify-end transition-opacity"
    @click.self="emit('close')"
  >
    <div class="w-full max-w-2xl bg-[#0B0F17] border-l border-[#1A2232] h-full flex flex-col shadow-2xl overflow-hidden animate-slide-in">
      <!-- Drawer Header -->
      <div class="p-4 border-b border-[#1A2232] bg-[#0E131F] flex items-center justify-between shrink-0">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center font-black font-mono">
            {{ instrument?.name || 'AI' }}
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h3 class="font-extrabold text-sm text-white font-mono">{{ instrument?.name }} 深度认知推演全景</h3>
              <span class="text-[10px] font-mono px-1.5 py-0.2 rounded border border-blue-500/30 text-blue-400 bg-blue-500/10">
                {{ instrument?.instId }}
              </span>
            </div>
            <div class="text-[10px] text-[#707E94] font-mono mt-0.5">
              100% 审计溯源 · 微积分数学定积分证明 · 链上聪明钱博弈
            </div>
          </div>
        </div>

        <button
          @click="emit('close')"
          class="p-1.5 rounded-lg text-[#707E94] hover:text-white hover:bg-[#151D2C] transition-colors cursor-pointer"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Segmented View Selector -->
      <div class="flex border-b border-[#1A2232] bg-[#0D121B] px-4 pt-2 shrink-0">
        <button
          @click="activeTab = 'reasoning'"
          class="flex items-center space-x-2 px-4 py-2 border-b-2 text-xs font-mono font-bold transition-all cursor-pointer"
          :class="activeTab === 'reasoning' ? 'border-blue-400 text-white bg-[#141B28]' : 'border-transparent text-[#707E94] hover:text-zinc-300'"
        >
          <Cpu class="w-3.5 h-3.5 text-blue-400" />
          <span>五重数学推演证据</span>
        </button>
        <button
          @click="activeTab = 'prompt'"
          class="flex items-center space-x-2 px-4 py-2 border-b-2 text-xs font-mono font-bold transition-all cursor-pointer"
          :class="activeTab === 'prompt' ? 'border-blue-400 text-white bg-[#141B28]' : 'border-transparent text-[#707E94] hover:text-zinc-300'"
        >
          <FileText class="w-3.5 h-3.5 text-purple-400" />
          <span>当轮实发 Prompt 原文对照</span>
        </button>
      </div>

      <!-- Drawer Content -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <!-- TAB 1: 五重数学与微积分动能推演 -->
        <div v-if="activeTab === 'reasoning'" class="space-y-3">
          <!-- Decision Summary Banner -->
          <div class="bg-[#0E1422] border border-[#1A2232] rounded-xl p-3.5">
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-mono text-[#707E94]">决策输出</span>
              <span
                class="px-2 py-0.5 rounded text-xs font-bold font-mono border"
                :class="instrument?.action === 'BUY_LONG' ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : instrument?.action === 'SELL_SHORT' ? 'text-rose-400 border-rose-500/30 bg-rose-500/10' : 'text-zinc-400 border-zinc-700/40 bg-zinc-800/20'"
              >
                {{ instrument?.action || 'WAIT' }}
              </span>
            </div>
            <p class="text-xs text-white leading-relaxed font-sans font-medium">
              {{ instrument?.reason || '全市场宏观多因子评估中' }}
            </p>
          </div>

          <!-- Section 1: Calculus Dynamics -->
          <div class="bg-[#0E1422] border border-[#1A2232] rounded-xl p-3.5">
            <div class="flex items-center space-x-2 text-xs font-mono font-bold text-blue-400 mb-2">
              <Zap class="w-4 h-4" />
              <span>1. 高阶微积分物理动能证据 (Calculus Dynamics)</span>
            </div>
            <p class="text-xs text-zinc-300 font-mono leading-relaxed bg-[#080B10] p-2.5 rounded-lg border border-[#1A2232]/60">
              {{ instrument?.thought_process?.calculus_dynamics || '等待模型解析微积分动力学矩阵...' }}
            </p>
          </div>

          <!-- Section 2: Mathematical Probability Rationale -->
          <div class="bg-[#0E1422] border border-[#1A2232] rounded-xl p-3.5">
            <div class="flex items-center space-x-2 text-xs font-mono font-bold text-purple-400 mb-2">
              <TrendingUp class="w-4 h-4" />
              <span>2. 积分作用量与概率胜率评估 (Mathematical Rationale)</span>
            </div>
            <p class="text-xs text-zinc-300 font-mono leading-relaxed bg-[#080B10] p-2.5 rounded-lg border border-[#1A2232]/60">
              {{ instrument?.thought_process?.math_prob_rationale || '等待模型输出定积分与VaR概率证据...' }}
            </p>
          </div>

          <!-- Section 3: Market Structure & Volume/OI -->
          <div class="bg-[#0E1422] border border-[#1A2232] rounded-xl p-3.5">
            <div class="flex items-center space-x-2 text-xs font-mono font-bold text-emerald-400 mb-2">
              <ShieldAlert class="w-4 h-4" />
              <span>3. 多周期时空结构与持仓异动 (Market Structure & Flow)</span>
            </div>
            <div class="space-y-2 text-xs font-mono">
              <div class="bg-[#080B10] p-2 rounded border border-[#1A2232]/60">
                <span class="text-[#707E94] text-[10px] block">周期共振结构：</span>
                <span class="text-zinc-200">{{ instrument?.thought_process?.market_structure || '--' }}</span>
              </div>
              <div class="bg-[#080B10] p-2 rounded border border-[#1A2232]/60">
                <span class="text-[#707E94] text-[10px] block">持仓与量能异动：</span>
                <span class="text-zinc-200">{{ instrument?.thought_process?.volume_and_oi || '--' }}</span>
              </div>
            </div>
          </div>

          <!-- Section 4: Risk-Reward 2R Evaluation -->
          <div class="bg-[#0E1422] border border-[#1A2232] rounded-xl p-3.5">
            <div class="flex items-center space-x-2 text-xs font-mono font-bold text-amber-400 mb-2">
              <CheckCircle2 class="w-4 h-4" />
              <span>4. 严格盈亏比验证 (Risk-Reward Evaluation)</span>
            </div>
            <p class="text-xs text-zinc-300 font-mono leading-relaxed bg-[#080B10] p-2.5 rounded-lg border border-[#1A2232]/60">
              {{ instrument?.thought_process?.risk_reward_evaluation || '目标 R:R ≥ 2.5；执行底线 2.0。未达 2R 执行层一律安全降级拒绝开仓。' }}
            </p>
          </div>
        </div>

        <!-- TAB 2: 当轮实发 Prompt 原文对照 -->
        <div v-else class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-xs text-[#707E94] font-mono">发送至大模型网关的完整提示词</span>
            <button
              @click="copyPrompt"
              class="px-2.5 py-1 rounded bg-[#151D2C] hover:bg-[#1D273B] border border-[#1A2232] text-xs font-mono text-zinc-200 cursor-pointer"
            >
              复制原文
            </button>
          </div>
          <pre class="bg-[#080B10] border border-[#1A2232] rounded-xl p-4 text-xs font-mono text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-[600px] overflow-y-auto">{{ fullPromptText || '等待下一次 15 分钟交易周期写入实发提示词...' }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes slide-in {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
.animate-slide-in {
  animation: slide-in 0.2s ease-out;
}
</style>
