<script setup lang="ts">
/**
 * 右侧滑出抽屉 —— 详情透视专用：列表上下文不丢，看完即关。
 * 规则：任何"看详情"一律 Drawer，禁止全屏跳转或嵌套弹窗。
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { X } from 'lucide-vue-next';
import { useI18n } from '../../composables/useI18n';

const { t } = useI18n();

const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    subtitle?: string;
    width?: string;
    closeOnScrim?: boolean;
  }>(),
  { closeOnScrim: true, width: '580px' },
);

const emit = defineEmits<{ (e: 'close'): void }>();

const panel = ref<HTMLElement | null>(null);
let lastFocused: Element | null = null;

/** 可聚焦元素收集 —— 与 BaseDialog 同一判据（可见性用 offsetParent 过滤隐藏项）。
 *  批D(2026-09-13)：抽屉此前只有 Escape + 焦点归位，**没有焦点陷阱**——Tab 会一路
 *  走出抽屉落到被遮罩盖住的页面上（键盘用户"点进空气"，屏幕阅读器也会跑到背景内容）。
 *  抽屉是详情透视的主入口（台账/持仓/快讯详情全走它），补 Tab 环绕。 */
function focusables(): HTMLElement[] {
  if (!panel.value) return [];
  return Array.from(
    panel.value.querySelectorAll<HTMLElement>(
      'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])',
    ),
  ).filter((el) => el.offsetParent !== null);
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.stopPropagation();
    emit('close');
    return;
  }
  if (e.key === 'Tab') {
    const els = focusables();
    if (!els.length) return;
    const first = els[0];
    const last = els[els.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      lastFocused = document.activeElement;
      document.body.style.overflow = 'hidden';
      await nextTick();
      panel.value?.addEventListener('keydown', onKeydown);
      const els = focusables();
      (els[0] || panel.value)?.focus?.();
    } else {
      document.body.style.overflow = '';
      panel.value?.removeEventListener('keydown', onKeydown);
      (lastFocused as HTMLElement | null)?.focus?.();
    }
  },
);

onBeforeUnmount(() => {
  document.body.style.overflow = '';
});
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0" style="z-index: var(--z-drawer)">
        <div class="absolute inset-0" style="background-color: var(--overlay-scrim)" @mousedown="closeOnScrim && emit('close')" />
        <Transition name="drawer" appear>
          <aside
            v-if="open"
            ref="panel"
            tabindex="-1"
            role="dialog"
            aria-modal="true"
            class="absolute inset-y-0 right-0 flex flex-col outline-none"
            :style="{
              width: `min(${width}, 96vw)`,
              backgroundColor: 'var(--surface-2)',
              borderLeft: '1px solid var(--line-2)',
              boxShadow: 'var(--shadow-dialog)',
            }"
          >
            <header
              class="flex items-start justify-between gap-4 px-5 py-4 shrink-0"
              style="border-bottom: 1px solid var(--line-1)"
            >
              <div class="min-w-0">
                <h3 class="truncate text-md font-semibold" style="color: var(--ink-strong)">
                  <slot name="title">{{ title }}</slot>
                </h3>
                <p v-if="subtitle || $slots.subtitle" class="mt-0.5 truncate text-xs" style="color: var(--ink-2)">
                  <slot name="subtitle">{{ subtitle }}</slot>
                </p>
              </div>
              <div class="flex items-center gap-1 shrink-0">
                <slot name="actions" />
                <button class="btn btn-quiet btn-icon" :aria-label="t('common.close')" @click="emit('close')"><X /></button>
              </div>
            </header>
            <div class="scroll-y flex-1 px-5 py-4">
              <slot />
            </div>
            <footer
              v-if="$slots.footer"
              class="flex items-center justify-end gap-2 px-5 py-3.5 shrink-0"
              style="border-top: 1px solid var(--line-1)"
            >
              <slot name="footer" />
            </footer>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: transform var(--dur-slow) var(--ease-out), opacity var(--dur-slow) var(--ease-out);
}
.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(28px);
  opacity: 0.4;
}
</style>
