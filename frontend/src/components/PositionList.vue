<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { ShieldCheck, TrendingUp, TrendingDown, ArrowUpRight, Lock } from 'lucide-vue-next'

const store = useDashboardStore()

function fmt2(v: any): string {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''))
  return Number.isFinite(n) ? n.toFixed(2) : '--'
}
function fmt4(v: any): string {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''))
  if (!Number.isFinite(n)) return '--'
  return n >= 100 ? n.toFixed(2) : String(parseFloat(n.toFixed(4)))
}
const allProtected = computed(() =>
  store.positions.length > 0 && store.positions.every((p: any) => p.protectionStatus === 'fully_protected' || Number(p.protectionCoveragePct || 0) >= 100)
)
</script>

<template>
  <div class="quantum-card p-4 sm:p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 pb-3.5 mb-3.5 border-b border-[#182644]">
      <div class="flex items-center space-x-2.5">
        <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse ring-4 ring-emerald-500/20"></span>
        <h2 class="text-sm sm:text-base font-black text-white font-mono uppercase tracking-wider">
          实盘多空持仓与动态风控
        </h2>
        <span class="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-[#080E1E] text-cyan-400 border border-cyan-500/30">
          {{ store.positions.length }} / 6 在途
        </span>
      </div>
      <div
        class="flex items-center space-x-1.5 text-xs font-mono px-3 py-1 rounded-xl border shadow-sm"
        :class="allProtected ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' : 'text-rose-400 bg-rose-500/10 border-rose-500/30'"
      >
        <ShieldCheck class="w-4 h-4 text-emerald-400" />
        <span class="font-bold">{{ allProtected ? '100% 交易所云端 OCO 全覆盖' : '⚠ 存在未保护仓位' }}</span>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="store.positions.length === 0" class="py-10 text-center bg-[#070D1C]/60 border border-dashed border-[#182644] rounded-2xl">
      <div class="w-10 h-10 mx-auto mb-2 rounded-xl bg-slate-800/40 border border-slate-700/40 flex items-center justify-center text-slate-400">
        <Lock class="w-5 h-5" />
      </div>
      <p class="text-xs text-slate-400 font-mono">当前无在途持仓，AI 决策中枢空仓等待最高确定性顺势信号</p>
    </div>

    <!-- Positions Table / List -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-left text-xs sm:text-sm font-mono whitespace-nowrap">
        <thead>
          <tr class="text-slate-400 text-xs uppercase tracking-wider border-b border-[#182644] bg-[#070D1C]/60">
            <th class="py-3 px-4 font-bold">标的 / 杠杆</th>
            <th class="py-3 px-4 font-bold">方向</th>
            <th class="py-3 px-4 font-bold">持仓量</th>
            <th class="py-3 px-4 font-bold">开仓均价</th>
            <th class="py-3 px-4 font-bold">最新市价</th>
            <th class="py-3 px-4 font-bold">保证金占用</th>
            <th class="py-3 px-4 font-bold">云端移动止损防线</th>
            <th class="py-3 px-4 text-right font-bold">未结浮盈 / ROI</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#182644]/60">
          <tr
            v-for="pos in store.positions"
            :key="pos.instId"
            class="hover:bg-[#0E172E]/80 transition-colors group"
          >
            <!-- 标的 / 杠杆 -->
            <td class="py-3.5 px-4">
              <div class="flex items-center space-x-2">
                <span class="font-black text-white text-base tracking-wide font-mono group-hover:text-blue-400 transition-colors">{{ pos.name }}</span>
                <span class="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-[#0D1832] text-cyan-300 border border-cyan-500/25">
                  {{ pos.lever }}x
                </span>
              </div>
            </td>

            <!-- 方向 -->
            <td class="py-3.5 px-4">
              <span
                class="px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center space-x-1 shadow-sm"
                :class="pos.side === 'long' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'"
              >
                <span>{{ pos.side === 'long' ? '🟢 做多 (LONG)' : '🔴 做空 (SHORT)' }}</span>
              </span>
            </td>

            <!-- 持仓量 -->
            <td class="py-3.5 px-4 text-slate-200 font-bold">
              {{ pos.pos }} <span class="text-xs text-slate-400 font-normal">张</span>
            </td>

            <!-- 开仓均价 -->
            <td class="py-3.5 px-4 text-slate-300 font-mono num-tabular">
              ${{ fmt2(pos.avgPx) }}
            </td>

            <!-- 标记市价 -->
            <td class="py-3.5 px-4 font-black text-white font-mono text-sm num-tabular">
              ${{ fmt4(pos.markPx ?? pos.last) }}
            </td>

            <!-- 实际保证金 -->
            <td class="py-3.5 px-4 text-slate-200 font-mono num-tabular">
              ${{ fmt2(pos.margin_usdt ?? pos.margin) }} <span class="text-xs text-slate-400">U</span>
            </td>

            <!-- 云端止损防线 -->
            <td class="py-3.5 px-4">
              <div
                class="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-[#070D1C] border"
                :class="pos.side === 'long' ? 'text-rose-400 border-rose-500/30' : 'text-emerald-400 border-emerald-500/30'"
              >
                <ShieldCheck class="w-3.5 h-3.5 shrink-0" />
                <span class="font-bold num-tabular">${{ pos.displayStop || '--' }}</span>
              </div>
            </td>

            <!-- 未结浮盈 / ROI -->
            <td class="py-3.5 px-4 text-right">
              <div
                class="text-sm sm:text-base font-black font-mono num-tabular"
                :class="Number(pos.upl) >= 0 ? 'text-emerald-400 text-glow-emerald' : 'text-rose-400 text-glow-rose'"
              >
                {{ Number(pos.upl) >= 0 ? '+' : '' }}{{ fmt2(pos.upl) }} U
              </div>
              <div
                class="text-[11px] font-bold font-mono"
                :class="Number(pos.uplRatio ?? pos.roi) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
              >
                {{ Number(pos.uplRatio ?? pos.roi) >= 0 ? '+' : '' }}{{ fmt2(pos.uplRatio ?? pos.roi) }}%
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
