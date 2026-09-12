<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { fmtDateTime } from '../../utils/format';
import { useI18n } from '../../composables/useI18n';
const { t } = useI18n();
const now = ref(new Date());
let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => { timer = setInterval(() => { now.value = new Date(); }, 1000); });
onBeforeUnmount(() => { if (timer) clearInterval(timer); });
</script>

<template>
  <time class="num whitespace-nowrap text-[10px] leading-tight" :datetime="now.toISOString()" :title="t('common.time.siteTimeTip')">
    <span class="hidden xl:inline">{{ fmtDateTime(now).slice(0, 11) }}</span>{{ fmtDateTime(now).slice(11) }}
    <span class="block text-center" style="color: var(--ink-3)">{{ t('common.time.beijingTime') }}</span>
  </time>
</template>
