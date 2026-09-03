<script setup lang="ts">
import { ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { TrendingUp, TrendingDown, Zap, ArrowUpRight } from 'lucide-vue-next'
import FactorDetailModal from './FactorDetailModal.vue'

const store = useDashboardStore()
const selectedInstrument = ref<any | null>(null)
const drawerVisible = ref(false)

function openDetail(item: any) {
  selectedInstrument.value = item
  drawerVisible.value = true
}

function getActionColor(action?: string) {
  if (action === 'BUY_LONG') return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
  if (action === 'SELL_SHORT') return 'text-rose-400 border-rose-500/30 bg-rose-500/10'
  return 'text-slate-400 border-slate-700/40 bg-slate-800/20'
}

function getActionLabel(action?: string) {
  if (action === 'BUY_LONG') return '多头做多'
  if (action === 'SELL_SHORT') return '空头做空'
  return '观望等待'
}
</script>

<template>
  <div class="space-y-3.5">
    <!-- Macro Summary Strip -->
    <div class="quantum-card p-4 flex items-start space-x-3.5">
      <div class="p-2.5 rounded-xl bg-gradient-to-tr from-blue-600/30 to-cyan-500/20 border border-blue-500/30 text-blue-400 shrink-0">
        <Zap class="w-4 h-4" />
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center space-x-2.5">
          <span class="text-xs font-black font-mono uppercase tracking-wider text-cyan-400">宏观多周期推演基调</span>
          <span class="text-[10px] font-mono text-slate-400">{{ store.data?.timestamp }}</span>
        </div>
        <p class="text-xs text-slate-200 font-sans mt-1 leading-relaxed">
          {{ store.macroAssessment }}
        </p>
      </div>
    </div>

    <!-- 6-Asset Cards Grid: 1 on mobile, 2 on sm, 3 on lg, 6 across on 2xl -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6 gap-3.5">
      <div
        v-for="item in store.factors"
        :key="item.instId"
        @click="openDetail(item)"
        class="quantum-card p-4 transition-all duration-200 flex flex-col justify-between cursor-pointer group hover:-translate-y-0.5"
      >
        <!-- Top: Symbol Header -->
        <div>
          <div class="flex items-center justify-between pb-2 border-b border-[#182644]">
            <div class="flex items-center space-x-2">
              <span class="font-black text-lg tracking-wide text-white font-mono group-hover:text-blue-400 transition-colors">
                {{ item.name }}
              </span>
              <span class="text-[10px] font-mono text-slate-400">{{ item.instId }}</span>
            </div>
            <div class="text-right font-mono">
              <div class="text-sm font-black text-white num-tabular">${{ item.price }}</div>
              <div
                class="text-[11px] font-bold flex items-center justify-end space-x-0.5"
                :class="item.chg24h >= 0 ? 'text-emerald-400' : 'text-rose-400'"
              >
                <TrendingUp v-if="item.chg24h >= 0" class="w-3 h-3" />
                <TrendingDown v-else class="w-3 h-3" />
                <span>{{ item.chg24h >= 0 ? '+' : '' }}{{ item.chg24h }}%</span>
              </div>
            </div>
          </div>

          <!-- Calculus Dynamics Metrics Grid -->
          <div class="grid grid-cols-4 gap-1.5 my-3 py-2 px-2.5 rounded-xl bg-[#060D1C] border border-[#182644]/70 text-[11px] font-mono">
            <div>
              <div class="text-slate-400 text-[9px] uppercase">速度 v</div>
              <div :class="(item.calculus?.velocity_1h ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'" class="font-bold num-tabular">
                {{ item.calculus?.velocity_1h ?? '--' }}
              </div>
            </div>
            <div>
              <div class="text-slate-400 text-[9px] uppercase">加速 a</div>
              <div class="text-white font-bold num-tabular">{{ item.calculus?.accel_1h ?? '--' }}</div>
            </div>
            <div>
              <div class="text-slate-400 text-[9px] uppercase">冲击 j</div>
              <div class="text-slate-300 font-bold num-tabular">{{ item.calculus?.jerk_1h ?? '--' }}</div>
            </div>
            <div>
              <div class="text-slate-400 text-[9px] uppercase">ADX</div>
              <div class="text-cyan-400 font-bold num-tabular">{{ item.adx_1h ?? '--' }}</div>
            </div>
          </div>

          <!-- Smart Money & Flow -->
          <div class="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-2.5 px-0.5">
            <span>聪明钱做多: <strong class="text-slate-200">{{ item.smart_money?.weighted_long_pct ?? 50 }}%</strong></span>
            <span>净流入: <strong class="text-slate-200">{{ item.smart_money?.net_flow_usdt ?? '0 U' }}</strong></span>
          </div>
        </div>

        <!-- Bottom: AI Decision & Setup Details -->
        <div class="pt-2.5 border-t border-[#182644]">
          <div class="flex items-center justify-between">
            <span
              class="px-2 py-0.5 rounded-lg text-[10px] font-bold font-mono border"
              :class="getActionColor(item.decision?.action || item.action)"
            >
              {{ getActionLabel(item.decision?.action || item.action) }}
            </span>
            <div class="flex items-center space-x-1 text-xs font-mono font-bold text-slate-300">
              <span class="text-[11px] text-slate-400">置信:</span>
              <span class="text-white">{{ item.decision?.confidence || item.confidence || 0 }}%</span>
              <ArrowUpRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-400 transition-colors" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Factor Detail Modal (Drawer) -->
    <FactorDetailModal
      v-if="drawerVisible && selectedInstrument"
      :visible="drawerVisible"
      :instrument="selectedInstrument"
      @close="drawerVisible = false"
    />
  </div>
</template>
