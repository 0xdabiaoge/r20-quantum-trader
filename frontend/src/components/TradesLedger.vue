<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Receipt, Calendar, ArrowUpRight, ArrowDownRight, CheckCircle2 } from 'lucide-vue-next'

const store = useDashboardStore()
const trades = computed(() => store.data?.trades || [])
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
          <Receipt class="w-5 h-5" />
        </div>
        <div>
          <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">完整成交台账与生命周期履历</h2>
          <p class="text-xs text-[#707E94] font-mono">真实撮合成交记录，扣除交易所手续费与资金费率净额</p>
        </div>
      </div>
      <div class="text-xs font-mono text-zinc-400">
        累计归档笔数: <strong class="text-white">{{ trades.length }}</strong>
      </div>
    </div>

    <!-- Trades Table -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
      <div v-if="trades.length === 0" class="py-12 text-center text-xs font-mono text-[#707E94]">
        暂无平仓历史交易记录
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs font-mono">
          <thead>
            <tr class="text-[#707E94] border-b border-[#1A2232] pb-2">
              <th class="pb-2">平仓时间</th>
              <th class="pb-2">标的</th>
              <th class="pb-2">方向</th>
              <th class="pb-2">开仓价</th>
              <th class="pb-2">平仓价</th>
              <th class="pb-2">张数</th>
              <th class="pb-2">占用保证金</th>
              <th class="pb-2 text-right">已结净盈亏</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#1A2232]/50">
            <tr v-for="(t, idx) in trades" :key="idx" class="hover:bg-[#121824]/50">
              <td class="py-2.5 text-[#707E94]">{{ t.close_time || t.time || '--' }}</td>
              <td class="py-2.5 font-bold text-white">{{ t.name || t.instId }}</td>
              <td class="py-2.5">
                <span
                  class="px-1.5 py-0.5 rounded text-[10px] font-bold"
                  :class="t.side === 'long' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'"
                >
                  {{ t.side === 'long' ? '多头' : '空头' }}
                </span>
              </td>
              <td class="py-2.5 text-zinc-300">{{ t.open_px || t.avgPx || '--' }}</td>
              <td class="py-2.5 text-white font-bold">{{ t.close_px || '--' }}</td>
              <td class="py-2.5 text-zinc-300">{{ t.sz || t.pos || '--' }}</td>
              <td class="py-2.5 text-zinc-300">{{ t.margin ? parseFloat(t.margin).toFixed(2) + ' U' : '--' }}</td>
              <td
                class="py-2.5 text-right font-bold"
                :class="(parseFloat(t.pnl || t.net_pnl || 0) >= 0) ? 'text-emerald-400' : 'text-rose-400'"
              >
                {{ parseFloat(t.pnl || t.net_pnl || 0) >= 0 ? '+' : '' }}{{ (parseFloat(t.pnl || t.net_pnl || 0)).toFixed(2) }} U
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
