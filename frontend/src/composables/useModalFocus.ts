/**
 * 模态焦点管理（批 42）—— 从 `BaseDialog.vue` / `BaseDrawer.vue` 里提取的**同一份逻辑**。
 *
 * ## 为什么要提出来
 *
 * 这三件事（Escape 关层、Tab 环绕不逃到背景页、打开/关闭时的焦点交接）此前在
 * BaseDialog 与 BaseDrawer 里**各写了一份**，而 `TrajectoryPanel.vue` —— 一个同样声明
 * `role="dialog" aria-modal="true"` 的模态抽屉 —— **一份都没有**：
 *
 * - 按 Escape 关不掉（全站唯一关不掉的模态）；实测复现；
 * - Tab 一路走到被遮罩盖住的背景页（`aria-modal` 说了谎）；
 * - 打开后焦点仍在顶栏的触发按钮上，关闭后也不归还；
 * - 背景页仍可滚动（两个基础组件都有滚动锁）。
 *
 * 抄第三份不是办法，所以提取到这里：
 * **同一层栈**（模块级 `stack`）保证嵌套时只有最上层响应 Escape，
 * 后来者只要接上本组合式就不会再出现"某个模态少一样"。
 *
 * ## 用法
 *
 * ```ts
 * const panel = ref<HTMLElement | null>(null)
 * const { sync } = useModalFocus(panel, () => emit('close'))
 * watch(() => props.open, sync, { immediate: true })
 * onBeforeUnmount(() => release())   // 组件卸载时兜底
 * ```
 */
import { nextTick, type Ref } from 'vue';

/** 可聚焦元素判据（三处统一）：可见性用 `offsetParent` 过滤隐藏项。 */
const FOCUSABLE_SELECTOR =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

/** 模块级栈：嵌套模态只有最上层响应 Escape。 */
const stack: symbol[] = [];

export function useModalFocus(
  panel: Ref<HTMLElement | null>,
  onClose: () => void,
  options: { lockScroll?: boolean } = {},
) {
  const lockScroll = options.lockScroll !== false;
  let lastFocused: Element | null = null;
  let token: symbol | null = null;

  function focusables(): HTMLElement[] {
    if (!panel.value) return [];
    return Array.from(panel.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
      (el) => el.offsetParent !== null,
    );
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      if (stack[stack.length - 1] !== token) return;
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== 'Tab') return;
    const els = focusables();
    if (!els.length) return;
    // 焦点已不在面板里（例如刚点了面板内的纯文本）→ 拉回来，别漏到背景页
    if (!panel.value || !panel.value.contains(document.activeElement)) {
      e.preventDefault();
      (els[0] || panel.value)?.focus?.();
      return;
    }
    // 焦点停在面板容器上（打开时的默认落点）：正向 Tab 交给浏览器进第一个可聚焦项，
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

  function attach() {
    token = Symbol('modal');
    stack.push(token);
    document.addEventListener('keydown', onKeydown, true);
  }

  function detach() {
    document.removeEventListener('keydown', onKeydown, true);
    if (token) {
      const i = stack.indexOf(token);
      if (i >= 0) stack.splice(i, 1);
      token = null;
    }
  }

  /**
   * 跟随 `open` 状态调用：打开时记住原焦点、锁滚动、挂监听并把焦点落到**面板容器**
   * （`tabindex="-1"` + `outline-none`；不给第一个按钮，否则鼠标用户会看到一圈蓝环）；
   * 关闭时解锁、摘监听、把焦点还给触发元素。
   */
  async function sync(open: boolean) {
    if (open) {
      lastFocused = document.activeElement;
      if (lockScroll) document.body.style.overflow = 'hidden';
      await nextTick();
      attach();
      panel.value?.focus?.();
      return;
    }
    if (lockScroll) document.body.style.overflow = '';
    detach();
    (lastFocused as HTMLElement | null)?.focus?.();
  }

  /** 组件卸载兜底：解开滚动锁与监听（避免留下"页面永远滚不动"）。 */
  function release() {
    if (lockScroll) document.body.style.overflow = '';
    detach();
  }

  return { sync, release };
}
