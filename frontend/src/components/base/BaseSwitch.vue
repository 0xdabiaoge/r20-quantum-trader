<script setup lang="ts">
/**
 * 开关：v-model 布尔，带禁用与无障碍角色。
 *
 * 批 18 补 `label`：开关本体没有文字，若调用点没把它放进 <label>，
 * 屏幕阅读器与鼠标悬停都拿不到「这一格开的是什么」（实测全站 17 处如此）。
 * 传入 label 后同时落到 `aria-label` 与 `title`。
 */
const props = defineProps<{ modelValue: boolean; disabled?: boolean; label?: string }>();
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

function toggle() {
  if (props.disabled) return;
  emit('update:modelValue', !props.modelValue);
}
</script>

<template>
  <button
    type="button"
    role="switch"
    class="switch"
    :aria-checked="modelValue"
    :aria-label="label || undefined"
    :title="label || undefined"
    :disabled="disabled"
    @click="toggle"
  />
</template>
