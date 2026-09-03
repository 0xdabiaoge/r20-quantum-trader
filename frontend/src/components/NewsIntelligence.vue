<script setup lang="ts">
import { useDashboardStore } from '../stores/dashboard'
import { Newspaper, Flame, Activity } from 'lucide-vue-next'

const store = useDashboardStore()
const newsItems = computed(() => store.data?.news_intelligence || [])
</script>

<script lang="ts">
import { computed } from 'vue'
</script>

<template>
  <div class="space-y-4">
    <!-- Header Banner -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
          <Newspaper class="w-5 h-5" />
        </div>
        <div>
          <h2 class="text-sm font-bold text-white font-mono uppercase tracking-wide">全网加密重大舆情与流动性情报</h2>
          <p class="text-xs text-[#707E94] font-mono">基于主流财经与链上异动聚合扫描，过滤低噪长尾噪音</p>
        </div>
      </div>
      <span class="px-2.5 py-1 rounded bg-[#080B10] border border-[#1A2232] text-xs font-mono text-zinc-400">
        AI 情绪过滤器：已启用
      </span>
    </div>

    <!-- News Grid / Empty -->
    <div v-if="!newsItems || newsItems.length === 0" class="py-16 text-center border border-dashed border-[#1A2232] rounded-xl bg-[#0D121B]/50">
      <p class="text-xs text-[#707E94] font-mono">当前市场无破坏性突发黑天鹅或高热度异动，舆情情绪平稳。</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div
        v-for="(item, idx) in newsItems"
        :key="idx"
        class="bg-[#0D121B] border border-[#1A2232] hover:border-amber-500/30 rounded-xl p-4 transition-all"
      >
        <div class="flex items-start justify-between gap-2 mb-2">
          <div class="flex items-center space-x-1.5">
            <Flame class="w-4 h-4 text-amber-400" />
            <span class="font-bold text-sm text-white">{{ item.title || item.headline }}</span>
          </div>
          <span class="text-[10px] font-mono text-[#707E94] shrink-0">{{ item.time || '--' }}</span>
        </div>
        <p class="text-xs text-zinc-300 leading-relaxed font-sans">{{ item.content || item.summary }}</p>
        <div class="mt-3 pt-2 border-t border-[#1A2232] flex items-center justify-between text-[11px] font-mono text-[#707E94]">
          <span>情绪倾向: <strong class="text-amber-400">{{ item.sentiment || '中性' }}</strong></span>
          <span>影响代币: <strong class="text-white">{{ item.related_assets?.join(', ') || 'ALL' }}</strong></span>
        </div>
      </div>
    </div>
  </div>
</template>
