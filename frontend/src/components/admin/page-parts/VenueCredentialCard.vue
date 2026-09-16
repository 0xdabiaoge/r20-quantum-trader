<script setup lang="ts">
/**
 * VenueCredentialCard · 三所凭证卡外壳（**仅供 SecurityPage 使用**）
 * ---------------------------------------------------------------------------
 * 批 10 重构：内联 `TONES` 样式三元 → 语义徽章类；内嵌 `surface-1` 方块 →
 * 面板内分区（发丝分隔）；页脚动作位改用共享按钮语汇。
 * 对外接口（props / slots）保持兼容。
 */
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  name: string
  apiLabel: string
  statusText: string
  tone?: 'up' | 'warn' | 'down'
  envText: string
  envLabel?: string
}>(), { tone: 'warn', envLabel: '当前资金档位' })

const toneClass = computed(
  () => ({ up: 'badge-up', warn: 'badge-warn', down: 'badge-down' })[props.tone] ?? 'badge-warn',
)
</script>

<template>
  <div class="vc">
    <!-- 卡头：所名 + 接口档 + 状态徽章 -->
    <header class="vc-head">
      <div class="vc-id">
        <h4 class="vc-name">{{ name }}</h4>
        <span class="vc-api">{{ apiLabel }}</span>
      </div>
      <span class="badge" :class="toneClass">{{ statusText }}</span>
    </header>

    <!-- 资金档位 -->
    <div class="vc-env">
      <span class="vc-env-label">{{ envLabel }}</span>
      <span class="vc-env-value mono">{{ envText }}</span>
    </div>

    <div class="vc-body">
      <slot name="env" />
      <slot />
      <slot name="extra" />
    </div>

    <!-- 页脚动作 -->
    <footer class="vc-foot">
      <slot name="footer-left" />
      <div class="vc-foot-actions">
        <slot name="probe" />
        <slot name="save" />
      </div>
    </footer>
  </div>
</template>

<style scoped>
.vc {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--ds-color-border-default);
  border-radius: var(--r-ctl);
  background-color: var(--ds-color-bg-surface-inset);
  overflow: hidden;
}
.vc-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ds-space-3);
  padding: 10px var(--ds-space-3);
  border-bottom: 1px solid var(--ds-color-border-default);
}
.vc-id {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.vc-name {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ds-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vc-api {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
.vc-head .badge {
  flex-shrink: 0;
}
.vc-env {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
  padding:8px var(--ds-space-3);
  border-bottom: 1px solid var(--ds-color-border-default);
}
.vc-env-label {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
.vc-env-value {
  font-size: var(--text-3xs);
  font-weight: 600;
  color: var(--ds-color-text-primary);
}
.vc-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  padding: var(--ds-space-3);
}
.vc-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--ds-space-2);
  flex-wrap: wrap;
  padding: 10px var(--ds-space-3);
  border-top: 1px solid var(--ds-color-border-default);
  background-color: var(--ds-color-bg-surface-1);
}
.vc-foot-actions {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  margin-left: auto;
}
</style>
