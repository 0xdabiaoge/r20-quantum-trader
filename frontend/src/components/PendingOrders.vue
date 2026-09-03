<script setup lang="ts">
import { useDashboardStore } from '../stores/dashboard'
import { Layers } from 'lucide-vue-next'

const store = useDashboardStore()
</script>

<template>
  <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-4 sm:p-5 shadow-lg">
    <div
      class="flex flex-wrap items-center justify-between gap-2"
      :class="store.pendingOrders.length > 0 ? 'pb-3.5 mb-3 border-b border-[#1A2232]' : ''"
    >
      <div class="flex items-center space-x-2.5">
        <Layers class="w-4 h-4 text-blue-400" />
        <h2 class="text-sm sm:text-base font-bold text-white font-mono uppercase tracking-wide">在途限价挂单监控 (Maker)</h2>
        <span class="px-2 py-0.5 rounded text-xs font-mono font-bold bg-[#0A0D14] text-blue-400 border border-blue-500/20">
          {{ store.pendingOrders.length }} 笔在途
        </span>
      </div>
      <span class="text-xs text-[#707E94] font-mono hidden sm:inline">被动撮合成交，赚取负手续费 Rebate</span>
    </div>

    <!-- Empty State: Compact & Tidy -->
    <div
      v-if="store.pendingOrders.length === 0"
      class="mt-3 py-3 px-4 text-center bg-[#0A0D14]/40 border border-dashed border-[#1A2232] rounded-lg"
    >
      <p class="text-xs text-[#707E94] font-mono">当前无在途限价挂单 · 挂单池就绪 (AI 动态毫秒级报单与撤单重挂)</p>
    </div>

    <!-- Table -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-left text-xs sm:text-sm font-mono whitespace-nowrap">
        <thead>
          <tr class="text-[#8A99AD] text-xs uppercase tracking-wider border-b border-[#1A2232] bg-[#0A0D14]/40">
            <th class="py-3 px-4 font-semibold">订单号</th>
            <th class="py-3 px-4 font-semibold">标的</th>
            <th class="py-3 px-4 font-semibold">操作类型</th>
            <th class="py-3 px-4 font-semibold">挂单限价</th>
            <th class="py-3 px-4 font-semibold">委托数量</th>
            <th class="py-3 px-4 font-semibold">挂单时间</th>
            <th class="py-3 px-4 text-right font-semibold">状态</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#1A2232]/50">
          <tr
            v-for="ord in store.pendingOrders"
            :key="ord.ordId"
            class="hover:bg-[#141B26]/70 transition-colors"
          >
            <td class="py-3 px-4 text-[#707E94] font-mono">{{ ord.ordId }}</td>
            <td class="py-3 px-4 font-extrabold text-white text-sm">{{ ord.name || ord.instId }}</td>
            <td class="py-3 px-4">
              <span
                class="px-2.5 py-1 rounded text-xs font-bold inline-flex items-center space-x-1 shadow-sm"
                :class="ord.side === 'buy' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'"
              >
                <span>{{ ord.side === 'buy' ? '买入开多' : '卖出开空' }}</span>
              </span>
            </td>
            <td class="py-3 px-4 text-white font-mono font-bold">${{ ord.px }}</td>
            <td class="py-3 px-4 text-zinc-200">{{ ord.sz }} 张</td>
            <td class="py-3 px-4 text-[#707E94]">
              {{ ord.cTime ? new Date(parseInt(ord.cTime)).toLocaleTimeString() : '--' }}
            </td>
            <td class="py-3 px-4 text-right text-blue-400 font-bold">待撮合</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
