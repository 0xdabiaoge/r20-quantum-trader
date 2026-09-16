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

/** 批 23：Escape 的监听从 panel 挪到 document。
 *  原实现挂在 panel 上，只有「焦点正好在面板内」时才收到按键；而用户只要点一下
 *  面板里的标题、说明文字这类**不可聚焦**元素，焦点就回到 body，
 *  此后 Escape/遮罩都关不掉抽屉（实测：焦点在 body 时按 Esc 无反应，抽屉不关）。
 *  模块级栈保证嵌套时只有最上层响应 Escape。 */
const stack: symbol[] = [];
let token: symbol | null = null;

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
    if (stack[stack.length - 1] !== token) return;
    e.stopPropagation();
    emit('close');
    return;
  }
  if (e.key === 'Tab') {
    const els = focusables();
    if (!els.length) return;
    // 焦点已经不在面板里（例如刚点了面板内的纯文本）→ 把焦点拉回来，别漏到背景页
    if (!panel.value || !panel.value.contains(document.activeElement)) {
      e.preventDefault();
      (els[0] || panel.value)?.focus?.();
      return;
    }
    // 焦点停在面板容器上（打开时的默认落点）：正向 Tab 交给浏览器自然进第一个可聚焦项，
    // 反向 Tab 必须拦住，否则会退到遮罩后面的背景页
    if (document.activeElement === panel.value) {
      if (e.shiftKey) {
        e.preventDefault();
        els[els.length - 1].focus();
      }
      return;
    }
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

function detach() {
  document.removeEventListener('keydown', onKeydown, true);
  if (token) {
    const i = stack.indexOf(token);
    if (i >= 0) stack.splice(i, 1);
    token = null;
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      lastFocused = document.activeElement;
      document.body.style.overflow = 'hidden';
      await nextTick();
      token = Symbol('drawer');
      stack.push(token);
      document.addEventListener('keydown', onKeydown, true);
      // 批 23：焦点落在面板容器（outline-none）而不是第一个按钮 —— 详见 BaseDialog 同处注释：
      // 把焦点给按钮会让关闭按钮每次都顶着一圈蓝环（真实鼠标点击后 :focus-visible 仍匹配）。
      panel.value?.focus?.();
    } else {
      document.body.style.overflow = '';
      detach();
      (lastFocused as HTMLElement | null)?.focus?.();
    }
  },
);

onBeforeUnmount(() => {
  document.body.style.overflow = '';
  detach();
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
