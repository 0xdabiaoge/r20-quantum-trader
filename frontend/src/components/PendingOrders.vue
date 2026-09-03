<script setup lang="ts">
import { useDashboardStore } from '../stores/dashboard'
import { Clock, Layers } from 'lucide-vue-next'

const store = useDashboardStore()
</script>

<template>
  <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center space-x-2">
        <Layers class="w-4 h-4 text-blue-400" />
        <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">在途限价挂单监控 (Maker)</h2>
        <span class="text-xs text-[#707E94] font-mono">({{ store.pendingOrders.length }})</span>
      </div>
      <span class="text-xs text-[#707E94] font-mono">被动撮合成交，赚取负手续费 Rebate</span>
    </div>

    <!-- Empty -->
    <div v-if="store.pendingOrders.length === 0" class="py-6 text-center border border-dashed border-[#1A2232] rounded-lg">
      <p class="text-xs text-[#707E94] font-mono">当前无在途挂单</p>
    </div>

    <!-- Table -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-left text-xs font-mono">
        <thead>
          <tr class="text-[#707E94] border-b border-[#1A2232] pb-2">
            <th class="pb-2">订单号</th>
            <th class="pb-2">标的</th>
            <th class="pb-2">操作类型</th>
            <th class="pb-2">挂单价</th>
            <th class="pb-2">委托数量</th>
            <th class="pb-2">挂单时间</th>
            <th class="pb-2 text-right">状态</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#1A2232]/50">
          <tr v-for="ord in store.pendingOrders" :key="ord.ordId" class="hover:bg-[#121824]/50">
            <td class="py-2 text-[#707E94]">{{ ord.ordId }}</td>
            <td class="py-2 font-bold text-white">{{ ord.name || ord.instId }}</td>
            <td class="py-2">
              <span
                class="px-1.5 py-0.5 rounded text-[10px] font-bold"
                :class="ord.side === 'buy' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'"
              >
                {{ ord.side === 'buy' ? '买入开多' : '卖出开空' }}
              </span>
            </td>
            <td class="py-2 text-white font-bold">{{ ord.px }}</td>
            <td class="py-2 text-zinc-300">{{ ord.sz }} 张</td>
            <td class="py-2 text-[#707E94]">{{ ord.cTime ? new Date(parseInt(ord.cTime)).toLocaleTimeString() : '--' }}</td>
            <td class="py-2 text-right text-blue-400 font-bold">待撮合</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
