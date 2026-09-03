<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { ShieldCheck, ArrowUpRight, ArrowDownRight, Clock, AlertCircle } from 'lucide-vue-next'

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
  <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center space-x-2">
        <div class="w-2 h-2 rounded-full bg-emerald-400"></div>
        <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">当前实盘持仓与风控</h2>
        <span class="text-xs text-[#707E94] font-mono">({{ store.positions.length }}/6)</span>
      </div>
      <div class="flex items-center space-x-1.5 text-xs font-mono px-2.5 py-1 rounded border"
        :class="allProtected ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : 'text-rose-400 bg-rose-500/10 border-rose-500/20'">
        <ShieldCheck class="w-3.5 h-3.5" />
        <span>{{ allProtected ? '100% 交易所云端 OCO 全覆盖' : '⚠ 存在未保护仓位' }}</span>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="store.positions.length === 0" class="py-8 text-center border border-dashed border-[#1A2232] rounded-lg">
      <p class="text-xs text-[#707E94] font-mono">当前无在途持仓，AI 主脑空仓观望并执行挂单扫描中</p>
    </div>

    <!-- Positions Table / List -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-left text-xs font-mono">
        <thead>
          <tr class="text-[#707E94] border-b border-[#1A2232] pb-2">
            <th class="pb-2">标的 / 方向</th>
            <th class="pb-2">持仓张数</th>
            <th class="pb-2">持仓杠杆</th>
            <th class="pb-2">开仓均价</th>
            <th class="pb-2">标记市价</th>
            <th class="pb-2">实际保证金</th>
            <th class="pb-2">云端止损线</th>
            <th class="pb-2 text-right">未结浮动盈亏</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#1A2232]/50">
          <tr v-for="pos in store.positions" :key="pos.instId" class="hover:bg-[#121824]/50 transition-colors">
            <!-- Symbol & Direction -->
            <td class="py-2.5 flex items-center space-x-1.5">
              <span class="font-bold text-white">{{ pos.name }}</span>
              <span
                class="px-1.5 py-0.5 rounded text-[10px] font-extrabold"
                :class="pos.side === 'long' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'"
              >
                {{ pos.side === 'long' ? '做多' : '做空' }}
              </span>
            </td>

            <td class="py-2.5 text-zinc-300">{{ pos.pos }} 张</td>
            <td class="py-2.5 text-zinc-300">{{ pos.lever }}x</td>
            <td class="py-2.5 text-zinc-300">{{ fmt2(pos.avgPx) }}</td>
            <td class="py-2.5 text-white font-bold">{{ fmt4(pos.markPx ?? pos.last) }}</td>
            <td class="py-2.5 text-zinc-300">{{ fmt2(pos.margin_usdt ?? pos.margin) }} U</td>
            <td class="py-2.5 font-bold" :class="pos.side === 'long' ? 'text-rose-400' : 'text-emerald-400'">
              {{ pos.displayStop || '--' }}
            </td>
            <!-- UPL: uplRatio already arrives as a percentage, do not rescale -->
            <td class="py-2.5 text-right font-bold" :class="num(pos.upl) >= 0 ? 'text-emerald-400' : 'text-rose-400'">
              {{ num(pos.upl) >= 0 ? '+' : '' }}{{ fmt2(pos.upl) }} U
              <span class="text-[10px]">({{ num(pos.uplRatio) >= 0 ? '+' : '' }}{{ fmt2(pos.uplRatio) }}%)</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
