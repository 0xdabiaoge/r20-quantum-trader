/**
 * 26px 方形图标盒：单一事实源 + 盒内图标尺寸一致（批 78）。
 *
 * ## 实测到的重复与漂移
 *
 * 全站有 7 处「26px 方形图标盒」，其中 **6 处是逐字节相同的 9 属性规则**：
 *
 *   `.ag-icon`（AgentsPage）/ `.bk-archive-icon`（BackupPage）/
 *   `.cn-avatar`（CouncilPage）/ `.nf-cat-icon`（NotifyPage）/
 *   `.pl-icon`（PluginsPage）/ `.pol-unit-icon`（PolicySnapshotPage）
 *
 * 另有 `.dz-icon`（DangerZone）只是配色换成危险色。
 * 改一次盒径要改 7 个地方 —— 而且**已经漂移了**：
 * 同样大的盒子里，图标有 **13 / 14 / 15px 三种**尺寸
 * （BackupPage 13、DangerZone 15、其余 14）。多数决 + 与 `.btn-sm`
 * 的图标契约同值 ⇒ 统一 14px。
 *
 * 现收口为 `styles/components.css` 的 `.icon-box`，
 * 各页只在模板挂 `icon-box`，有差异的才另写 delta（`.dz-icon` 危险色、
 * `.cn-avatar.is-lg` 大号 34px + 16px 图标）。
 *
 * ## 顺带删掉的死 CSS（48 行）
 *
 * `.trace` / `.trace-step` / `.trace-marker` 及其 4 个语义变体
 * （`.is-brand` / `.is-up` / `.is-down` / `.is-warn`）实测在 `src/` 下
 * **任何** `.vue` / `.ts` 都不引用，是上一版设计的遗留。
 *
 * 运行：`node --test tests/*.test.mjs`
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';

const SRC = path.resolve(import.meta.dirname, '..', 'src');
const COMPONENTS_CSS = path.join(SRC, 'styles', 'components.css');

const BOX_PROPS = [
  'display: flex;',
  'align-items: center;',
  'justify-content: center;',
  'width: 26px;',
  'height: 26px;',
  'border-radius: var(--r-ctl);',
  'background-color: var(--ds-color-bg-surface-1);',
  'color: var(--ds-color-text-description);',
  'flex-shrink: 0;',
];

function styleFiles(dir, out = []) {
  for (const n of readdirSync(dir)) {
    const p = path.join(dir, n);
    if (statSync(p).isDirectory()) styleFiles(p, out);
    else if (/\.(vue|css)$/.test(n)) out.push(p);
  }
  return out;
}

/** 找出所有「图标盒形状」的规则：flex 居中 + 26×26。 */
export function iconBoxShapedRules(text) {
  const out = [];
  for (const m of text.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const body = m[2];
    const shaped =
      /display:\s*flex/.test(body) &&
      /align-items:\s*center/.test(body) &&
      /justify-content:\s*center/.test(body) &&
      /width:\s*26px/.test(body) &&
      /height:\s*26px/.test(body);
    if (shaped) {
      out.push({
        selector: m[1].trim().split('\n').pop().trim(),
        line: text.slice(0, m.index).split('\n').length,
      });
    }
  }
  return out;
}

test('26px 图标盒只允许有一处定义，且必须是 .icon-box 原件', () => {
  const bad = [];
  let found = 0;
  for (const file of styleFiles(SRC)) {
    const rel = path.relative(SRC, file);
    for (const r of iconBoxShapedRules(readFileSync(file, 'utf8'))) {
      found += 1;
      if (rel !== path.join('styles', 'components.css') || r.selector !== '.icon-box') {
        bad.push(`${rel}:${r.line} ${r.selector}`);
      }
    }
  }
  assert.deepEqual(
    bad,
    [],
    `26px 图标盒被重复定义（应改用全站 .icon-box 原件）：\n  ${bad.join('\n  ')}`,
  );
  assert.equal(found, 1, `全站应有且仅有 1 处图标盒定义，实测 ${found} 处`);
});

/**
 * 图标盒用户的**清册**。
 *
 * ⚠️ 变异 M1 暴露的缺口：只校验"CSS 里有没有重复定义"是拦不住模板**丢掉**
 * `icon-box` 的 —— 那样元素会静默失去全部盒样式（尺寸、居中、底色都没了），
 * 而任何规则层面的断言都不会响。故逐个文件钉死数量。
 *
 * 新增图标盒时在这里登记；数量不符即翻红。
 */
export const BOX_USERS = {
  'components/admin/page-parts/DangerZone.vue': 1,
  'views/admin/AgentsPage.vue': 1,
  'views/admin/BackupPage.vue': 1,
  'views/admin/CouncilPage.vue': 2,
  'views/admin/NotifyPage.vue': 1,
  'views/admin/PluginsPage.vue': 1,
  'views/admin/PolicySnapshotPage.vue': 1,
};

test('每个图标盒用户都必须挂着 icon-box（清册逐文件钉数量）', () => {
  const bad = [];
  let total = 0;

  for (const [rel, expected] of Object.entries(BOX_USERS)) {
    const text = readFileSync(path.join(SRC, rel), 'utf8');
    const actual = (text.match(/class="[^"]*\bicon-box\b[^"]*"/g) || []).length;
    total += actual;
    if (actual !== expected) {
      bad.push(`${rel} 应挂 ${expected} 处 icon-box，实测 ${actual} 处`);
    }
  }

  assert.deepEqual(bad, [], `图标盒用户在模板上丢了 icon-box：\n  ${bad.join('\n  ')}`);
  assert.equal(total, 8, `全站图标盒实例应为 8 个，实测 ${total} 个`);
});

test('.icon-box 原件必须完整（9 条属性一个不少）', () => {
  const css = readFileSync(COMPONENTS_CSS, 'utf8');
  const m = css.match(/\.icon-box\s*\{([^}]*)\}/);
  assert.ok(m, 'components.css 里找不到 .icon-box');
  for (const p of BOX_PROPS) {
    assert.ok(m[1].includes(p), `.icon-box 缺少属性 ${p}`);
  }
});

test('挂了 icon-box 的元素，盒内图标必须是 14px（.is-lg 大号变体除外）', () => {
  const bad = [];
  let checked = 0;

  for (const file of styleFiles(SRC)) {
    if (!file.endsWith('.vue')) continue;
    const rel = path.relative(SRC, file);
    const lines = readFileSync(file, 'utf8').split('\n');
    lines.forEach((line, i) => {
      const m = line.match(/class="([^"]*\bicon-box\b[^"]*)"/);
      if (!m) return;
      const classes = m[1].split(/\s+/);
      // 图标可能在同行，也可能在下一行（子元素换行）
      const window = line + ' ' + (lines[i + 1] || '');
      const size = window.match(/:size="(\d+)"/);
      if (!size) {
        bad.push(`${rel}:${i + 1} 图标盒内找不到 :size（无法核对尺寸一致性）`);
        return;
      }
      checked += 1;
      const expected = classes.includes('is-lg') ? 16 : 14;
      if (Number(size[1]) !== expected) {
        bad.push(`${rel}:${i + 1} [${classes.join(' ')}] :size="${size[1]}"，应为 ${expected}`);
      }
    });
  }

  assert.ok(checked >= 6, `核对到的图标盒过少（${checked}）`);
  assert.deepEqual(bad, [], `图标盒内图标尺寸不一致：\n  ${bad.join('\n  ')}`);
});

test('每个挂了 icon-box 的模板都必须真有对应的样式或 delta', () => {
  // 反向：.icon-box 不能被删掉却在模板里继续挂着（样式会整体丢失）
  const css = readFileSync(COMPONENTS_CSS, 'utf8');
  assert.match(css, /\.icon-box\s*\{/, '模板挂着 icon-box 但 components.css 里没有该规则');

  // 危险色 delta 必须显式存在（否则危险图标会退回中性底色）
  const dz = readFileSync(path.join(SRC, 'components/admin/page-parts/DangerZone.vue'), 'utf8');
  assert.match(dz, /\.dz-icon\s*\{[^}]*background-color:\s*var\(--down-bg\)/s, '.dz-icon 危险色 delta 丢失');
  assert.match(dz, /\.dz-icon\s*\{[^}]*color:\s*var\(--down\)/s, '.dz-icon 危险色 delta 丢失');
  // 大号变体必须显式存在
  const cn = readFileSync(path.join(SRC, 'views/admin/CouncilPage.vue'), 'utf8');
  assert.match(cn, /\.cn-avatar\.is-lg\s*\{[^}]*width:\s*34px/s, '.cn-avatar.is-lg 大号变体丢失');
});

test('已删的死 CSS（.trace 家族）不得回潮', () => {
  const css = readFileSync(COMPONENTS_CSS, 'utf8');
  for (const sel of ['.trace', '.trace-step', '.trace-marker']) {
    assert.ok(
      !new RegExp(`\\${sel}\\s*[,{]`).test(css),
      `components.css 又出现死 CSS ${sel}（全站零引用）`,
    );
  }
  // 也确认它真的没人用（若将来有人要用，本断言会先提醒去审核）
  for (const file of styleFiles(SRC)) {
    if (file.endsWith('components.css')) continue;
    const text = readFileSync(file, 'utf8');
    assert.ok(!/trace-(step|marker)|class="trace\b/.test(text), `${path.relative(SRC, file)} 引用了已删的 .trace 家族`);
  }
});

test('闸自检：能识别重复的图标盒，且不误伤其它 26px 规则', () => {
  const dup = `
.icon-box { display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; }
.other-icon { display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; }`;
  const hits = iconBoxShapedRules(dup);
  assert.equal(hits.length, 2, '应识别出两处图标盒形状的规则');
  assert.deepEqual(hits.map((h) => h.selector), ['.icon-box', '.other-icon']);

  // 不误伤：26×26 但没有 flex 居中的（例如图片缩略图）
  assert.deepEqual(
    iconBoxShapedRules('.thumb { width: 26px; height: 26px; border-radius: var(--r-ctl); }'),
    [],
    '不带 flex 居中的 26×26 不该被当作图标盒',
  );
  // 不误伤：flex 居中但尺寸不同的
  assert.deepEqual(
    iconBoxShapedRules('.box32 { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; }'),
    [],
    '32px 的盒子不该被当作 26px 图标盒',
  );
});
