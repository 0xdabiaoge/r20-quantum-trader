<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { ShieldCheck } from 'lucide-vue-next'

const store = useDashboardStore()

// Null-safe numeric formatting for exchange payloads (fields may be str/num/absent)
function num(v: any): number {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''))
  return Number.isFinite(n) ? n : 0
}
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
  <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-4 sm:p-5 shadow-lg">
    <div class="flex flex-wrap items-center justify-between gap-2 pb-3.5 mb-3 border-b border-[#1A2232]">
      <div class="flex items-center space-x-2.5">
        <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
        <h2 class="text-sm sm:text-base font-bold text-white font-mono uppercase tracking-wide">当前实盘持仓与风控</h2>
        <span class="px-2 py-0.5 rounded text-xs font-mono font-bold bg-[#0A0D14] text-blue-400 border border-blue-500/20">
          {{ store.positions.length }} / 6 在途
        </span>
      </div>
      <div
        class="flex items-center space-x-1.5 text-xs font-mono px-3 py-1 rounded-lg border shadow-sm"
        :class="allProtected ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : 'text-rose-400 bg-rose-500/10 border-rose-500/20'"
      >
        <ShieldCheck class="w-4 h-4" />
        <span class="font-bold">{{ allProtected ? '100% 交易所云端 OCO 全覆盖' : '⚠ 存在未保护仓位' }}</span>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="store.positions.length === 0" class="py-8 text-center bg-[#0A0D14]/40 border border-dashed border-[#1A2232] rounded-lg">
      <p class="text-xs text-[#707E94] font-mono">当前无在途持仓，AI 主脑空仓观望并执行挂单扫描中</p>
    </div>

    <!-- Positions Table / List -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-left text-xs sm:text-sm font-mono whitespace-nowrap">
        <thead>
          <tr class="text-[#8A99AD] text-xs uppercase tracking-wider border-b border-[#1A2232] bg-[#0A0D14]/40">
            <th class="py-3 px-4 font-semibold">标的 / 杠杆</th>
            <th class="py-3 px-4 font-semibold">方向</th>
            <th class="py-3 px-4 font-semibold">持仓张数</th>
            <th class="py-3 px-4 font-semibold">开仓均价</th>
            <th class="py-3 px-4 font-semibold">标记市价</th>
            <th class="py-3 px-4 font-semibold">实际保证金</th>
            <th class="py-3 px-4 font-semibold">云端止损防线</th>
            <th class="py-3 px-4 text-right font-semibold">未结浮盈 / ROI</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#1A2232]/50">
          <tr
            v-for="pos in store.positions"
            :key="pos.instId"
            class="hover:bg-[#141B26]/70 transition-colors group"
          >
            <!-- 标的 / 杠杆 -->
            <td class="py-3.5 px-4">
              <div class="flex items-center space-x-2">
                <span class="font-extrabold text-white text-sm tracking-wide">{{ pos.name }}</span>
                <span class="px-1.5 py-0.5 rounded text-[11px] font-mono font-bold bg-[#141B26] text-blue-300 border border-blue-500/20">
                  {{ pos.lever }}x
                </span>
              </div>
            </td>

            <!-- 方向 -->
            <td class="py-3.5 px-4">
              <span
                class="px-2.5 py-1 rounded text-xs font-bold inline-flex items-center space-x-1 shadow-sm"
                :class="pos.side === 'long' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'"
              >
                <span>{{ pos.side === 'long' ? '多头 BUY' : '空头 SELL' }}</span>
              </span>
            </td>

            <!-- 持仓张数 -->
            <td class="py-3.5 px-4 text-zinc-200 font-medium">
              {{ pos.pos }} <span class="text-xs text-[#707E94]">张</span>
            </td>

            <!-- 开仓均价 -->
            <td class="py-3.5 px-4 text-zinc-300 font-mono">
              ${{ fmt2(pos.avgPx) }}
            </td>

            <!-- 标记市价 -->
            <td class="py-3.5 px-4 font-extrabold text-white font-mono text-sm">
              ${{ fmt4(pos.markPx ?? pos.last) }}
            </td>

            <!-- 实际保证金 -->
            <td class="py-3.5 px-4 text-zinc-200 font-mono">
              ${{ fmt2(pos.margin_usdt ?? pos.margin) }} <span class="text-xs text-[#707E94]">U</span>
            </td>

            <!-- 云端止损防线 -->
            <td class="py-3.5 px-4">
              <div
                class="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-[#0A0D14] border"
                :class="pos.side === 'long' ? 'text-rose-400 border-rose-500/30' : 'text-emerald-400 border-emerald-500/30'"
              >
                <ShieldCheck class="w-3.5 h-3.5 shrink-0" />
                <span class="font-bold">${{ pos.displayStop || '--' }}</span>
              </div>
            </td>

            <!-- 未结浮盈 / ROI -->
            <td class="py-3.5 px-4 text-right">
              <div class="font-extrabold text-sm font-mono" :class="num(pos.upl) >= 0 ? 'text-emerald-400' : 'text-rose-400'">
                {{ num(pos.upl) >= 0 ? '+' : '' }}{{ fmt2(pos.upl) }} <span class="text-xs font-normal text-[#707E94]">USDT</span>
              </div>
              <div class="text-xs font-semibold font-mono" :class="num(pos.uplRatio) >= 0 ? 'text-emerald-400' : 'text-rose-400'">
                ({{ num(pos.uplRatio) >= 0 ? '+' : '' }}{{ fmt2(pos.uplRatio) }}%)
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
