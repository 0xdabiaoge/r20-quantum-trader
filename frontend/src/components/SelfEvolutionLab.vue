<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Sparkles, Brain, Cpu, TrendingUp, ShieldCheck } from 'lucide-vue-next'

const store = useDashboardStore()
const review = computed(() => store.data?.review || {})
const memoryMd = computed(() => store.data?.ai_trading_memory_md || '')
const backtest = computed(() => store.data?.backtest_report || null)
</script>

<template>
  <div class="space-y-3.5">
    <!-- Lab Header -->
    <div
      class="rounded-xl border p-4 sm:p-5 flex items-center justify-between shadow-xs transition-colors"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <div class="flex items-center space-x-3">
        <div
          class="w-9 h-9 rounded-lg flex items-center justify-center border shrink-0"
          style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
        >
          <Sparkles class="w-4 h-4" />
        </div>
        <div>
          <h2 class="text-xs sm:text-sm font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">
            AI 策略自进化与认知提炼中心
          </h2>
          <p class="text-xs font-mono mt-0.5" style="color: var(--text-muted);">
            基于实战胜率、盈亏比与微积分动能反馈，每日全自主修正参数与策略心法
          </p>
        </div>
      </div>
      <div class="flex items-center space-x-2 text-xs font-mono">
        <span style="color: var(--text-faint);">自进化主脑:</span>
        <span class="font-bold font-mono" style="color: var(--text-main);">{{ store.llmRuntime.model }}</span>
      </div>
    </div>

    <!-- Dual Layout: Realtime Memory MD & Factor Library -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
      <!-- 1. Realtime Trading Memory (Markdown) -->
      <div
        class="rounded-xl border p-4 sm:p-5 flex flex-col justify-between shadow-xs transition-colors"
        style="background-color: var(--bg-card); border-color: var(--border-subtle);"
      >
        <div>
          <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
            <div class="flex items-center space-x-2">
              <Brain class="w-4 h-4" style="color: var(--color-brand);" />
              <h3 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">
                AI 进化心法与实盘记忆 (AI_TRADING_MEMORY.md)
              </h3>
            </div>
            <span
              class="text-[10px] font-mono px-2 py-0.5 rounded border font-bold"
              style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-muted);"
            >
              持续沉淀
            </span>
          </div>
          <div
            class="rounded-lg border p-3 max-h-96 overflow-y-auto font-mono text-xs whitespace-pre-wrap leading-relaxed"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-muted);"
          >
            {{ memoryMd || '【AI 认知提炼库为空，等待每日闭环自进化任务触发提炼】' }}
          </div>
        </div>
      </div>

      <!-- 2. Factor Library & Parameter Snapshot -->
      <div
        class="rounded-xl border p-4 sm:p-5 flex flex-col justify-between shadow-xs transition-colors"
        style="background-color: var(--bg-card); border-color: var(--border-subtle);"
      >
        <div>
          <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
            <div class="flex items-center space-x-2">
              <Cpu class="w-4 h-4" style="color: var(--color-brand);" />
              <h3 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">
                动态因子权重与量化自适应参数
              </h3>
            </div>
            <span
              class="text-[10px] font-mono px-2 py-0.5 rounded border font-bold"
              style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-muted);"
            >
              动态反馈
            </span>
          </div>

          <div class="space-y-3 font-mono text-xs">
            <div class="p-3 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
              <div class="text-[10px] uppercase mb-1 font-bold" style="color: var(--text-faint);">最近复盘结论</div>
              <p class="text-xs font-sans leading-relaxed" style="color: var(--text-main);">
                {{ review.summary || '当前市场因子权重处于最优稳态区间，未触发阈值震荡修正。' }}
              </p>
            </div>

            <div class="grid grid-cols-2 gap-2 text-center">
              <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
                <div class="text-[10px]" style="color: var(--text-faint);">微积分动能权重</div>
                <div class="font-bold text-sm mt-0.5 num-tabular" style="color: var(--color-up);">35%</div>
              </div>
              <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
                <div class="text-[10px]" style="color: var(--text-faint);">聪明钱流向权重</div>
                <div class="font-bold text-sm mt-0.5 num-tabular" style="color: var(--text-main);">30%</div>
              </div>
              <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
                <div class="text-[10px]" style="color: var(--text-faint);">多周期结构共振</div>
                <div class="font-bold text-sm mt-0.5 num-tabular" style="color: var(--text-main);">25%</div>
              </div>
              <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
                <div class="text-[10px]" style="color: var(--text-faint);">全网舆情过滤</div>
                <div class="font-bold text-sm mt-0.5 num-tabular" style="color: var(--color-warn);">10%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 3. Quantitative Backtesting & Statistical Verification (公开算法实证看板) -->
    <div
      v-if="backtest"
      class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
        <div class="flex items-center space-x-2">
          <TrendingUp class="w-4 h-4 text-indigo-400" />
          <h3 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">
            量化回测与统计显著性验证 (Deterministic Backtesting Attribution)
          </h3>
          <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            OKX 真实历史 K 线驱动
          </span>
        </div>
        <span class="text-[10px] font-mono" style="color: var(--text-muted);">
          标的: {{ backtest.symbol }} · 初始资金: ${{ backtest.initial_equity }}
        </span>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono">
        <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">收益率 / 净值</div>
          <div class="font-bold text-sm mt-0.5" :class="backtest.total_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'">
            {{ backtest.total_return_pct }}%
          </div>
          <div class="text-[9px] text-gray-500">${{ backtest.final_equity }}</div>
        </div>

        <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">夏普比率 (Sharpe)</div>
          <div class="font-bold text-sm mt-0.5 text-indigo-400">{{ backtest.sharpe_ratio }}</div>
          <div class="text-[9px] text-gray-500">索提诺: {{ backtest.sortino_ratio }}</div>
        </div>

        <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">最大回撤 (Max DD)</div>
          <div class="font-bold text-sm mt-0.5 text-amber-400">{{ backtest.max_drawdown_pct }}%</div>
          <div class="text-[9px] text-gray-500">卡玛: {{ backtest.calmar_ratio }}</div>
        </div>

        <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">胜率 / 盈亏比</div>
          <div class="font-bold text-sm mt-0.5 text-cyan-400">{{ backtest.win_rate_pct }}%</div>
          <div class="text-[9px] text-gray-500">PF: {{ backtest.profit_factor }}</div>
        </div>

        <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">回测交易单数</div>
          <div class="font-bold text-sm mt-0.5" style="color: var(--text-main);">{{ backtest.total_trades }} 笔</div>
          <div class="text-[9px] text-gray-500">胜{{ backtest.winning_trades }}/负{{ backtest.losing_trades }} (均R: {{ backtest.avg_r_multiple }}R)</div>
        </div>

        <div class="p-2.5 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">拦截器物理防割肉</div>
          <div class="font-bold text-sm mt-0.5 text-emerald-400">{{ backtest.gatekeeper_filtered_count }} 次</div>
          <div class="text-[9px] text-gray-500">过滤虚假杂波</div>
        </div>
      </div>
    </div>
  </div>
</template>
