<script setup lang="ts">
/**
 * BaseStat.vue · DeepSeek Harness 风格 KPI 指标单元
 * 包含：微标头、大号等宽数理数值、动态变动副值、走势图插槽与可展开释义
 */
import { ref } from 'vue';

withDefaults(
  defineProps<{
    label: string;
    value: string;
    delta?: string;
    deltaTone?: 'up' | 'down' | 'muted' | 'warn';
    hint?: string;
  }>(),
  { deltaTone: 'muted' },
);

const showHint = ref(false);

const toneVar = {
  up: 'var(--up)',
  down: 'var(--down)',
  warn: 'var(--warn)',
  muted: 'var(--ink-2)',
} as const;
</script>

<template>
  <div class="group flex min-w-0 flex-col justify-center gap-1 overflow-hidden px-3.5 py-2.5 select-none" :title="hint">
    <div class="flex min-w-0 items-center justify-between gap-1">
      <span class="truncate text-3xs font-semibold uppercase tracking-wider text-[var(--ink-3)]">{{ label }}</span>
      <button
        v-if="hint"
        type="button"
        class="kpi-hint shrink-0 cursor-pointer opacity-0 group-hover:opacity-60 hover:!opacity-100"
        :aria-label="hint"
        :aria-expanded="showHint"
        @click.stop="showHint = !showHint"
      >
        i
      </button>
    </div>

    <div class="flex min-w-0 flex-wrap items-baseline justify-between gap-1">
      <span class="num font-mono truncate text-lg font-bold leading-tight text-[var(--ink-strong)]">{{ value }}</span>
      <div class="flex items-center gap-1.5 shrink-0">
        <span v-if="delta" class="num font-mono text-3xs font-semibold" :style="{ color: toneVar[deltaTone] }">{{ delta }}</span>
        <slot name="extra" />
      </div>
    </div>

    <p v-if="hint && showHint" class="text-4xs leading-snug font-sans text-[var(--ink-2)] mt-0.5">{{ hint }}</p>
  </div>
</template>

<style scoped>
.kpi-hint {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 13px;
  height: 13px;
  padding: 0;
  border-radius: 9999px;
  border: 1px solid var(--line-1);
  background: var(--surface-2);
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 9px;
  font-style: italic;
  font-weight: 700;
  line-height: 1;
  transition: all var(--dur-fast);
}
.kpi-hint:hover {
  background: var(--surface-3);
  color: var(--ink-1);
  border-color: var(--line-2);
}
</style>
