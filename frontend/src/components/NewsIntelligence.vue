<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Newspaper, Flame, Activity, ExternalLink, ShieldAlert } from 'lucide-vue-next'

const store = useDashboardStore()
const intel = computed<any>(() => store.data?.news_intelligence || {})
const newsItems = computed<any[]>(() => intel.value.latest_news || [])
const coinsSentiment = computed<[string, any][]>(() => Object.entries(intel.value.coins_sentiment || {}))
const macro = computed<string>(() => intel.value.macro_sentiment || '--')
const breakerActive = computed<boolean>(() => !!intel.value.circuit_breaker?.active)

function labelClass(label: string) {
  if (label === 'bullish') return 'text-emerald-400 border-emerald-500/25 bg-emerald-500/10'
  if (label === 'bearish') return 'text-rose-400 border-rose-500/25 bg-rose-500/10'
  if (label === 'mixed') return 'text-amber-400 border-amber-500/25 bg-amber-500/10'
  return 'text-zinc-400 border-[#1A2232] bg-[#080B10]'
}
function labelCn(label: string) {
  return { bullish: '偏多', bearish: '偏空', mixed: '多空交织', neutral: '中性' }[label] || label || '中性'
}
function importanceClass(imp: string) {
  if (imp === 'high' || imp === 'critical') return 'text-rose-400'
  if (imp === 'medium') return 'text-amber-400'
  return 'text-[#707E94]'
}
function importanceCn(imp: string) {
  return { critical: '重大', high: '高', medium: '中', low: '低' }[imp] || (imp || '低')
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header Banner -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center space-x-3">
        <div class="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
          <Newspaper class="w-5 h-5" />
        </div>
        <div>
          <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">全网加密重大舆情与流动性情报</h2>
          <p class="text-xs text-[#707E94] font-mono">聚合扫描主流财经与链上异动 · 更新于 {{ intel.updated_at || '--' }} (北京时间)</p>
        </div>
      </div>
      <div class="flex items-center space-x-2">
        <span class="px-2.5 py-1 rounded border text-xs font-mono font-bold" :class="breakerActive ? 'text-rose-400 border-rose-500/30 bg-rose-500/10' : 'text-emerald-400 border-emerald-500/25 bg-emerald-500/10'">
          <ShieldAlert class="w-3 h-3 inline mr-1" />{{ breakerActive ? '黑天鹅熔断激活' : '常态监控' }}
        </span>
        <span class="px-2.5 py-1 rounded bg-[#080B10] border border-[#1A2232] text-xs font-mono text-zinc-300">宏观情绪：<strong class="text-amber-400">{{ macro }}</strong></span>
      </div>
    </div>

    <!-- Coin Sentiment Chips -->
    <div v-if="coinsSentiment.length" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
      <div v-for="[ccy, s] in coinsSentiment" :key="ccy" class="bg-[#0D121B] border border-[#1A2232] rounded-lg p-2.5">
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-bold text-white font-mono">{{ ccy }}</span>
          <span class="px-1.5 py-0.5 rounded border text-[9px] font-mono font-bold" :class="labelClass(s.label)">{{ labelCn(s.label) }}</span>
        </div>
        <div class="flex items-center justify-between text-[10px] font-mono text-[#707E94]">
          <span class="text-emerald-400">{{ s.bullish_ratio || '--' }}多</span>
          <span class="text-rose-400">{{ s.bearish_ratio || '--' }}空</span>
        </div>
        <div class="text-[9px] font-mono text-[#556677] mt-0.5">提及 {{ (s.mentions ?? 0).toLocaleString() }}</div>
      </div>
    </div>

    <!-- News List -->
    <div v-if="newsItems.length === 0" class="py-16 text-center border border-dashed border-[#1A2232] rounded-xl bg-[#0D121B]/50">
      <p class="text-xs text-[#707E94] font-mono">当前市场无破坏性突发黑天鹅或高热度异动，舆情情绪平稳。</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div
        v-for="item in newsItems"
        :key="item.id"
        class="bg-[#0D121B] border border-[#1A2232] hover:border-amber-500/30 rounded-xl p-4 transition-all"
      >
        <div class="flex items-start justify-between gap-2 mb-2">
          <div class="flex items-start space-x-1.5 min-w-0">
            <Flame class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" :class="importanceClass(item.importance)" />
            <span class="font-bold text-sm text-white leading-snug">{{ item.title }}</span>
          </div>
          <span class="text-[10px] font-mono text-[#707E94] shrink-0">{{ item.time }}</span>
        </div>
        <p class="text-xs text-zinc-300 leading-relaxed font-sans line-clamp-3">{{ item.summary }}</p>
        <div class="mt-3 pt-2 border-t border-[#1A2232] flex items-center justify-between text-[11px] font-mono text-[#707E94]">
          <span>热度: <strong :class="importanceClass(item.importance)">{{ importanceCn(item.importance) }}</strong></span>
          <span class="flex items-center space-x-2">
            <span>影响: <strong class="text-white">{{ (item.coins || []).join(', ') || 'ALL' }}</strong></span>
            <a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer" class="flex items-center text-blue-400 hover:text-blue-300">
              原文<ExternalLink class="w-3 h-3 ml-0.5" />
            </a>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
