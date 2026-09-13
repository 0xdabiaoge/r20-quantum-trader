<script setup lang="ts">
/** 数据状态 chips：引擎 / 熔断 / 决策周期 / 最后更新 */
import { computed } from 'vue';
import { useDashboardStore } from '../../stores/dashboard';
import { useI18n } from '../../composables/useI18n';
import TimeAgo from '../base/TimeAgo.vue';

const store = useDashboardStore();
const { t } = useI18n();

const health = computed(() => (store.data as any)?.data_health || {});
const breaker = computed(() => (store.data as any)?.state_snapshot?.circuit_breaker || {});

const engine = computed(() => {
  if (!store.isConnected) return { dot: 'dot-down', cls: 'down', label: t('dash.shell.connLost') };
  const s = String(health.value.status || '').toUpperCase();
  if (s === 'LIVE') return { dot: 'dot-live', cls: '', label: t('status.live') };
  if (s === 'PARTIAL') return { dot: 'dot-warn', cls: '', label: t('status.attention') };
  if (s === 'NOT_READY') return { dot: 'dot-warn', cls: '', label: t('common.notConfigured') };
  if (s === 'STALE' || store.isStale) return { dot: 'dot-warn', cls: '', label: t('status.stale') };
  return { dot: 'dot-down', cls: '', label: t('status.offline') };
});
const updated = computed(() => store.lastUpdated);
// 批B(2026-09-13)：决策周期改为后端调度器真值（data_health.cycle_minutes），
// 此前写死 n:15 当事实展示——后端降频/改周期后界面照旧宣称，属 UI 谎报。
// 取不到一律不渲染该 chip（宁缺勿假）。
const cycleMinutes = computed<number | null>(() => {
  const v = Number((health.value as any)?.cycle_minutes);
  return Number.isFinite(v) && v > 0 ? v : null;
});
</script>

<template>
  <div class="flex items-center gap-2">
    <span v-if="breaker.active" class="chip" style="border-color: var(--down-line); color: var(--down)" :title="breaker.reason">
      <span class="dot dot-down" />
      {{ t('dash.shell.breaker') }}
    </span>
    <span class="chip">
      <span class="dot" :class="engine.dot" />
      {{ engine.label }}
    </span>
    <span v-if="cycleMinutes" class="chip hidden md:inline-flex">{{ t('dash.shell.cycle', undefined, { n: cycleMinutes }) }}</span>
    <span v-if="updated" class="chip hidden md:inline-flex">
      <span class="t-faint">{{ t('dash.shell.updatedLabel') }}</span>
      <TimeAgo :time="updated" />
    </span>
  </div>
</template>
