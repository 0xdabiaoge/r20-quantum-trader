/**
 * 悬停反馈判据（批 100）。
 *
 * ## 怎么发现的：又一个审计工具不覆盖的维度
 *
 * 前几批把 `a11y-audit.js` 的各类指标压到 0 之后，换量「**可点但悬停毫无反馈**」。
 * 做法不用逐个 hover：把 CSS 里所有 `:hover` 选择器**剥掉伪类**，再对每个
 * `cursor: pointer` 的最外层元素跑 `el.matches(stripped)` —— 完整且极快。
 *
 * 25 路由 **901 个可点元素 / 139 个无任何 hover 规则**。逐个复核后：
 *
 * | 组 | 数量 | 判定 |
 * |---|---|---|
 * | `button.w-full.flex`（侧栏频道） | 30 | **真缺陷**：同列表下面的「文档」按钮有 hover，相邻两项行为不同 |
 * | `button.sort-btn` | 16 | **真缺陷**：实测悬停 computed style **零变化** |
 * | `button.switch` | 16 | **真缺陷**：全站开关只有「点击后旋钮位移」 |
 * | `A.skip-link` | 24 | 不是缺陷：平时移出视口，靠 `:focus` 显现 |
 * | `button.seg-on` | 17 | 不是缺陷：`.seg button:hover:not(.seg-on)` **明确排除**选中项 |
 * | `button.w-full.text-left`（DocsView） | 11 | **假阳性**：子元素有 `group-hover:opacity-100` |
 *
 * ## 修法
 *
 * ① 侧栏频道按钮：活动/非活动态原本写在内联 `:style` —— **内联样式优先级高于工具类**，
 *    直接加 `hover:` 类不会生效。改为 `:class`，hover 只加在**非活动**项上（与
 *    `.seg button:hover:not(.seg-on)` 同一约定）。
 * ② `.sort-btn:hover` 用既有语汇 `--ds-color-text-primary` + `--dur-fast`。
 * ③ `.switch:hover:not([aria-checked="true"])` 用 `--ds-color-border-hover`；
 *    **显式 `:not()` 是必须的**：否则与 `.switch[aria-checked="true"]` 同权重，
 *    靠书写顺序决胜（行为对，但改一处顺序就静默失效）。
 *
 * 实机复核（hover 前后 diff computed style）：
 * 排序按钮 2 项变化；侧栏**非当前**频道 2 项变化、当前频道 0 项（符合约定）；
 * **关**的开关边色 `rgb(40,48,66)` → `rgb(59,69,94)`、**开**的开关 0 项（符合约定）；
 * 对照 `.btn-ghost` 2 项变化（证明仪器能检出阳性）。
 *
 * ⚠️ 遍历样式表时：**CSS 嵌套让 `CSSStyleRule` 也有 `cssRules`（通常是空列表）**，
 * 写成 `if (rule.cssRules) { walk(); continue }` 会把**每条样式规则都跳过**
 * （实测 899 条规则里 0 条 hover）。必须先看 `selectorText`。
 *
 * 运行：`node --test tests/*.test.mjs`
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

const SRC = path.resolve(import.meta.dirname, '..', 'src');
const CSS = readFileSync(path.join(SRC, 'styles', 'components.css'), 'utf8');
const DASH = readFileSync(path.join(SRC, 'layouts', 'DashboardLayout.vue'), 'utf8');

/** 找到含指定选择器的规则体（注释先剥掉）。 */
function ruleBody(css, selector) {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const re = new RegExp(`(?:^|\\})\\s*${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`);
  const m = re.exec(clean);
  return m ? m[1] : null;
}

test('表格排序按钮必须有 hover 反馈（批 100 修的 16 处）', () => {
  const body = ruleBody(CSS, '.sort-btn:hover');
  assert.ok(body, '找不到 .sort-btn:hover —— 表头又会变成「看不出可点」');
  assert.match(body, /color\s*:\s*var\(--ds-color-text-primary\)/, 'hover 应改文字色（全站既有语汇）');
  const base = ruleBody(CSS, '.sort-btn');
  assert.match(base, /transition:\s*color\s+var\(--dur-fast\)/, 'hover 变色要接动效令牌，否则硬切');
});

test('开关的 hover 必须显式排除「开着」的状态（去掉顺序依赖）', () => {
  const body = ruleBody(CSS, '.switch:hover:not([aria-checked="true"])');
  assert.ok(
    body,
    '找不到 .switch:hover:not([aria-checked="true"]) —— ' +
      '若退回成裸 `.switch:hover`，它与 `.switch[aria-checked="true"]` 同权重，' +
      '只能靠书写顺序决胜，动一处顺序就静默失效',
  );
  assert.match(body, /border-color\s*:\s*var\(--ds-color-border-hover\)/);
});

test('侧栏频道按钮不得再用内联样式写活动态（否则 hover 类永远不生效）', () => {
  const m = /<button\s+v-for="tab in publicTabs"[\s\S]*?>/.exec(DASH);
  assert.ok(m, '找不到 publicTabs 的按钮');
  const tag = m[0];
  assert.ok(
    !/:style="[\s\S]*backgroundColor/.test(tag),
    '活动态又写回了内联 `:style` —— **内联样式优先级高于工具类**，hover 类会失效',
  );
  assert.match(tag, /:class="[\s\S]*hover:bg-\[var\(--surface-2\)\]/, '非活动态缺少 hover 类');
  assert.match(tag, /activeTab === tab\.key[\s\S]*?\?[\s\S]*?:\s*'[^']*hover:/, 'hover 只应加在非活动分支上');
});

test('内联 :style 写活动态 + transition-colors 的组合必须清零（批 100 修的三处）', () => {
  // 这是同一个反模式的三个落点：内联样式优先级高于工具类，于是 `transition-colors`
  // 永远等不到 hover，成了一条「看着像有动效、实际不会动」的死属性。
  const targets = [
    ['layouts/DashboardLayout.vue', '侧栏频道按钮'],
    ['components/dashboard/FactorMatrix.vue', '矩阵筛选芯片'],
    ['components/dashboard/VenueAccountsPanel.vue', '环境切换'],
  ];
  for (const [rel, label] of targets) {
    const src = readFileSync(path.join(SRC, rel), 'utf8');
    const m = /class="[^"]*transition-colors[^"]*"\s*\n\s*:style="([^"]*)"/.exec(src);
    assert.equal(
      m,
      null,
      `${label}（${rel}）：又出现「transition-colors + 内联 :style 写状态」—— ` +
        `该 transition 永远不会触发（内联样式优先级高于 hover 工具类）。改用 :class。`,
    );
    assert.match(src, /hover:/, `${label}（${rel}）里一个 hover: 都没有`);
  }
});

test('判据自检：ruleBody 能取到规则、取不到时不误判', () => {
  assert.ok(ruleBody(CSS, '.sort-btn:hover'), '已知存在的选择器应取到');
  assert.equal(ruleBody(CSS, '.definitely-not-here:hover'), null, '不存在的选择器应返回 null');
  assert.match(ruleBody(CSS, '.seg button:hover:not(.seg-on)'), /background-color/, '选中态排除的既有语汇仍在');
});
