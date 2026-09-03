<script setup lang="ts">
import { useDashboardStore } from '../stores/dashboard'
import { TrendingUp, TrendingDown, Minus, Zap, Shield, HelpCircle } from 'lucide-vue-next'
import type { InstrumentFactor } from '../types/dashboard'

const store = useDashboardStore()

function getActionColor(action?: string) {
  if (action === 'BUY_LONG') return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
  if (action === 'SELL_SHORT') return 'text-rose-400 border-rose-500/30 bg-rose-500/10'
  return 'text-zinc-400 border-zinc-700/40 bg-zinc-800/20'
}

function getActionLabel(action?: string) {
  if (action === 'BUY_LONG') return '多头做多'
  if (action === 'SELL_SHORT') return '空头做空'
  return '观望等待'
}
</script>

<template>
  <div class="space-y-3">
    <!-- Macro Summary Strip -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-3.5 flex items-start space-x-3">
      <div class="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
        <Zap class="w-4 h-4" />
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center space-x-2">
          <span class="text-xs font-bold font-mono uppercase tracking-wider text-blue-400">宏观多周期推演基调</span>
          <span class="text-[10px] font-mono text-[#707E94]">{{ store.data?.timestamp }}</span>
        </div>
        <p class="text-xs text-zinc-300 font-sans mt-0.5 leading-relaxed">
          {{ store.macroAssessment }}
        </p>
      </div>
    </div>

    <!-- 6-Asset Cards Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      <div
        v-for="item in store.factors"
        :key="item.instId"
        class="bg-[#0D121B] border border-[#1A2232] hover:border-blue-500/30 rounded-xl p-4 transition-all duration-200 flex flex-col justify-between"
      >
        <!-- Top: Symbol Header -->
        <div>
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <span class="font-black text-base tracking-wide text-white font-mono">{{ item.name }}</span>
              <span class="text-[11px] font-mono text-[#707E94]">{{ item.instId }}</span>
            </div>
            <div class="text-right font-mono">
              <div class="text-sm font-bold text-white">${{ item.price }}</div>
              <div
                class="text-[11px] font-semibold flex items-center justify-end space-x-0.5"
                :class="item.chg24h >= 0 ? 'text-emerald-400' : 'text-rose-400'"
              >
                <TrendingUp v-if="item.chg24h >= 0" class="w-3 h-3" />
                <TrendingDown v-else class="w-3 h-3" />
                <span>{{ item.chg24h >= 0 ? '+' : '' }}{{ item.chg24h }}%</span>
              </div>
            </div>
          </div>

          <!-- Calculus Dynamics Metrics Grid -->
          <div class="grid grid-cols-4 gap-1.5 my-3 py-2 px-2.5 rounded-lg bg-[#080B10] border border-[#1A2232]/60 text-[11px] font-mono">
            <div>
              <div class="text-[#707E94] text-[10px]">一阶速度 v</div>
              <div :class="(item.calculus?.velocity_1h ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'" class="font-bold">
                {{ item.calculus?.velocity_1h ?? '--' }}
              </div>
            </div>
            <div>
              <div class="text-[#707E94] text-[10px]">二阶加速 a</div>
              <div class="text-white font-bold">{{ item.calculus?.accel_1h ?? '--' }}</div>
            </div>
            <div>
              <div class="text-[#707E94] text-[10px]">三阶冲击 j</div>
              <div class="text-zinc-300 font-bold">{{ item.calculus?.jerk_1h ?? '--' }}</div>
            </div>
            <div>
              <div class="text-[#707E94] text-[10px]">趋势强度 ADX</div>
              <div class="text-blue-400 font-bold">{{ item.adx_1h ?? '--' }}</div>
            </div>
          </div>

          <!-- Smart Money & Flow -->
          <div class="flex items-center justify-between text-[11px] font-mono text-[#707E94] mb-2 px-1">
            <span>聪明钱多空比: <strong class="text-zinc-300">{{ item.smart_money?.weighted_long_pct ?? 50 }}%</strong></span>
            <span>净流入: <strong class="text-zinc-300">{{ item.smart_money?.net_flow_usdt ?? '0 U' }}</strong></span>
          </div>
        </div>

        <!-- Bottom: AI Decision & Setup Details -->
        <div class="pt-2 border-t border-[#1A2232]/80">
          <div class="flex items-center justify-between mb-1.5">
            <span
              class="px-2 py-0.5 rounded text-[11px] font-bold font-mono border"
              :class="getActionColor(item.decision?.action)"
            >
              {{ getActionLabel(item.decision?.action) }}
            </span>
            <span v-if="item.decision?.confidence" class="text-xs font-mono font-bold text-zinc-300">
              置信度: {{ item.decision.confidence }}%
            </span>
          </div>

          <p class="text-xs text-zinc-300 line-clamp-2 leading-relaxed font-sans min-h-[32px]">
            {{ item.decision?.summary_reason || '模型多周期数据评估中，等待共振结构确认...' }}
          </p>

          <!-- Trade Parameter Setup (When not WAIT) -->
          <div
            v-if="item.decision && item.decision.action !== 'WAIT' && item.decision.entry_price"
            class="mt-2.5 p-2 rounded bg-blue-500/5 border border-blue-500/20 text-[11px] font-mono grid grid-cols-3 gap-1 text-center"
          >
            <div>
              <div class="text-[#707E94] text-[10px]">入场限价</div>
              <div class="text-white font-bold">{{ item.decision.entry_price }}</div>
            </div>
            <div>
              <div class="text-emerald-400/80 text-[10px]">止盈目标</div>
              <div class="text-emerald-400 font-bold">{{ item.decision.take_profit_price }}</div>
            </div>
            <div>
              <div class="text-rose-400/80 text-[10px]">止损防线</div>
              <div class="text-rose-400 font-bold">{{ item.decision.stop_loss_price }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
