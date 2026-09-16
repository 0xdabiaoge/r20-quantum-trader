<script setup lang="ts">
/** 币种头像：字母徽标 + 按 symbol 哈希的稳定色相（无外部图片依赖） */
import { computed } from 'vue';

const props = withDefaults(defineProps<{ symbol?: string; size?: number }>(), { size: 20 });

const HUES = [212, 265, 32, 160, 340, 190, 285, 100, 12, 230];

const hue = computed(() => {
  const s = String(props.symbol || 'R');
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 997;
  return HUES[h % HUES.length];
});
</script>

<template>
  <span
    class="inline-flex shrink-0 select-none items-center justify-center rounded-md font-bold"
    :style="{
      width: size + 'px',
      height: size + 'px',
      /* 批 28：地板 9 → 11（档位下限）。字母是图形化字形，字号仍随方块等比缩放，
         但不再掉到 11px 以下；16~20px 的方块都会落到 11px，尺寸也因此统一。 */
      fontSize: Math.max(11, size * 0.52) + 'px',
      lineHeight: 1,
      /* 批 19：字母色 62% → 74% 明度。原值在蓝/紫色相上只有 4.37~4.45:1
         （低于 AA 4.5），而这是 9~10px 的小字母，压暗更看不清。
         74% 在全部 10 个色相 × 常用底色上 ≥5.68:1。 */
      backgroundColor: `hsl(${hue} 60% 50% / 0.14)`,
      color: `hsl(${hue} 72% 74%)`,
      border: `1px solid hsl(${hue} 60% 55% / 0.3)`,
    }"
    aria-hidden="true"
  >
    {{ (symbol || '?').slice(0, 1) }}
  </span>
</template>
