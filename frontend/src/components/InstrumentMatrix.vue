<script setup lang="ts">
import { ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { TrendingUp, TrendingDown, Activity, ArrowUpRight, Compass } from 'lucide-vue-next'
import FactorDetailModal from './FactorDetailModal.vue'

const store = useDashboardStore()
const selectedInstrument = ref<any | null>(null)
const drawerVisible = ref(false)

function openDetail(item: any) {
  selectedInstrument.value = item
  drawerVisible.value = true
}

function getActionStyle(action?: string) {
  if (action === 'BUY_LONG') {
    return {
      backgroundColor: 'var(--color-up-bg)',
      borderColor: 'var(--color-up-border)',
      color: 'var(--color-up)',
    }
  }
  if (action === 'SELL_SHORT') {
    return {
      backgroundColor: 'var(--color-down-bg)',
      borderColor: 'var(--color-down-border)',
      color: 'var(--color-down)',
    }
  }
  return {
    backgroundColor: 'var(--bg-badge)',
    borderColor: 'var(--border-subtle)',
    color: 'var(--text-muted)',
  }
}

function getActionLabel(action?: string) {
  if (action === 'BUY_LONG') return '顺势做多 BUY'
  if (action === 'SELL_SHORT') return '顺势做空 SELL'
  return '空仓等待 WAIT'
}
</script>

<template>
  <div class="space-y-3">
    <!-- Macro Summary Telemetry Strip -->
    <div
      class="rounded-xl border p-3.5 sm:p-4 flex items-start space-x-3 transition-colors shadow-xs"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <div
        class="w-7 h-7 rounded-lg flex items-center justify-center border shrink-0 mt-0.5"
        style="background-color: var(--color-brand-bg); border-color: var(--color-brand-border); color: var(--color-brand);"
      >
        <Compass class="w-4 h-4" />
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center space-x-2">
          <span class="text-xs font-bold font-mono uppercase tracking-wider" style="color: var(--color-brand);">
            宏观多周期推演基调 (Macro Assessment)
          </span>
          <span class="text-[10px] font-mono" style="color: var(--text-faint);">
            {{ store.data?.timestamp }}
          </span>
        </div>
        <p class="text-xs font-sans mt-0.5 leading-relaxed" style="color: var(--text-muted);">
          {{ store.macroAssessment }}
        </p>
      </div>
    </div>

    <!-- 6-Asset Quantitative Ticker Cards Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6 gap-3">
      <div
        v-for="item in store.factors"
        :key="item.instId"
        @click="openDetail(item)"
        class="rounded-xl border p-4 transition-all duration-150 flex flex-col justify-between cursor-pointer group shadow-xs"
        style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        :class="'hover:border-[var(--border-medium)] hover:bg-[var(--bg-card-hover)]'"
      >
        <!-- Top: Header Info -->
        <div>
          <div class="flex items-center justify-between pb-2.5 border-b" style="border-color: var(--border-subtle);">
            <div class="flex items-center space-x-1.5">
              <span class="font-mono font-black text-base tracking-wide" style="color: var(--text-main);">
                {{ item.name }}
              </span>
              <span class="text-[9px] font-mono px-1 py-0.2 rounded border" style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-faint);">
                SWAP
              </span>
            </div>
            <div class="text-right font-mono">
              <div class="text-sm font-black num-tabular" style="color: var(--text-main);">
                ${{ item.price }}
              </div>
              <div
                class="text-[10px] font-bold font-mono flex items-center justify-end space-x-0.5 num-tabular"
                :style="{ color: item.chg24h >= 0 ? 'var(--color-up)' : 'var(--color-down)' }"
              >
                <TrendingUp v-if="item.chg24h >= 0" class="w-3 h-3" />
                <TrendingDown v-else class="w-3 h-3" />
                <span>{{ item.chg24h >= 0 ? '+' : '' }}{{ item.chg24h }}%</span>
              </div>
            </div>
          </div>

          <!-- Calculus Telemetry Grid -->
          <div
            class="grid grid-cols-4 gap-1.5 my-3 py-2 px-2 rounded-lg border text-[11px] font-mono"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
          >
            <div>
              <div class="text-[9px] uppercase" style="color: var(--text-faint);">速度 v</div>
              <div
                class="font-bold num-tabular"
                :style="{ color: (item.calculus?.velocity_1h ?? 0) >= 0 ? 'var(--color-up)' : 'var(--color-down)' }"
              >
                {{ item.calculus?.velocity_1h ?? '--' }}
              </div>
            </div>
            <div>
              <div class="text-[9px] uppercase" style="color: var(--text-faint);">加速 a</div>
              <div class="font-bold num-tabular" style="color: var(--text-main);">
                {{ item.calculus?.accel_1h ?? '--' }}
              </div>
            </div>
            <div>
              <div class="text-[9px] uppercase" style="color: var(--text-faint);">冲击 j</div>
              <div class="font-bold num-tabular" style="color: var(--text-muted);">
                {{ item.calculus?.jerk_1h ?? '--' }}
              </div>
            </div>
            <div>
              <div class="text-[9px] uppercase" style="color: var(--text-faint);">ADX</div>
              <div class="font-bold num-tabular" style="color: var(--color-brand);">
                {{ item.adx_1h ?? '--' }}
              </div>
            </div>
          </div>

          <!-- Microstructure Flow -->
          <div class="flex items-center justify-between text-[10px] font-mono mb-2.5 px-0.5" style="color: var(--text-muted);">
            <span>聪明钱做多: <strong class="num-tabular" style="color: var(--text-main);">{{ item.smart_money?.weighted_long_pct ?? 50 }}%</strong></span>
            <span>净流: <strong class="num-tabular" style="color: var(--text-main);">{{ item.smart_money?.net_flow_usdt ?? '0 U' }}</strong></span>
          </div>
        </div>

        <!-- Bottom: Decision Status & Drawer Trigger -->
        <div class="pt-2 border-t" style="border-color: var(--border-subtle);">
          <div class="flex items-center justify-between">
            <span
              class="px-2 py-0.5 rounded text-[10px] font-bold font-mono border"
              :style="getActionStyle(item.decision?.action || item.action)"
            >
              {{ getActionLabel(item.decision?.action || item.action) }}
            </span>
            <div class="flex items-center space-x-1 text-xs font-mono font-bold" style="color: var(--text-muted);">
              <span class="text-[10px]" style="color: var(--text-faint);">置信:</span>
              <span class="num-tabular" style="color: var(--text-main);">{{ item.decision?.confidence || item.confidence || 0 }}%</span>
              <ArrowUpRight class="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition-opacity" />
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
