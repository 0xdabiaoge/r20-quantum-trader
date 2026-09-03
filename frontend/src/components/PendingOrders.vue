<script setup lang="ts">
import { useDashboardStore } from '../stores/dashboard'
import { Layers } from 'lucide-vue-next'

const store = useDashboardStore()
</script>

<template>
  <div class="quantum-card p-4 sm:p-5">
    <div
      class="flex flex-wrap items-center justify-between gap-2"
      :class="store.pendingOrders.length > 0 ? 'pb-3.5 mb-3 border-b border-[#182644]' : ''"
    >
      <div class="flex items-center space-x-2.5">
        <div class="w-6 h-6 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
          <Layers class="w-3.5 h-3.5" />
        </div>
        <h2 class="text-sm sm:text-base font-bold text-white font-mono uppercase tracking-wide">在途限价挂单监控 (Maker)</h2>
        <span class="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-[#0A1124] text-blue-400 border border-blue-500/20">
          {{ store.pendingOrders.length }} 笔在途
        </span>
      </div>
      <span class="text-xs text-slate-400 font-mono hidden sm:inline">被动撮合成交，赚取负手续费 Rebate</span>
    </div>

    <!-- Empty State: Compact & Tidy -->
    <div
      v-if="store.pendingOrders.length === 0"
      class="mt-2.5 py-3 px-4 text-center bg-[#070D1C]/50 border border-dashed border-[#182644] rounded-xl"
    >
      <p class="text-xs text-slate-400 font-mono">当前无在途限价挂单 · 挂单池就绪 (AI 动态毫秒级报单与撤单重挂)</p>
    </div>

    <!-- Table -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-left text-xs sm:text-sm font-mono whitespace-nowrap">
        <thead>
          <tr class="text-slate-400 text-xs uppercase tracking-wider border-b border-[#182644] bg-[#070D1C]/60">
            <th class="py-3 px-4 font-bold">订单号</th>
            <th class="py-3 px-4 font-bold">标的</th>
            <th class="py-3 px-4 font-bold">操作类型</th>
            <th class="py-3 px-4 font-bold">挂单限价</th>
            <th class="py-3 px-4 font-bold">委托数量</th>
            <th class="py-3 px-4 font-bold">挂单时间</th>
            <th class="py-3 px-4 text-right font-bold">状态</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#182644]/60">
          <tr
            v-for="ord in store.pendingOrders"
            :key="ord.ordId"
            class="hover:bg-[#0E172E]/80 transition-colors"
          >
            <td class="py-3 px-4 text-slate-400 font-mono text-xs">{{ ord.ordId }}</td>
            <td class="py-3 px-4 font-black text-white text-sm">{{ ord.name || ord.instId }}</td>
            <td class="py-3 px-4">
              <span
                class="px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center space-x-1 shadow-sm"
                :class="ord.side === 'buy' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'"
              >
                <span>{{ ord.side === 'buy' ? '买入开多' : '卖出开空' }}</span>
              </span>
            </td>
            <td class="py-3 px-4 text-white font-mono font-black num-tabular">${{ ord.px }}</td>
            <td class="py-3 px-4 text-slate-200 num-tabular">{{ ord.sz }} 张</td>
            <td class="py-3 px-4 text-slate-400">
              {{ ord.cTime ? new Date(parseInt(ord.cTime)).toLocaleTimeString() : '--' }}
            </td>
            <td class="py-3 px-4 text-right text-cyan-400 font-bold">待撮合</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
