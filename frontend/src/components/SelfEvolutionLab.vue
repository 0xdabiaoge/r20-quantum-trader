<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Sparkles, Brain, RefreshCw, Cpu, GitCommit } from 'lucide-vue-next'

const store = useDashboardStore()
const review = computed(() => store.data?.review || {})
const memoryMd = computed(() => store.data?.ai_trading_memory_md || '')
const factorLib = computed(() => store.data?.factor_library || {})
</script>

<template>
  <div class="space-y-4">
    <!-- Lab Header -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="p-2 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
          <Sparkles class="w-5 h-5" />
        </div>
        <div>
          <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">AI 策略自进化与认知提炼中心</h2>
          <p class="text-xs text-[#707E94] font-mono">基于实战胜率、盈亏比与微积分动能反馈，每日全自主修正参数与策略心法</p>
        </div>
      </div>
      <div class="flex items-center space-x-2 text-xs font-mono">
        <span class="text-[#707E94]">自进化主脑:</span>
        <span class="text-purple-300 font-bold">{{ store.llmRuntime.model }}</span>
      </div>
    </div>

    <!-- Dual Layout: Realtime Memory MD & Factor Library -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- 1. Realtime Trading Memory (Markdown) -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
            <div class="flex items-center space-x-2">
              <Brain class="w-4 h-4 text-purple-400" />
              <h3 class="text-xs font-bold text-white font-mono uppercase">AI 进化心法与实盘记忆 (AI_TRADING_MEMORY.md)</h3>
            </div>
            <span class="text-[10px] font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
              持续沉淀
            </span>
          </div>
          <div class="bg-[#080B10] border border-[#1A2232] rounded-lg p-3 max-h-96 overflow-y-auto font-mono text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">
            {{ memoryMd || '【AI 认知提炼库为空，等待每日闭环自进化任务触发提炼】' }}
          </div>
        </div>
      </div>

      <!-- 2. Factor Library & Parameter Snapshot -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
            <div class="flex items-center space-x-2">
              <Cpu class="w-4 h-4 text-blue-400" />
              <h3 class="text-xs font-bold text-white font-mono uppercase">动态因子权重与量化自适应参数</h3>
            </div>
            <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
              动态回馈
            </span>
          </div>

          <div class="space-y-3 font-mono text-xs">
            <div class="bg-[#080B10] p-3 rounded-lg border border-[#1A2232]">
              <div class="text-[#707E94] text-[10px] uppercase mb-1">最近复盘结论</div>
              <p class="text-white text-xs font-sans leading-relaxed">{{ review.summary || '当前市场因子权重处于最优稳态区间，未触发阈值震荡修正。' }}</p>
            </div>

            <div class="grid grid-cols-2 gap-2 text-center">
              <div class="bg-[#080B10] p-2.5 rounded-lg border border-[#1A2232]">
                <div class="text-[#707E94] text-[10px]">微积分动能权重</div>
                <div class="text-emerald-400 font-bold text-sm mt-0.5">35%</div>
              </div>
              <div class="bg-[#080B10] p-2.5 rounded-lg border border-[#1A2232]">
                <div class="text-[#707E94] text-[10px]">聪明钱流向权重</div>
                <div class="text-blue-400 font-bold text-sm mt-0.5">30%</div>
              </div>
              <div class="bg-[#080B10] p-2.5 rounded-lg border border-[#1A2232]">
                <div class="text-[#707E94] text-[10px]">多周期结构共振</div>
                <div class="text-purple-400 font-bold text-sm mt-0.5">25%</div>
              </div>
              <div class="bg-[#080B10] p-2.5 rounded-lg border border-[#1A2232]">
                <div class="text-[#707E94] text-[10px]">全网舆情过滤</div>
                <div class="text-amber-400 font-bold text-sm mt-0.5">10%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
