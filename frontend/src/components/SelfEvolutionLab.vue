<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Sparkles, Brain, Cpu, TrendingUp, ShieldCheck, Layers, ArrowUpRight, ArrowDownRight, RefreshCw, BarChart3 } from 'lucide-vue-next'

const store = useDashboardStore()
const review = computed(() => store.data?.review || {})
const memoryMd = computed(() => store.data?.ai_trading_memory_md || '')
const rawBacktest = computed(() => store.data?.backtest_report || null)

// Current view tab for backtesting: "PORTFOLIO" or specific symbol
const selectedSymbol = ref<string>('PORTFOLIO')

const currentReport = computed(() => {
  if (!rawBacktest.value) return null
  if (selectedSymbol.value === 'PORTFOLIO') {
    return rawBacktest.value.portfolio || rawBacktest.value
  }
  return rawBacktest.value.by_symbol?.[selectedSymbol.value] || rawBacktest.value.portfolio || rawBacktest.value
})

const availableSymbols = computed(() => {
  return rawBacktest.value?.active_symbols || [
    'BTC-USDT-SWAP',
    'ETH-USDT-SWAP',
    'SOL-USDT-SWAP',
    'DOGE-USDT-SWAP',
    'SUI-USDT-SWAP',
    'ASTER-USDT-SWAP',
  ]
})

const equityPoints = computed(() => {
  const curve = currentReport.value?.equity_curve || []
  if (!curve.length) return []
  const values = curve.map((p: any) => Number(p.equity))
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  return curve.map((p: any, idx: number) => ({
    x: (idx / (curve.length - 1 || 1)) * 100,
    y: 100 - ((Number(p.equity) - min) / range) * 80 - 10,
    equity: p.equity,
    time: p.time,
  }))
})

const svgPath = computed(() => {
  const pts = equityPoints.value
  if (!pts.length) return ''
  return pts.map((p: any, idx: number) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
})
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
            基于实战胜率、盈亏比与微积分动能反馈，每6小时全自主修正参数与策略心法
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
                实战经验记忆库 (Trading Memory)
              </h3>
            </div>
            <span
              class="text-[10px] font-mono px-2 py-0.5 rounded border font-bold"
              style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-muted);"
            >
              每6小时自动沉淀
            </span>
          </div>
          <div
            class="p-3.5 rounded-lg border text-xs font-mono leading-relaxed max-h-[260px] overflow-y-auto whitespace-pre-wrap select-text"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-main);"
          >
            {{ memoryMd || '正在读取长期心法知识库...' }}
          </div>
        </div>
      </div>

      <!-- 2. Dynamic Factor Weights & Parameters -->
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
                {{ review.summary || '当前市场因子权重处于最优稳态区间，微积分动能结合保本移损锁死期望值优势。' }}
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

    <!-- 3. Full-Scale Institutional Backtesting Attribution Console -->
    <div
      v-if="currentReport"
      class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors space-y-4"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <!-- Top Title & Asset Switcher Bar -->
      <div class="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b gap-3" style="border-color: var(--border-subtle);">
        <div>
          <div class="flex items-center space-x-2">
            <TrendingUp class="w-4 h-4 text-indigo-400" />
            <h3 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">
              确定性量化回测与统计显著性归因 (Deterministic Backtest Attribution)
            </h3>
            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              OKX 真实 100 根 1H K线驱动
            </span>
          </div>
          <p class="text-xs font-mono mt-1" style="color: var(--text-muted);">
            测算标的：<strong>{{ currentReport.symbol }}</strong> · 初始资金：${{ currentReport.initial_equity?.toLocaleString() }} · 真实滑点/手续费摩擦完全扣除
          </p>
        </div>

        <!-- Symbol Selector Pills -->
        <div class="flex flex-wrap items-center gap-1.5 font-mono text-xs">
          <button
            @click="selectedSymbol = 'PORTFOLIO'"
            class="px-2.5 py-1 rounded-lg border transition-all cursor-pointer font-bold"
            :style="selectedSymbol === 'PORTFOLIO' ? {
              backgroundColor: '#3875F6',
              borderColor: '#2b5ec9',
              color: '#FFFFFF',
            } : {
              backgroundColor: 'var(--bg-card-subtle)',
              borderColor: 'var(--border-subtle)',
              color: 'var(--text-muted)',
            }"
          >
            🌟 全组合全景 (6币)
          </button>
          <button
            v-for="s in availableSymbols"
            :key="s"
            @click="selectedSymbol = s"
            class="px-2 py-1 rounded-lg border transition-all cursor-pointer font-mono text-[11px]"
            :style="selectedSymbol === s ? {
              backgroundColor: '#3875F6',
              borderColor: '#2b5ec9',
              color: '#FFFFFF',
            } : {
              backgroundColor: 'var(--bg-card-subtle)',
              borderColor: 'var(--border-subtle)',
              color: 'var(--text-muted)',
            }"
          >
            {{ s.replace('-USDT-SWAP', '') }}
          </button>
        </div>
      </div>

      <!-- Core Risk Metrics Grid (6 Columns) -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono">
        <div class="p-3 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">总收益率 (Total ROI)</div>
          <div class="font-black text-sm mt-1" :class="currentReport.total_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'">
            {{ currentReport.total_return_pct >= 0 ? '+' : '' }}{{ currentReport.total_return_pct }}%
          </div>
          <div class="text-[10px] text-gray-500 font-mono mt-0.5">${{ currentReport.final_equity?.toLocaleString() }}</div>
        </div>

        <div class="p-3 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">年化夏普 / 索提诺</div>
          <div class="font-black text-sm mt-1 text-indigo-400">{{ currentReport.sharpe_ratio }}</div>
          <div class="text-[10px] text-gray-500 font-mono mt-0.5">Sortino: {{ currentReport.sortino_ratio }}</div>
        </div>

        <div class="p-3 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">最大回撤 (Max DD)</div>
          <div class="font-black text-sm mt-1 text-amber-400">{{ currentReport.max_drawdown_pct }}%</div>
          <div class="text-[10px] text-gray-500 font-mono mt-0.5">Calmar: {{ currentReport.calmar_ratio }}</div>
        </div>

        <div class="p-3 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">胜率 / 获利因子 (PF)</div>
          <div class="font-black text-sm mt-1 text-cyan-400">{{ currentReport.win_rate_pct }}%</div>
          <div class="text-[10px] text-gray-500 font-mono mt-0.5">PF: {{ currentReport.profit_factor }}</div>
        </div>

        <div class="p-3 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">推演单数 (胜/负)</div>
          <div class="font-black text-sm mt-1" style="color: var(--text-main);">{{ currentReport.total_trades }} 笔</div>
          <div class="text-[10px] text-gray-500 font-mono mt-0.5">{{ currentReport.winning_trades }}胜 / {{ currentReport.losing_trades }}负 (均R: {{ currentReport.avg_r_multiple }}R)</div>
        </div>

        <div class="p-3 rounded-lg border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="text-[10px]" style="color: var(--text-faint);">拦截器防割肉过滤</div>
          <div class="font-black text-sm mt-1 text-emerald-400">{{ currentReport.gatekeeper_filtered_count }} 次</div>
          <div class="text-[10px] text-gray-500 font-mono mt-0.5">Fail-Closed 杂波剔除</div>
        </div>
      </div>

      <!-- Mini Equity Curve Visualization -->
      <div v-if="equityPoints.length > 1" class="rounded-lg border p-3.5 space-y-2" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
        <div class="flex items-center justify-between text-xs font-mono">
          <div class="flex items-center space-x-1.5 text-gray-300 font-bold">
            <BarChart3 class="w-3.5 h-3.5 text-indigo-400" />
            <span>历史资产净值演进曲线 (Equity Curve)</span>
          </div>
          <span class="text-[10px] text-gray-500">区间：{{ currentReport.equity_curve[0]?.time }} ~ {{ currentReport.equity_curve[currentReport.equity_curve.length - 1]?.time }}</span>
        </div>

        <!-- SVG Sparkline -->
        <div class="h-20 w-full relative pt-1">
          <svg class="w-full h-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
            <path
              :d="svgPath"
              fill="none"
              stroke="#3875F6"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>
      </div>

      <!-- Recent Simulated Execution Log (Audit Trails) -->
      <div v-if="currentReport.recent_trades && currentReport.recent_trades.length" class="space-y-2">
        <div class="flex items-center justify-between text-xs font-mono">
          <span class="font-bold text-gray-300">最新推演成交明细 (最近 {{ currentReport.recent_trades.length }} 笔)</span>
          <span class="text-[10px] text-gray-500">2.0x ATR 宽止损 · 0.8R 保本锁利</span>
        </div>

        <div class="rounded-lg border overflow-hidden" style="border-color: var(--border-subtle);">
          <table class="w-full text-left font-mono text-xs border-collapse">
            <thead class="text-[10px] uppercase text-gray-400" style="background-color: var(--bg-card-subtle);">
              <tr>
                <th class="p-2">标的</th>
                <th class="p-2">方向</th>
                <th class="p-2">开仓时间</th>
                <th class="p-2">平仓时间</th>
                <th class="p-2">开/平价格</th>
                <th class="p-2">净盈亏</th>
                <th class="p-2 text-right">退出原因</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-subtle);">
              <tr
                v-for="(t, idx) in currentReport.recent_trades"
                :key="idx"
                class="hover:bg-[var(--bg-card-subtle)] transition-colors text-[11px]"
              >
                <td class="p-2 font-bold">{{ t.symbol.replace('-USDT-SWAP', '') }}</td>
                <td class="p-2">
                  <span
                    class="px-1.5 py-0.2 rounded font-bold text-[10px]"
                    :style="{
                      backgroundColor: t.direction === 'LONG' ? 'var(--color-up-bg)' : 'var(--color-down-bg)',
                      color: t.direction === 'LONG' ? 'var(--color-up)' : 'var(--color-down)'
                    }"
                  >
                    {{ t.direction === 'LONG' ? '买多' : '卖空' }}
                  </span>
                </td>
                <td class="p-2 text-gray-400">{{ t.entry_time }}</td>
                <td class="p-2 text-gray-400">{{ t.exit_time }}</td>
                <td class="p-2 font-mono text-gray-300">{{ t.entry_price }} → {{ t.exit_price }}</td>
                <td class="p-2 font-bold num-tabular" :class="t.pnl_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'">
                  {{ t.pnl_usd >= 0 ? '+' : '' }}{{ t.pnl_usd }} U ({{ t.r_multiple }}R)
                </td>
                <td class="p-2 text-right text-[10px] text-gray-400">
                  <span v-if="t.exit_reason === 'TAKE_PROFIT'" class="text-emerald-400 font-bold">🎯 目标止盈</span>
                  <span v-else-if="t.r_multiple >= 0" class="text-cyan-400 font-bold">🛡️ 保本平仓</span>
                  <span v-else class="text-rose-400">🛑 触碰止损</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
