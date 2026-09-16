/**
 * `aria-controls` 不得指向「被 v-if 摘掉」的元素（批 85）。
 *
 * ## 实测：16 处悬空引用
 *
 * 用真实浏览器扫 5 个可达页面（实盘矩阵 / AI 推演 / 舆情情报 / 自进化 / 交易台账），
 * 逐个 `document.getElementById(ref)` 校验，发现 **16 处 `aria-controls` 指向
 * 不存在的元素** —— 全部是同一个成因：**目标元素用 `v-if` 渲染，收起时根本不在 DOM 里**。
 *
 * | 站点 | 目标 | 目标的 v-if |
 * |---|---|---|
 * | `BaseStat.vue`（kpi-hint） | `<p :id="hintId">` | `hint && showHint` |
 * | `SettingsPopover.vue` | 弹层 `:id="panelId"` | `open` |
 * | `ChartWorkstation.vue`（币种） | 下拉 `:id="symbolMenuId"` | `symbolMenu` |
 * | `ChartWorkstation.vue`（指标） | 面板 `:id="indicatorMenuId"` | `showIndicatorMenu` |
 * | `PromptStudioPage.vue` | `#ps-var-ribbon` | `showVarRibbon` |
 * | `CouncilPage.vue` | `` #cn-reasoning-${key} `` | `expandedReasoning[…]` |
 * | `OverviewPage.vue` | `#audit-detail-{idx}` | `inspectingAuditIndex === idx` |
 *
 * 其中 `BaseStat` 一个组件就贡献了 9 处（仪表盘上每个带释义的 KPI 单元一个）。
 *
 * ## 修法与仓内既有约定
 *
 * `BaseTabs.vue` 早就写明了正确做法并留了注释：
 * 「不传则不产出 aria-controls（避免指向不存在的 id）」。
 * 7 处全部照此改为**目标存在时才输出**，例如
 * `:aria-controls="showHint ? hintId : undefined"`。
 * `BaseCollapse.vue` 用 `v-show`（元素在 DOM、只是 display:none）——本来就正确，未改。
 *
 * **实测复核**：5 个页面悬空引用 **16 → 0**；
 * 且正向也成立 —— 点开 KPI 释义后 `aria-controls` 出现且 `getElementById` 命中 `<p>`，
 * 再次收起后该属性消失。偏好设置弹层同理。
 *
 * ## 本闸的判据
 *
 * 对源码里每个 `:aria-controls="EXPR"`：找到它引用的 id 绑定所在的标签；
 * **若该标签带 `v-if`，则 EXPR 必须是「条件输出」且引用同一个状态标识**。
 *
 * 运行：`node --test tests/*.test.mjs`
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';

const SRC = path.resolve(import.meta.dirname, '..', 'src');

/** 允许「目标有 v-if 却仍无条件输出」的例外（值=理由）。本批修完应为空。 */
export const UNGUARDED_ALLOWED = {};

function vueFiles(dir, out = []) {
  for (const n of readdirSync(dir)) {
    const p = path.join(dir, n);
    if (statSync(p).isDirectory()) vueFiles(p, out);
    else if (n.endsWith('.vue')) out.push(p);
  }
  return out;
}

/** 去注释（HTML / 块 / 行）。`//` 用 (?<!:) 保护 https:// */
export function stripComments(text) {
  return text
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(?<!:)\/\/[^\n]*/g, '');
}

/** 找到 offset 所在标签的完整文本（引号感知，且跳过标签内的 > ）。 */
export function enclosingTag(text, offset) {
  const start = text.lastIndexOf('<', offset);
  if (start === -1) return '';
  let i = start, q = null;
  while (i < text.length) {
    const ch = text[i];
    if (q) { if (ch === q) q = null; }
    else if (ch === '"' || ch === "'") q = ch;
    else if (ch === '>') return text.slice(start, i + 1);
    i += 1;
  }
  return text.slice(start);
}

/** 从 v-if / v-show 属性里取出条件表达式。 */
export function conditionOf(tag) {
  const m = /(?<!:)\bv-if="([^"]*)"/.exec(tag);
  return m ? m[1] : null;
}

/** 取条件里的「状态标识」（排除纯字面量与运算符）。 */
export function stateTokens(cond) {
  if (!cond) return [];
  return (cond.match(/[A-Za-z_$][\w$]*/g) || []).filter((t) => !['true', 'false', 'null', 'undefined', 'Boolean', 'String', 'Number'].includes(t));
}

/** 取 aria-controls 表达式里「真正指向元素」的那部分（三元取真支）。 */
export function targetPart(expr) {
  const q = expr.indexOf('?');
  if (q === -1) return expr;
  const rest = expr.slice(q + 1);
  const colon = rest.lastIndexOf(':');
  return colon === -1 ? rest : rest.slice(0, colon);
}

/** 从 id 表达式里取出可用于匹配的标识（标识符 ≥3 字符，或字符串字面量）。 */
export function idTokens(expr) {
  const out = new Set();
  for (const m of expr.matchAll(/'([^']{3,})'|"([^"]{3,})"/g)) out.add(m[1] ?? m[2]);
  for (const m of expr.matchAll(/[A-Za-z_$][\w$]{2,}/g)) {
    if (!['undefined', 'String', 'Boolean'].includes(m[0])) out.add(m[0]);
  }
  return [...out];
}

function analyse() {
  const files = vueFiles(SRC).map((f) => ({ rel: path.relative(SRC, f), raw: stripComments(readFileSync(f, 'utf8')) }));

  // 收集**全局** id 绑定 —— 目标可能在别的文件里（如 TopBar 控制 DashboardLayout 的侧栏）
  const bindingsOf = (raw) => {
    const out = [];
    for (const m of raw.matchAll(/(?<!:)\bid="([^"]*)"|:id="([^"]*)"/g)) {
      const expr = m[1] ?? m[2] ?? '';
      if (!expr) continue;
      out.push({ expr, vIf: conditionOf(enclosingTag(raw, m.index)) });
    }
    return out;
  };
  const perFile = new Map(files.map((f) => [f.rel, bindingsOf(f.raw)]));

  const sites = [];
  for (const { rel, raw } of files) {
    for (const m of raw.matchAll(/:aria-controls="([^"]*)"/g)) {
      const expr = m[1];
      const wanted = idTokens(targetPart(expr));
      // 先在**本文件**找，再退到全局（跨文件引用是合法的：TopBar → 侧栏）
      let best = null, bestScore = 0, bestRel = null;
      for (const [r2, list] of perFile) {
        for (const b of list) {
          const have = new Set(idTokens(b.expr));
          const score = wanted.filter((t) => have.has(t)).length;
          // 同文件优先：给本文件的命中加一点权重
          const weighted = score + (r2 === rel ? 0.5 : 0);
          if (score > 0 && weighted > bestScore) { best = b; bestScore = weighted; bestRel = r2; }
        }
      }
      sites.push({
        rel, expr,
        guarded: /\?/.test(expr) && /undefined/.test(expr),
        target: best ? best.vIf : '__NOT_FOUND__',
        targetFound: !!best,
        targetRel: bestRel,
        targetScore: bestScore,
      });
    }
  }
  return sites;
}

test('目标被 v-if 摘掉的 aria-controls，必须做成条件输出', () => {
  const problems = [];
  for (const s of analyse()) {
    if (!s.targetFound || s.targetScore === 0) {
      problems.push(`${s.rel} :: ${s.expr}  —— 找不到它引用的 id 绑定（无法判定目标是否存在）`);
      continue;
    }
    if (s.target === '__NOT_FOUND__') continue;
    const cond = s.target; // null 表示目标无 v-if（元素恒在）
    if (!cond) continue; // 恒在 → 无条件输出也正确
    if (UNGUARDED_ALLOWED[`${s.rel}::${s.expr}`]) continue;
    if (!s.guarded) {
      problems.push(`${s.rel} :: ${s.expr}\n      目标带 v-if="${cond}"，收起时元素不在 DOM → 引用悬空，应改为「目标存在时才输出」`);
      continue;
    }
    // 条件输出还必须引用同一个状态标识（否则守卫的不是这个目标）
    const toks = stateTokens(cond);
    if (toks.length && !toks.some((t) => s.expr.includes(t))) {
      problems.push(`${s.rel} :: ${s.expr}\n      守卫条件未引用目标的 v-if 状态（${toks.join('/')}），可能守卫错了目标`);
    }
  }
  assert.deepEqual(problems, [], `aria-controls 悬空引用：\n  ${problems.join('\n  ')}`);
});

test('全站 aria-controls 站点数与「条件输出」数应保持可审计', () => {
  const sites = analyse();
  assert.ok(sites.length >= 15, `识别到的 aria-controls 站点过少（${sites.length}），判据可能失效`);
  // 记录基线：批 85 收官时 7 处条件输出（其余目标恒在 DOM，无需条件）
  const unguardedWithVIf = sites.filter((s) => s.target && s.target !== '__NOT_FOUND__' && !s.guarded);
  assert.deepEqual(
    unguardedWithVIf.map((s) => `${s.rel} :: ${s.expr}`),
    [],
    '仍有「目标带 v-if 却无条件输出」的站点',
  );
});

test('BaseStat 的释义按钮：收起时不得输出 aria-controls', () => {
  const t = stripComments(readFileSync(path.join(SRC, 'components/base/BaseStat.vue'), 'utf8'));
  assert.match(
    t,
    /:aria-controls="showHint \? hintId : undefined"/,
    'BaseStat 的 aria-controls 应随 showHint 条件输出（其目标是 v-if="hint && showHint"）',
  );
  // ⚠️ 这条必须用**未剥注释**的原始文本：剥了注释就看不出"注释被塞进标签属性之间"。
  const raw = readFileSync(path.join(SRC, 'components/base/BaseStat.vue'), 'utf8');
  const at = raw.indexOf(':aria-controls="showHint');
  const tag = enclosingTag(raw, at);
  assert.doesNotMatch(tag, /<!--/, 'HTML 注释不能出现在标签的属性之间（Vue 编译期直接报错，vue-tsc 不报）');
});

/**
 * 通用检查：`<!-- -->` 不得出现在**标签内部**（属性之间）。
 * 本批实测踩到：把说明注释插在 `:aria-expanded` 与 `:aria-controls` 之间，
 * `vue-tsc` 通过、但 `vite build` 直接失败
 * （Attribute name cannot contain U+0022 / U+0027 / U+003C）。
 * 这个错只有构建能发现，故在此固化成源码级闸。
 */
test('任何 .vue 都不得把 HTML 注释写进标签内部', () => {
  const bad = [];
  for (const f of vueFiles(SRC)) {
    const raw = readFileSync(f, 'utf8');
    let i = 0;
    while (i < raw.length) {
      if (raw.startsWith('<!--', i)) i += 4; // 正常注释，跳过其起始标记
      else if (raw[i] === '<' && /[A-Za-z]/.test(raw[i + 1] || '')) {
        // 进入一个开始标签，扫到未加引号的 '>'
        let j = i + 1, q = null;
        while (j < raw.length && raw[j] !== '>') {
          if (q) { if (raw[j] === q) q = null; }
          else if (raw[j] === '"' || raw[j] === "'") q = raw[j];
          else if (raw.startsWith('<!--', j)) {
            const ln = raw.slice(0, j).split('\n').length;
            bad.push(`${path.relative(SRC, f)}:${ln} 标签内部出现 <!--`);
            break;
          }
          j += 1;
        }
        i = j + 1;
      } else i += 1;
    }
  }
  assert.deepEqual(bad, [], `HTML 注释被写进了标签内部（vite build 会失败）：\n  ${bad.join('\n  ')}`);
});

test('闸自检：标签提取不被属性里的 > 截断，条件/状态抽取正确', () => {
  const tpl = '<div v-if="a > 1" :id="xId" class="c">';
  const tag = enclosingTag(tpl, tpl.indexOf(':id'));
  assert.match(tag, /class="c"/, 'enclosingTag 被属性里的 > 截断');
  assert.equal(conditionOf(tag), 'a > 1');
  assert.deepEqual(stateTokens('a > 1'), ['a']);
  assert.deepEqual(stateTokens('expandedReasoning[String(key)]'), ['expandedReasoning', 'key']);
  // targetPart：三元取真支
  assert.equal(targetPart('showHint ? hintId : undefined'), ' hintId ');
  assert.equal(targetPart('hintId'), 'hintId');
  // idTokens 命中标识符与字符串字面量
  assert.ok(idTokens("'ps-var-ribbon'").includes('ps-var-ribbon'));
  assert.ok(idTokens('hintId').includes('hintId'));
  // 注释剥离
  assert.deepEqual(stripComments('<!-- x -->').trim(), '');
  // 标签内注释的识别（样例）
  const badSample = '<button\n  a="1"\n  <!-- nope -->\n  b="2"\n>';
  let found = false, k = badSample.indexOf('<button') + 1;
  while (k < badSample.length && badSample[k] !== '>') { if (badSample.startsWith('<!--', k)) { found = true; break; } k += 1; }
  assert.equal(found, true, '样例里的标签内注释应被识别');
});
