<script setup lang="ts">
/**
 * DataStatus.vue · DeepSeek Harness 风格引擎与数据健康状态指示器
 * 熔断检测、引擎在线状态、调度周期与实时数据更新心跳
 */
import { computed } from 'vue';
import { useDashboardStore } from '../../stores/dashboard';
import { useI18n } from '../../composables/useI18n';
import TimeAgo from '../base/TimeAgo.vue';

const store = useDashboardStore();
const { t } = useI18n();

const health = computed(() => (store.data as any)?.data_health || {});
const breaker = computed(() => (store.data as any)?.state_snapshot?.circuit_breaker || {});

const engine = computed(() => {
  if (!store.isConnected) return { dot: 'error', cls: 'down', label: t('dash.shell.connLost') };
  const s = String(health.value.status || '').toUpperCase();
  if (s === 'LIVE') return { dot: 'active', cls: '', label: t('status.live') };
  if (s === 'PARTIAL') return { dot: 'warn', cls: '', label: t('status.attention') };
  if (s === 'NOT_READY') return { dot: 'warn', cls: '', label: t('common.notConfigured') };
  if (s === 'STALE' || store.isStale) return { dot: 'warn', cls: '', label: t('status.stale') };
  return { dot: 'error', cls: '', label: t('status.offline') };
});
const updated = computed(() => store.lastUpdated);
const cycleMinutes = computed<number | null>(() => {
  const v = Number((health.value as any)?.cycle_minutes);
  return Number.isFinite(v) && v > 0 ? v : null;
});
</script>

<template>
  <div class="flex items-center gap-1.5">
    <span
      v-if="breaker.active"
      class="dsh-pill text-[var(--down)] border-[var(--down-line)] bg-[var(--down-bg)]"
      :title="breaker.reason"
    >
      <span class="dsh-status-dot error" aria-hidden="true" />
      {{ t('dash.shell.breaker') }}
    </span>

    <div
      class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-3xs font-mono border"
      style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-2)"
    >
      <span class="dsh-status-dot" :class="engine.dot" aria-hidden="true" />
      <span class="font-medium" style="color: var(--ink-1)">{{ engine.label }}</span>
      <span v-if="cycleMinutes" class="text-[var(--ink-3)]">· {{ cycleMinutes }}M</span>
      <span v-if="updated" class="hidden lg:inline text-[var(--ink-3)]">
        · <TimeAgo :time="updated" />
      </span>
    </div>
  </div>
</template>
