<script setup lang="ts">
/** KPI 单元：标签 + 大数字 + 副值(涨跌) + 可选 sparkline。KPI 必带 Δ 或走势，禁裸数字。 */
import { ref } from 'vue';

withDefaults(
  defineProps<{
    label: string;
    value: string;
    /** 副值文本（已含符号），配合 deltaTone 上色 */
    delta?: string;
    deltaTone?: 'up' | 'down' | 'muted' | 'warn';
    hint?: string;
  }>(),
  { deltaTone: 'muted' },
);

/** 批D(2026-09-13)：口径说明原先只挂在容器 title 上——触屏没有 hover，等于不存在
 *  （而"今日已实现是几所合并口径"这类信息直接决定用户信不信这个数）。改为可点按的 ⓘ：
 *  点开就地展示全文，button 自带 aria-label，键盘/读屏同样可读。 */
const showHint = ref(false);

const toneVar = {
  up: 'var(--up)',
  down: 'var(--down)',
  warn: 'var(--warn)',
  muted: 'var(--ink-2)',
} as const;
</script>

<template>
  <div class="kpi-cell flex min-w-0 flex-col justify-center gap-0.5 overflow-hidden px-4 py-2.5" :title="hint">
    <span class="t-label flex min-w-0 items-center gap-1">
      <span class="truncate">{{ label }}</span>
      <button
        v-if="hint"
        type="button"
        class="kpi-hint shrink-0"
        :aria-label="hint"
        :aria-expanded="showHint"
        @click.stop="showHint = !showHint"
      >i</button>
    </span>
    <div class="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0">
      <span class="num truncate text-lg font-bold leading-tight xl:text-xl" style="color: var(--ink-strong)">{{ value }}</span>
      <span v-if="delta" class="num shrink-0 text-xs font-semibold" :style="{ color: toneVar[deltaTone] }">{{ delta }}</span>
      <div class="ms-auto flex shrink-0 items-center"><slot name="extra" /></div>
    </div>
    <p v-if="hint && showHint" class="text-3xs leading-snug" style="color: var(--ink-2)">{{ hint }}</p>
  </div>
</template>

<style scoped>
/* 小圆点 i：桌面克制、触屏可点（点开后整句展示，替代 hover-only 的 title） */
.kpi-hint {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  padding: 0;
  border-radius: 999px;
  font-size: 9px;
  font-style: italic;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  color: var(--ink-3);
  border: 1px solid var(--line-2);
  background: transparent;
}
.kpi-hint:hover,
.kpi-hint:focus-visible {
  color: var(--ink-strong);
  border-color: var(--line-3);
}
</style>
