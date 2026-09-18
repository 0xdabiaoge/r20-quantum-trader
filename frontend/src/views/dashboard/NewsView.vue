<script setup lang="ts">
/**
 * NewsView.vue · DeepSeek Harness 风格舆情快讯与重大黑天鹅情报看板
 * 包含：重大黑天鹅熔断预警带、币种情绪极性矩阵（支持点击联动筛选）、多源情报流（OKX/金十/全球宏观）与新鲜度监测
 */
import { computed, ref } from 'vue';
import {
  ExternalLink,
  ShieldAlert,
  Radio,
  X,
  Flame,
} from 'lucide-vue-next';
import { useDashboardStore } from '../../stores/dashboard';
import DataGate from '../../components/dashboard/DataGate.vue';
import { useI18n } from '../../composables/useI18n';
import { useRovingTabs } from '../../composables/useRovingTabs';
import { fmtHM } from '../../utils/format';
import BaseEmpty from '../../components/base/BaseEmpty.vue';
import TimeAgo from '../../components/base/TimeAgo.vue';
import CryptoLogo from '../../components/dashboard/CryptoLogo.vue';

const store = useDashboardStore();
const { t } = useI18n();

const selectedCoin = ref<string | null>(null);
const selectedSource = ref<string>('all');

const cryptoNewsCount = computed(() => rawNews.value.filter((item) =>
  (item.platforms || []).some((p: string) => ['Cointelegraph', 'CoinDesk', 'TheBlock', 'Binance'].some((k) => p.includes(k))) || (item.coins && item.coins.length > 0)
).length);

const jin10NewsCount = computed(() => rawNews.value.filter((item) =>
  (item.platforms || []).some((p: string) => p.includes('金十'))
).length);

const macroNewsCount = computed(() => rawNews.value.filter((item) =>
  (item.platforms || []).some((p: string) => p.includes('宏观') || p.includes('华尔街') || p.includes('新浪'))
).length);

const sourceFilters = computed(() => [
  { key: 'all', label: `${t('dash.news.filters.all')} (${rawNews.value.length})` },
  { key: 'crypto', label: `${t('dash.news.filters.crypto')} (${cryptoNewsCount.value})` },
  { key: 'jin10', label: `${t('dash.news.filters.jin10')} (${jin10NewsCount.value})` },
  { key: 'macro', label: `${t('dash.news.filters.macro')} (${macroNewsCount.value})` },
]);

/** 批 66：来源筛选分段的漫游 tabindex 与方向键导航。 */
const { setRef: setSourceRef, onKeydown: onSourceKey, roving: sourceRoving } = useRovingTabs(
  () => sourceFilters.value.length,
  (i) => { selectedSource.value = sourceFilters.value[i].key; },
);

const ni = computed<any>(() => (store.data as any)?.news_intelligence || {});
const macro = computed(() => ni.value.macro_sentiment || t('dash.news.macroDefault'));
const rawNews = computed<any[]>(() => ni.value.latest_news || []);
const freshAt = computed(() => ni.value.news_fresh_at || ni.value.timestamp || '');
const sourceReason = computed(() => ni.value.source_reason || t('dash.news.sourceReasonDefault'));
const isSourceActive = computed(() => ni.value.source_available === true);

// 黑天鹅熔断状态
const circuitBreaker = computed<any>(() => {
  const cb = ni.value.circuit_breaker;
  if (cb && typeof cb === 'object') return cb;
  return { active: false };
});
const isCbActive = computed(() => Boolean(circuitBreaker.value?.active));

// 币种情绪极性矩阵数据
const coins = computed(() => {
  const cs = ni.value.coins_sentiment || {};
  return Object.entries(cs)
    .map(([sym, v]: [string, any]) => {
      const bull = Math.max(0, Math.min(100, parseFloat(v.bullish_ratio) || 0));
      const bear = Math.max(0, Math.min(100, parseFloat(v.bearish_ratio) || 0));
      const score = typeof v.sentiment_factor_score === 'number' ? v.sentiment_factor_score : 0;
      return {
        sym,
        label: v.label || 'neutral',
        bull,
        bear,
        score,
        ls: v.long_short_ratio,
        // 真实入流快讯提及数：后端从本轮实际快讯逐条统计（缺失/未计算 → 0，
        // 绝不回落成「看起来饱满」的假样本量）。
        mentions: Number(v.mentions) || 0,
      };
    })
    .sort((a, b) => (b.mentions || 0) - (a.mentions || 0));
});

// 按选中币种与来源过滤后的快讯流
const filteredNews = computed(() => {
  let list = rawNews.value;
  if (selectedSource.value === 'crypto') {
    list = list.filter((item) =>
      (item.platforms || []).some((p: string) => ['Cointelegraph', 'CoinDesk', 'TheBlock', 'Binance'].some((k) => p.includes(k))) || (item.coins && item.coins.length > 0)
    );
  } else if (selectedSource.value === 'jin10') {
    list = list.filter((item) => (item.platforms || []).some((p: string) => p.includes('金十')));
  } else if (selectedSource.value === 'macro') {
    list = list.filter((item) => (item.platforms || []).some((p: string) => p.includes('宏观') || p.includes('华尔街') || p.includes('新浪')));
  } else if (selectedSource.value !== 'all') {
    list = list.filter((item) => (item.platforms || []).some((p: string) => p.includes(selectedSource.value)));
  }
  if (!selectedCoin.value) return list;
  const target = selectedCoin.value.toUpperCase();
  return list.filter((item) => {
    const coinList = (item.coins || []).map((c: string) => String(c).toUpperCase());
    if (coinList.includes(target)) return true;
    const title = String(item.title || '').toUpperCase();
    const summary = String(item.summary || '').toUpperCase();
    return title.includes(target) || summary.includes(target);
  });
});

function toggleCoinFilter(sym: string) {
  if (selectedCoin.value === sym) {
    selectedCoin.value = null;
  } else {
    selectedCoin.value = sym;
  }
}
</script>

<template>
  <div class="space-y-3">
    <!-- 页头 -->
    <div
      class="flex flex-wrap items-center justify-between gap-2 border-b pb-2.5"
      style="border-color: var(--line-1)"
    >
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-sm font-bold tracking-tight text-[var(--ink-strong)] flex items-center gap-1.5">
            <Radio class="h-4 w-4 text-[var(--accent)]" />
            {{ t('dash.news.title') }}
          </h1>
          <span
            class="rounded px-1.5 py-0.5 border text-3xs font-mono font-medium"
            style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-2)"
          >
            {{ t('dash.news.count', undefined, { n: rawNews.length }) }}
          </span>
          <span
            class="rounded px-1.5 py-0.5 border text-3xs font-medium"
            :class="macro.includes('多') ? 'text-[var(--up)] border-[var(--up-line)] bg-[var(--up-bg)]' : macro.includes('空') ? 'text-[var(--down)] border-[var(--down-line)] bg-[var(--down-bg)]' : 'text-[var(--ink-2)] border-[var(--line-1)] bg-[var(--surface-2)]'"
          >
            {{ macro }}
          </span>
        </div>
        <p class="text-3xs text-[var(--ink-3)] mt-0.5">
          {{ t('dash.news.desc') }}
        </p>
      </div>

      <!-- 信源状态与新鲜度 -->
      <div class="flex flex-wrap items-center gap-1.5 max-w-full min-w-0">
        <!-- 批 114：长信源文案在移动端（390px）增加 max-w-full 与 truncate，避免胶囊撑破视口溢出 68px -->
        <span class="dsh-pill max-w-full min-w-0" :title="sourceReason">
          <span class="dsh-status-dot" :class="isSourceActive ? 'active' : 'warn'" aria-hidden="true" />
          <span class="text-[var(--ink-2)] truncate min-w-0">{{ isSourceActive ? sourceReason : t('status.attention') }}</span>
        </span>
        <!-- 批 73：信源**非活跃**时胶囊只显示"需注意"，而"为什么需注意"（source_reason）
             此前只挂在上面的 :title 上 —— 恰好在最需要它的时刻键盘与触摸够不到。 -->
        <span
          v-if="!isSourceActive && sourceReason"
          class="text-3xs"
          style="color: var(--warn)"
          data-test="news-source-reason"
        >
          {{ sourceReason }}
        </span>
        <span v-if="freshAt" class="dsh-pill text-3xs font-mono text-[var(--ink-3)]">
          <span>{{ t('dash.news.freshness') }}</span>
          <TimeAgo :time="freshAt" />
        </span>
      </div>
    </div>

    <DataGate>
      <!-- 黑天鹅重大熔断预警卡 -->
      <div
        v-if="isCbActive"
        class="dsh-card p-3.5 border-[var(--down-line)] bg-[var(--down-bg)]"
      >
        <div class="flex items-start gap-3">
          <ShieldAlert class="h-5 w-5 text-[var(--down)] shrink-0 mt-0.5" />
          <div class="flex-1 space-y-1">
            <div class="flex items-center justify-between">
              <h3 class="text-xs font-bold text-[var(--down)] uppercase tracking-wider">
                {{ circuitBreaker.headline || t('dash.news.cb.headlineFallback') }}
              </h3>
              <span class="dsh-pill border-[var(--down-line)] text-[var(--down)] font-mono text-3xs">
                {{ t('dash.news.cb.badge') }}
              </span>
            </div>
            <p class="text-xs text-[var(--ink-1)] leading-body">
              {{ circuitBreaker.reason || circuitBreaker.detail || t('dash.news.cb.actionFallback') }}
            </p>
          </div>
        </div>
      </div>

      <!-- 币种情绪极性矩阵 (Coin Sentiment Polarity Matrix) -->
      <div v-if="coins.length" class="dsh-card overflow-hidden">
        <header class="dsh-card-header flex items-center justify-between">
          <div>
            <h2 class="text-xs font-bold uppercase tracking-wider text-[var(--ink-strong)] flex items-center gap-1.5">
              <Flame class="h-3.5 w-3.5 text-[var(--accent)]" />
              {{ t('dash.news.band.title') }}
            </h2>
            <p class="text-3xs text-[var(--ink-3)] mt-0.5">{{ t('dash.news.band.desc') }}</p>
          </div>

          <button type="button"
            v-if="selectedCoin"
            class="btn btn-ghost h-6 px-2 text-3xs font-medium cursor-pointer inline-flex items-center gap-1"
            @click="selectedCoin = null"
          >
            <X class="h-3 w-3" />
            <span>{{ t('dash.news.clearFilter') }} ({{ selectedCoin }})</span>
          </button>
        </header>

        <div class="grid grid-cols-2 gap-2 p-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          <button type="button"
            v-for="c in coins"
            :key="c.sym"
            class="dsh-card-sub p-2.5 text-left transition-all cursor-pointer relative"
            :class="selectedCoin === c.sym ? 'border-[var(--accent)] bg-[var(--surface-3)]' : 'hover:border-[var(--line-2)]'"
            :aria-pressed="selectedCoin === c.sym"
            @click="toggleCoinFilter(c.sym)"
          >
            <div class="flex items-center justify-between gap-1 mb-1.5">
              <div class="flex items-center gap-1.5">
                <CryptoLogo :symbol="c.sym" :size="16" />
                <span class="font-mono font-bold text-xs text-[var(--ink-strong)]">{{ c.sym }}</span>
              </div>
              <span
                class="rounded px-1 py-0.5 text-4xs font-mono font-semibold uppercase border"
                :class="c.label === 'bullish' ? 'text-[var(--up)] border-[var(--up-line)] bg-[var(--up-bg)]' : c.label === 'bearish' ? 'text-[var(--down)] border-[var(--down-line)] bg-[var(--down-bg)]' : 'text-[var(--ink-3)] border-[var(--line-1)] bg-[var(--surface-2)]'"
              >
                {{ c.label === 'bullish' ? t('common.dir.long') : c.label === 'bearish' ? t('common.dir.short') : t('common.dir.flat') }}
              </span>
            </div>

            <!-- 多空力量条 -->
            <div
              class="h-1.5 w-full overflow-hidden rounded bg-[var(--down)] flex mb-1.5"
              role="progressbar"
              :aria-valuenow="Math.round(c.bull)"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-label="`${c.sym} ${t('dash.news.ratioLabel')}`"
              :aria-valuetext="`${Math.round(c.bull)}% / ${Math.round(100 - c.bull)}%`"
            >
              <div
                class="h-full bg-[var(--up)] transition-all"
                :style="{ width: `${c.bull}%` }"
              />
            </div>

            <div class="flex justify-between text-4xs font-mono text-[var(--ink-3)]">
              <span class="text-[var(--up)]">{{ t('dash.news.pctBull', undefined, { n: c.bull.toFixed(0) }) }}</span>
              <!-- 中位指标：多空账户比来自 OKX Rubik（真实端点）。绝不显示
                   虚构的「100 篇」样本量；仅在确有快讯提及该币时才追加篇数。 -->
              <span :title="t('dash.news.ratioHint')">{{ t('dash.news.ratioLabel') }} {{ c.ls || '--' }}<template v-if="c.mentions > 0"> · {{ t('dash.news.mentions', undefined, { n: c.mentions }) }}</template></span>
              <span class="text-[var(--down)]">{{ t('dash.news.pctBear', undefined, { n: c.bear.toFixed(0) }) }}</span>
            </div>
          </button>
        </div>
      </div>

      <!-- 舆情快讯情报流 -->
      <div class="dsh-card overflow-hidden min-h-[480px] flex flex-col">
        <!-- 筛选栏 -->
        <header class="dsh-card-header flex flex-wrap items-center justify-between gap-2">
          <div class="seg" role="tablist" :aria-label="t('dash.news.feed.source')">
            <button
              v-for="(f, fi) in sourceFilters"
              :key="f.key"
              :ref="setSourceRef(fi)"
              type="button"
              role="tab"
              :aria-selected="selectedSource === f.key"
              :tabindex="sourceRoving(selectedSource === f.key)"
              :class="{ 'seg-on': selectedSource === f.key }"
              @click="selectedSource = f.key"
              @keydown="onSourceKey($event, fi)"
            >
              {{ f.label }}
            </button>
          </div>

          <div class="text-3xs text-[var(--ink-3)] font-mono">
            {{ t('dash.news.countNews', undefined, { a: filteredNews.length, b: rawNews.length }) }}
          </div>
        </header>

        <!-- 空态 -->
        <BaseEmpty v-if="!filteredNews.length" class="flex-1 flex items-center justify-center py-12" :text="t('dash.news.feed.empty')" />

        <!-- 快讯卡片列表 -->
        <div v-else class="divide-y flex-1" style="border-color: var(--line-1)">
          <article
            v-for="item in filteredNews"
            :key="item.id || item.title"
            class="p-4 transition-colors hover:bg-[var(--surface-2)] flex flex-col gap-2"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2 flex-wrap">
                <!-- 时间 -->
                <span class="num font-mono text-xs font-semibold text-[var(--ink-strong)]">
                  {{ fmtHM(item.timestamp || item.time) }}
                </span>

                <!-- 重要度 -->
                <span
                  v-if="item.importance === 'high'"
                  class="rounded px-1.5 py-0.5 text-4xs font-mono font-bold uppercase text-[var(--down)] border border-[var(--down-line)] bg-[var(--down-bg)]"
                >
                  HIGH
                </span>

                <!-- 来源渠道 -->
                <span
                  v-for="p in (item.platforms || [])"
                  :key="p"
                  class="rounded px-1.5 py-0.5 text-4xs font-mono text-[var(--ink-2)] border border-[var(--line-1)] bg-[var(--surface-2)]"
                >
                  {{ p }}
                </span>

                <!-- 关联币种 -->
                <button
                  v-for="coin in (item.coins || [])"
                  :key="coin"
                  type="button"
                  class="rounded px-1.5 py-0.5 text-4xs font-mono font-bold text-[var(--accent)] border border-[var(--line-2)] cursor-pointer hover:bg-[var(--surface-3)]"
                  @click="toggleCoinFilter(coin)"
                >
                  ${{ coin }}
                </button>
              </div>

              <!-- 外链 -->
              <a
                v-if="item.url"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
                class="relative text-3xs text-[var(--ink-3)] hover:text-[var(--accent)] inline-flex items-center gap-1 transition-colors px-1 -mx-1 py-1 -my-1"
              >
                <span>{{ t('common.more') }}</span>
                <span class="sr-only">{{ t('common.opensInNewTab') }}</span>
                <ExternalLink class="h-3 w-3" aria-hidden="true" />
              </a>
            </div>

            <!-- 标题与正文 -->
            <h3 class="text-xs font-bold text-[var(--ink-strong)] leading-snug">
              {{ item.title }}
            </h3>
            <p v-if="item.summary" class="text-xs text-[var(--ink-2)] leading-body font-sans">
              {{ item.summary }}
            </p>
          </article>
        </div>

        <!-- 底部结束提示，消除移动端大幅留白错觉 -->
        <footer
          v-if="filteredNews.length"
          class="mt-auto p-3.5 text-center text-3xs text-[var(--ink-3)] font-mono flex items-center justify-center gap-2 border-t border-[var(--line-1)] bg-[var(--surface-1)]/40"
        >
          <span class="h-px w-8 bg-[var(--line-1)]" aria-hidden="true" />
          <span>{{ t('dash.news.feedEnd') }}</span>
          <span class="h-px w-8 bg-[var(--line-1)]" aria-hidden="true" />
        </footer>
      </div>
    </DataGate>
  </div>
</template>
