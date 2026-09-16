<script setup lang="ts">
/**
 * LedgerDrawer.vue · DeepSeek Harness 风格单笔订单全生命周期穿透抽屉
 * 穿透展示：开平仓生命周期轨迹、费用精细构成、多维度盈亏归因、AI 委员会席位采纳溯源
 */
import { computed } from 'vue';
import { fmtDateTime, fmtNum, fmtSigned, fmtPct, fmtPrice, dirClass, cleanReason } from '../../utils/format';
import { pairLabel } from '../../utils/instId';
import { useI18n } from '../../composables/useI18n';
import {
  Coins,
  Landmark,
} from 'lucide-vue-next';
import BaseDrawer from '../base/BaseDrawer.vue';
import DirTag from '../base/DirTag.vue';
import CryptoLogo from './CryptoLogo.vue';

const props = defineProps<{ trade: any | null }>();
const emit = defineEmits<{ (e: 'close'): void }>();
const { t } = useI18n();

const x = computed(() => props.trade || {});
const holding = computed(() => x.value.status === 'holding');

/** 投委会溯源 */
const SEAT_LABELS: Record<string, string> = {
  trader_trend: 'A·顺势交易员',
  trader_momentum: 'B·动能突破员',
  trader_quant: 'C·数理套利员',
  cio: 'CIO 仲裁席',
  REJECT_ALL: '驳回全部',
};

const councilNote = computed(() => {
  const cc = x.value.council;
  if (!cc || !holding.value) return '';
  if (!cc.ran) return t('dash.ledger.council.degraded');
  const seat = SEAT_LABELS[String(cc.adopted_role || '')] || String(cc.adopted_role || '');
  return seat ? t('dash.ledger.council.adopted', undefined, { seat }) : t('dash.ledger.council.ran');
});

function feeAbs(v: unknown): string {
  if (v === null || v === undefined || v === '') return '--';
  const n = Number(v);
  return Number.isNaN(n) ? '--' : fmtNum(Math.abs(n), 4);
}

function feeSigned(v: unknown): string {
  const a = feeAbs(v);
  if (a === '--') return '--';
  // 批 24：0 不加负号 —— 否则「手续费 0」会渲染成 `-0.0000`（负零）
  return Number(a.replace(/,/g, '')) === 0 ? a : `-${a}`;
}

/* —— 数理快照可观测性（证据纪律）——
 * 与台账表格同源：后端逐单判定的 snapshot_observability。
 * PRICE_ONLY / NONE = 数理快照不可观测 —— 抽屉必须把「本笔未记录哪些量」和
 * 「禁止倒推编造」讲清楚，而不是留白（留白会被误读成「没有异常」）。 */
const obsTag = computed<string>(() => {
  const v = String(x.value?.snapshot_observability || 'NONE').toUpperCase();
  return ['DYNAMICS_OBSERVED', 'PARTIAL', 'PRICE_ONLY', 'NONE'].includes(v) ? v : 'NONE';
});
const obsUnobservable = computed(() => obsTag.value === 'NONE' || obsTag.value === 'PRICE_ONLY');
const obsLabel = computed(() => {
  if (obsTag.value === 'DYNAMICS_OBSERVED') return t('dash.ledger.observability.observed');
  if (obsTag.value === 'PARTIAL') return t('dash.ledger.observability.partial');
  if (obsTag.value === 'PRICE_ONLY') return t('dash.ledger.observability.priceOnly');
  return t('dash.ledger.observability.none');
});

const cells = computed(() => [
  { label: t('dash.ledger.col.entry'), value: fmtPrice(x.value.open_px), cls: 'text-[var(--ink-strong)]' },
  { label: t('dash.ledger.col.exit'), value: holding.value ? t('status.running') : fmtPrice(x.value.close_px), cls: holding.value ? 'text-[var(--ink-3)]' : 'text-[var(--ink-strong)]' },
  { label: t('dash.matrix.positions.col.margin'), value: fmtNum(x.value.margin, 2) + ' U', cls: 'text-[var(--ink-strong)]' },
  { label: t('dash.ledger.col.qty'), value: fmtNum(x.value.sz, 2) === '0.00' ? fmtNum(x.value.sz, 4) : fmtNum(x.value.sz, 2), cls: 'text-[var(--ink-strong)]' },
  { label: t('dash.ledger.lifecycle.grossPnl'), value: fmtSigned(x.value.gross_pnl), cls: dirClass(x.value.gross_pnl) },
  { label: t('dash.ledger.lifecycle.netPnl'), value: fmtSigned(x.value.net_pnl), cls: dirClass(x.value.net_pnl) },
  { label: t('dash.ledger.col.roi'), value: fmtPct(x.value.roi_pct), cls: dirClass(x.value.roi_pct) },
  { label: t('dash.ledger.col.fees'), value: feeSigned(x.value.fee), cls: feeSigned(x.value.fee) === '--' ? 'text-[var(--ink-3)]' : 'text-[var(--down)]' },
]);
</script>

<template>
  <BaseDrawer
    :open="!!trade"
    width="580px"
    :title="t('dash.ledger.lifecycle.title', undefined, { sym: pairLabel(x.inst || ''), dir: x.side || '' })"
    :subtitle="`${x.strategy || 'Momentum'} · ${x.lever || '10x'}${councilNote ? ' · ' + councilNote : ''}`"
    @close="emit('close')"
  >
    <div class="space-y-3.5">
      <!-- 订单状态与生命周期总览 -->
      <div class="dsh-card-sub p-3.5">
        <div class="flex items-center justify-between gap-2 border-b pb-2.5" style="border-color: var(--line-1)">
          <div class="flex items-center gap-2">
            <CryptoLogo :symbol="x.inst" :size="20" />
            <span class="text-sm font-bold font-mono text-[var(--ink-strong)]">{{ x.inst }}</span>
            <DirTag :dir="x.side" />
            <span
              class="rounded px-1.5 py-0.2 border text-3xs font-mono font-semibold"
              style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-2)"
            >
              {{ x.lever || '10x' }}
            </span>
          </div>
          <div class="flex items-center gap-1.5">
            <span
              class="rounded px-1.5 py-0.5 text-3xs font-semibold uppercase border"
              :class="holding ? 'text-[var(--warn)] border-[var(--warn-line)] bg-[var(--warn-bg)]' : 'text-[var(--ink-2)] border-[var(--line-1)] bg-[var(--surface-2)]'"
            >
              {{ holding ? t('status.running') : t('dash.ledger.status.closed') }}
            </span>
          </div>
        </div>

        <!-- 生命周期时间线 -->
        <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
          <div>
            <span class="text-3xs text-[var(--ink-3)] block">{{ t('dash.ledger.lifecycle.open') }}</span>
            <span class="num font-mono font-medium text-[var(--ink-1)] mt-0.5 block">{{ fmtDateTime(x.open_time) }}</span>
          </div>
          <div>
            <span class="text-3xs text-[var(--ink-3)] block">{{ t('dash.ledger.lifecycle.close') }}</span>
            <span class="num font-mono font-medium text-[var(--ink-1)] mt-0.5 block">{{ holding ? '--' : fmtDateTime(x.close_time) }}</span>
          </div>
          <div>
            <span class="text-3xs text-[var(--ink-3)] block">{{ t('dash.ledger.col.hold') }}</span>
            <span class="num font-mono font-medium text-[var(--ink-1)] mt-0.5 block">{{ x.duration || '--' }}</span>
          </div>
          <div>
            <span class="text-3xs text-[var(--ink-3)] block">{{ t('dash.ledger.col.exitReason') }}</span>
            <span class="text-[var(--ink-1)] mt-0.5 block leading-snug font-medium">{{ cleanReason(x.exit_reason) }}</span>
          </div>
        </div>
      </div>

      <!-- 数理快照可观测性（证据纪律：明确标注「不可观测」，严禁倒推编造） -->
      <div class="dsh-card-sub p-3.5">
        <div class="flex items-center justify-between gap-2">
          <h4 class="text-3xs font-bold uppercase tracking-wider text-[var(--ink-3)]">
            {{ t('dash.ledger.observability.title') }}
          </h4>
          <span
            class="rounded px-1.5 py-0.2 text-3xs font-semibold border"
            :class="obsUnobservable
              ? 'text-[var(--ink-2)] border-[var(--line-1)] bg-[var(--surface-2)]'
              : 'text-[var(--up)] border-[var(--up-line)] bg-[var(--up-bg)]'"
          >
            {{ obsLabel }}
          </span>
        </div>
        <p class="mt-2 text-3xs leading-relaxed" :class="obsUnobservable ? 'text-[var(--ink-2)]' : 'text-[var(--ink-3)]'">
          {{ t('dash.ledger.observability.missingFields') }}
        </p>
        <p class="mt-1.5 text-3xs leading-relaxed text-[var(--ink-3)]">
          {{ t('dash.ledger.observability.noBackfill') }}
        </p>
      </div>

      <!-- 8 核心财务指标矩阵 -->
      <div>
        <h4 class="text-3xs font-bold uppercase tracking-wider text-[var(--ink-3)] mb-1.5">
          {{ t('dash.ledger.lifecycle.grossPnl') }} & 财务指标
        </h4>
        <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <div
            v-for="c in cells"
            :key="c.label"
            class="dsh-card-sub px-3 py-2"
          >
            <p class="text-3xs text-[var(--ink-3)] truncate">{{ c.label }}</p>
            <p class="num font-mono mt-0.5 text-xs font-bold" :class="c.cls">{{ c.value }}</p>
          </div>
        </div>
      </div>

      <!-- 费用构成明细 -->
      <div class="dsh-card-sub p-3.5">
        <h4 class="text-3xs font-bold uppercase tracking-wider text-[var(--ink-3)] mb-2 flex items-center gap-1.5">
          <Coins class="h-3 w-3 text-[var(--accent)]" />
          {{ t('dash.ledger.lifecycle.feesBreak') }}
        </h4>
        <dl class="space-y-1.5 text-xs">
          <div class="flex justify-between items-center">
            <dt class="text-[var(--ink-3)]">{{ t('dash.ledger.lifecycle.makerFee') }} (Open)</dt>
            <dd class="num font-mono" :class="feeAbs(x.open_fee) === '--' ? 'text-[var(--ink-3)]' : 'text-[var(--down)]'">
              {{ feeAbs(x.open_fee) }}
            </dd>
          </div>
          <div class="flex justify-between items-center">
            <dt class="text-[var(--ink-3)]">{{ t('dash.ledger.lifecycle.takerFee') }} (Close)</dt>
            <dd class="num font-mono" :class="feeAbs(x.close_fee) === '--' ? 'text-[var(--ink-3)]' : 'text-[var(--down)]'">
              {{ feeAbs(x.close_fee) }}
            </dd>
          </div>
          <div v-if="x.funding_fee !== undefined" class="flex justify-between items-center">
            <dt class="text-[var(--ink-3)]">{{ t('dash.ledger.fundingTag') }} (Funding Fee)</dt>
            <dd
              class="num font-mono"
              :class="Number(x.funding_fee || 0) >= 0 ? 'text-[var(--up)]' : 'text-[var(--down)]'"
            >
              {{ Number(x.funding_fee || 0) >= 0 ? '+' : '' }}{{ fmtNum(x.funding_fee, 4) }}
            </dd>
          </div>
          <div class="flex justify-between items-center border-t pt-2" style="border-color: var(--line-1)">
            <dt class="font-bold text-[var(--ink-1)]">{{ t('common.total') }} 费用合计</dt>
            <dd class="num font-mono font-bold" :class="feeAbs(x.fee) === '--' ? 'text-[var(--ink-3)]' : 'text-[var(--down)]'">
              {{ feeAbs(x.fee) }}
            </dd>
          </div>
        </dl>
      </div>

      <!-- 投委会溯源与策略信息 -->
      <div v-if="x.council || x.strategy" class="dsh-card-sub p-3.5">
        <h4 class="text-3xs font-bold uppercase tracking-wider text-[var(--ink-3)] mb-2 flex items-center gap-1.5">
          <Landmark class="h-3 w-3 text-[var(--accent)]" />
          AI 投委会决策溯源
        </h4>
        <div class="space-y-2 text-xs">
          <div class="flex items-center justify-between">
            <span class="text-[var(--ink-3)]">执行策略</span>
            <span class="font-mono font-semibold text-[var(--ink-1)]">{{ x.strategy || 'Momentum Alpha' }}</span>
          </div>
          <div v-if="x.council?.adopted_role" class="flex items-center justify-between">
            <span class="text-[var(--ink-3)]">采纳席位</span>
            <span class="font-mono font-semibold text-[var(--up)]">
              {{ SEAT_LABELS[String(x.council.adopted_role)] || x.council.adopted_role }}
            </span>
          </div>
          <div v-if="councilNote" class="text-3xs text-[var(--ink-2)] rounded p-2" style="background-color: var(--surface-2)">
            {{ councilNote }}
          </div>
        </div>
      </div>
    </div>
  </BaseDrawer>
</template>
