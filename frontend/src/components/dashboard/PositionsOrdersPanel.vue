<script setup lang="ts">
/**
 * PositionsOrdersPanel.vue · DeepSeek Harness 开发者工作台持仓与挂单面板
 * 侧栏/工位双向联动，低饱和黑白/深灰主题，高密度表格与清晰订单状态
 */
import { computed, ref } from 'vue';
import { useDashboardStore } from '../../stores/dashboard';
import { useI18n } from '../../composables/useI18n';
import { fmtNum, fmtSigned, fmtPct, fmtPrice, arrow } from '../../utils/format';
import { venueToneCls } from '../../utils/venueMeta';
import { ShieldCheck, ShieldAlert } from 'lucide-vue-next';
import BaseSegmented from '../base/BaseSegmented.vue';
import BaseEmpty from '../base/BaseEmpty.vue';
import DirTag from '../base/DirTag.vue';
import TimeAgo from '../base/TimeAgo.vue';

const emit = defineEmits<{ (e: 'pick-symbol', instId: string): void }>();

const store = useDashboardStore();
const { t } = useI18n();

const tab = ref<'positions' | 'orders'>('positions');

type VenueFilter = 'all' | 'okx' | 'binance' | 'gate';
const selectedVenue = ref<VenueFilter>('all');

const positions = computed(() => store.positions);
const orders = computed(() => store.pendingOrders);

function getVenueOf(item: any): string {
  const v = String(item?.venue || item?.exchange || '').toLowerCase();
  if (v.includes('binance')) return 'binance';
  if (v.includes('gate')) return 'gate';
  return 'okx';
}

function getModeOf(item: any): 'LIVE' | 'DEMO' {
  if (item?.account_mode) return item.account_mode.toUpperCase() === 'LIVE' ? 'LIVE' : 'DEMO';
  if (item?.environment) return item.environment.toLowerCase() === 'live' ? 'LIVE' : 'DEMO';
  if (item?.is_simulated !== undefined) return item.is_simulated ? 'DEMO' : 'LIVE';
  return 'LIVE';
}

const filteredPositions = computed(() => {
  if (selectedVenue.value === 'all') return positions.value;
  return positions.value.filter((p) => getVenueOf(p) === selectedVenue.value);
});

const filteredOrders = computed(() => {
  if (selectedVenue.value === 'all') return orders.value;
  return orders.value.filter((o) => getVenueOf(o) === selectedVenue.value);
});

function posPnl(p: any): number {
  return Number(p.upl ?? 0);
}
function posRoi(p: any): number {
  return Number(p.roi_pct ?? p.uplRatio ?? 0);
}
function ocoOk(p: any): boolean {
  return p.cloud_oco_verified !== false && p.protectionStatus !== 'unprotected';
}
function orderDir(o: any): 'long' | 'short' {
  return String(o.posSide || (o.side === 'buy' ? 'long' : 'short')).toLowerCase() as any;
}
function symOf(x: { instId?: string; name?: string }): string {
  return x.name || String(x.instId || '').split('-')[0];
}
</script>

<template>
  <div class="dsh-card pop-panel flex h-full max-h-[58dvh] flex-col overflow-hidden xl:max-h-none">
    <!-- 面板头部：选项卡与场所过滤条 -->
    <div class="dsh-card-header flex flex-col sm:flex-row sm:items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <BaseSegmented
          v-model="tab"
          :options="[
            { value: 'positions', label: `${t('dash.matrix.positions.tab')} ${filteredPositions.length}` },
            { value: 'orders', label: `${t('dash.matrix.orders.tab')} ${filteredOrders.length}` },
          ]"
        />
        <span v-if="tab === 'positions' && !filteredPositions.length" class="text-3xs text-[var(--ink-3)] hidden sm:block">
          {{ t('dash.matrix.positions.aiManaged') }}
        </span>
      </div>

      <!-- 交易所过滤小胶囊 -->
      <div class="seg w-full sm:w-auto">
        <button
          v-for="v in [
            { key: 'all', label: t('common.all') },
            { key: 'okx', label: 'OKX' },
            { key: 'binance', label: 'Binance' },
            { key: 'gate', label: 'Gate' },
          ]"
          :key="v.key"
          :class="{ 'seg-on': selectedVenue === v.key }"
          @click="selectedVenue = v.key as any"
        >
          {{ v.label }}
        </button>
      </div>
    </div>

    <!-- 持仓列表 -->
    <div v-if="tab === 'positions'" class="scroll-y flex-1 min-h-0 overflow-x-auto">
      <BaseEmpty v-if="!filteredPositions.length" :text="t('dash.matrix.positions.empty')" />
      <table v-else class="table pop-table w-full">
        <thead>
          <tr>
            <th>{{ t('dash.matrix.positions.col.symbol') }}</th>
            <th class="col-num pop-col-entry">{{ t('dash.matrix.positions.col.entry') }}</th>
            <th class="col-num">{{ t('dash.matrix.positions.col.mark') }}</th>
            <th class="col-num pop-col-lev">{{ t('dash.matrix.positions.col.lev') }}</th>
            <th class="col-num">{{ t('dash.matrix.positions.col.pnl') }}</th>
            <th class="col-num">{{ t('dash.matrix.positions.col.sl') }} / {{ t('dash.matrix.positions.col.tp') }}</th>
            <th class="text-center">{{ t('dash.matrix.positions.col.oco') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in filteredPositions"
            :key="p.instId + p.side"
            class="clickable transition-colors hover:bg-[var(--surface-2)]"
            :title="t('dash.matrix.chart.pickHint')"
            @click="emit('pick-symbol', p.instId)"
          >
            <td>
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="num font-mono font-semibold text-xs text-[var(--ink-strong)]">{{ symOf(p) }}</span>
                <DirTag :dir="p.side" />
                <span
                  class="rounded px-1 py-0.5 text-3xs font-mono font-semibold uppercase border"
                  :class="venueToneCls(getVenueOf(p))"
                >
                  {{ getVenueOf(p).toUpperCase() }}
                </span>
                <span
                  class="rounded px-1 py-0.5 text-3xs font-mono font-medium border"
                  :class="getModeOf(p) === 'LIVE' ? 'text-[var(--up)] border-[var(--up-line)] bg-[var(--up-bg)]' : 'text-[var(--warn)] border-[var(--warn-line)] bg-[var(--warn-bg)]'"
                >
                  {{ getModeOf(p) }}
                </span>
              </div>
              <p v-if="p.stageDesc" class="text-3xs text-[var(--ink-3)] leading-tight mt-0.5">{{ p.stageDesc }}</p>
            </td>
            <td class="col-num font-mono pop-col-entry">{{ fmtPrice(p.avgPx) }}</td>
            <td class="col-num font-mono">{{ fmtPrice(p.markPx ?? p.last) }}</td>
            <td class="col-num font-mono pop-col-lev">{{ p.lever }}x</td>
            <td class="col-num font-mono" :class="posPnl(p) >= 0 ? 'up' : 'down'">
              {{ arrow(posPnl(p)) }} {{ fmtSigned(posPnl(p)) }}
              <span class="text-3xs block text-[var(--ink-3)]">{{ fmtPct(posRoi(p)) }}</span>
            </td>
            <td class="col-num font-mono text-[var(--ink-3)]">
              <span class="down">{{ fmtPrice(p.exchangeSl ?? p.displayStop) }}</span>
              <span class="mx-1">/</span>
              <span class="up">{{ fmtPrice(p.exchangeTp ?? p.displayTakeProfit) }}</span>
            </td>
            <td class="text-center">
              <span
                v-if="ocoOk(p)"
                class="inline-flex items-center gap-1 text-3xs text-[var(--up)]"
                :title="t('dash.matrix.positions.ocoOk')"
              >
                <ShieldCheck class="h-3.5 w-3.5" />
                <span class="hidden sm:inline">{{ t('dash.matrix.positions.ocoOk') }}</span>
              </span>
              <span
                v-else
                class="inline-flex items-center gap-1 text-3xs text-[var(--warn)]"
                :title="t('dash.matrix.positions.ocoMissHint')"
              >
                <ShieldAlert class="h-3.5 w-3.5" />
                <span class="hidden sm:inline">{{ t('dash.matrix.positions.ocoMiss') }}</span>
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 挂单列表 -->
    <div v-else class="scroll-y flex-1 min-h-0 overflow-x-auto">
      <BaseEmpty v-if="!filteredOrders.length" :text="t('dash.matrix.orders.empty')" />
      <table v-else class="table pop-table w-full">
        <thead>
          <tr>
            <th>{{ t('dash.matrix.orders.col.symbol') }}</th>
            <th class="col-num">{{ t('dash.matrix.orders.col.price') }}</th>
            <th class="col-num">{{ t('dash.matrix.orders.col.qty') }}</th>
            <th class="col-num">{{ t('dash.matrix.orders.col.sl') }} / {{ t('dash.matrix.orders.col.tp') }}</th>
            <th class="pop-col-time">{{ t('dash.matrix.orders.col.placed') }}</th>
            <th class="text-center">{{ t('dash.matrix.orders.col.state') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="o in filteredOrders"
            :key="o.ordId"
            class="clickable transition-colors hover:bg-[var(--surface-2)]"
            :title="t('dash.matrix.chart.pickHint')"
            @click="emit('pick-symbol', o.instId)"
          >
            <td>
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="num font-mono font-semibold text-xs text-[var(--ink-strong)]">{{ symOf(o) }}</span>
                <DirTag :dir="orderDir(o)" />
                <span
                  class="rounded px-1 py-0.5 text-3xs font-mono font-semibold uppercase border"
                  :class="venueToneCls(getVenueOf(o))"
                >
                  {{ getVenueOf(o).toUpperCase() }}
                </span>
                <span
                  class="rounded px-1 py-0.5 text-3xs font-mono font-medium border"
                  :class="getModeOf(o) === 'LIVE' ? 'text-[var(--up)] border-[var(--up-line)] bg-[var(--up-bg)]' : 'text-[var(--warn)] border-[var(--warn-line)] bg-[var(--warn-bg)]'"
                >
                  {{ getModeOf(o) }}
                </span>
              </div>
            </td>
            <td class="col-num font-mono">{{ fmtPrice(o.px) }}</td>
            <td class="col-num font-mono">{{ fmtNum(Number(o.sz), 0) }}</td>
            <td class="col-num font-mono text-[var(--ink-3)]">
              <span class="down">{{ o.slTriggerPx ? fmtPrice(o.slTriggerPx) : '--' }}</span>
              <span class="mx-1">/</span>
              <span class="up">{{ o.tpTriggerPx ? fmtPrice(o.tpTriggerPx) : '--' }}</span>
            </td>
            <td class="pop-col-time text-3xs text-[var(--ink-3)]"><TimeAgo :time="Number(o.cTime) || o.cTime" /></td>
            <td class="text-center">
              <span class="inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-3xs border border-[var(--line-1)] bg-[var(--surface-2)] text-[var(--ink-2)]">
                {{ o.state === 'live' ? t('status.waiting') : o.state }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="filteredOrders.length" class="text-3xs text-[var(--ink-3)] border-t px-3.5 py-2" style="border-color: var(--line-1)">
        {{ t('dash.matrix.orders.aiManaged') }}
      </p>
    </div>
  </div>
</template>

<style scoped>
/* =========================================================================
   批 18 · 列显隐改跟「面板宽度」，不再跟「视口宽度」
   -------------------------------------------------------------------------
   缺陷（实测）：本面板在 1600px 视口下宽 433px，而列显隐用的是 Tailwind
   视口断点 —— `hidden 2xl:table-cell` 在 1600 ≥ 1536 时判定为「可见」，
   于是 7 列硬塞进 433px，表格宽 564px 被容器裁掉："止损 / 止盈"（风险
   关键列）只剩半个「止」字，且没有任何滚动提示。

   修法：面板自身作为容器（container-type: inline-size），列显隐与内边距
   改由容器宽度决定，并按「信息重要性」排序取舍：
     始终保留 标的 / 标记价 / 未实现盈亏 / 止损·止盈 / 云端防线
     ≥520px  再放出 开仓均价（与标记价高度冗余）
     ≥600px  再放出 杠杆（静态值）与挂单时间
   ========================================================================= */
.pop-panel {
  container-type: inline-size;
}

.pop-col-entry,
.pop-col-lev,
.pop-col-time {
  display: none;
}

@container (min-width: 520px) {
  .pop-col-entry,
  .pop-col-time {
    display: table-cell;
  }
}
@container (min-width: 600px) {
  .pop-col-lev {
    display: table-cell;
  }
}

/* 窄容器收紧单元格内边距：让「止损 / 止盈」也能一屏放下，不出现横向滚动 */
@container (max-width: 559px) {
  .pop-table th,
  .pop-table td {
    padding-left: var(--sp-4);
    padding-right: var(--sp-4);
  }
}

/* 极窄（手机）：仍可能出现横向滚动，此时把标的列钉在左侧，滚到哪都认得出是谁 */
@container (max-width: 419px) {
  .pop-table th:first-child,
  .pop-table td:first-child {
    position: sticky;
    left: 0;
    z-index: 1;
    background-color: var(--ds-color-bg-surface-card);
  }
  .pop-table tbody tr:hover td:first-child {
    background-color: var(--ds-color-bg-surface-2);
  }
}
</style>
