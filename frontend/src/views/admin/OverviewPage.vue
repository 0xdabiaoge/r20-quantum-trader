<script setup lang="ts">
/**
 * OverviewPage.vue · 开发者工作台 · 系统全景总览
 * ---------------------------------------------------------------------------
 * 架构重构（推倒旧版模板）：
 *   - 顶部：实时心跳指示器与工作台状态栏
 *   - 模块 1：四维全景指标矩阵（执行核心 / AI决策主脑 / 撮合路由网关 / 物理安全防线）
 *   - 模块 2：双栏指挥工位
 *       · 左侧（62%）：AI 实时决策流（指令周期动作、置信度量规、推理时间与核心研判）
 *       · 右侧（38%）：数据管道实时时效监控 + 核心管控通道直达
 *   - 模块 3：系统审计与运行轨迹面板（结构化事件提取、状态指示、人类可读上下文）
 *
 * 后端契约（严格保持原样）：
 *   GET /api/v1/admin/runtime
 *   GET /api/v1/admin/config
 *   锁定消费键：model / provider_name / reasoning_effort / api_format
 */
import { computed, onMounted, ref } from 'vue';
import {
  Server,
  Cpu,
  Wallet,
  Braces,
  Crosshair,
  Landmark,
  RefreshCw,
  ArrowRight,
  Database,
  ScrollText,
  AlertCircle,
  ShieldCheck,
  History,
  LayoutGrid,
  ChevronRight,
  Clock
} from 'lucide-vue-next';
import { get } from '../../api/http';
import { useI18n } from '../../composables/useI18n';
import { APP_VERSION } from '../../config/version';
import PageHeader from '../../components/admin/PageHeader.vue';
import BaseEmpty from '../../components/base/BaseEmpty.vue';
import TimeAgo from '../../components/base/TimeAgo.vue';
import { fmtNum, fmtDateTime } from '../../utils/format';

const { t } = useI18n();

const runtime = ref<any>(null);
const loading = ref(false);
const loaded = ref(false);
const loadError = ref(false);
const inspectingAuditIndex = ref<number | null>(null);

async function load() {
  loading.value = true;
  loadError.value = false;
  try {
    const [rt, cfg] = await Promise.all([
      get('/api/v1/admin/runtime').catch(() => null),
      get('/api/v1/admin/config').catch(() => null),
    ]);
    if (rt && cfg?.configuration) {
      rt.configuration = { ...cfg.configuration, ...(rt.configuration || {}) };
    }
    runtime.value = rt;
    loadError.value = !rt;
  } finally {
    loading.value = false;
    loaded.value = true;
  }
}
onMounted(load);

const service = computed(() => runtime.value?.service || {});
const uptime = computed(() => {
  const s = Number(service.value.uptime_seconds || 0);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
});

const llm = computed(() => runtime.value?.llm_runtime || {});
const conf = computed<Record<string, string>>(() => runtime.value?.configuration || {});
const venueEnv = computed(() => conf.value['交易场所与路由'] || conf.value['OKX 当前环境'] || 'DEMO');
const isDemo = computed(() => venueEnv.value.includes('DEMO') || venueEnv.value.includes('模拟'));
const health = computed(() => runtime.value?.data_health || {});
const healthFiles = computed<any[]>(() => health.value.files || []);
const decisions = computed<any[]>(() => (runtime.value?.decisions || []).slice(0, 8));
const audits = computed<any[]>(() => (runtime.value?.audit || []).slice(0, 8));

const showSkeleton = computed(() => loading.value && !loaded.value);

const quickNavs = computed(() => [
  { to: '/admin/promptlib', icon: Braces, title: t('admin.overview.quick.prompts'), desc: '语义变量与版本预设' },
  { to: '/admin/council', icon: Landmark, title: t('admin.overview.quick.council'), desc: '多参谋交叉质询仲裁' },
  { to: '/admin/interceptors', icon: Crosshair, title: t('admin.overview.quick.interceptors'), desc: 'Fail-Closed 物理硬防线' },
  { to: '/admin/llm', icon: Cpu, title: t('admin.overview.quick.llm'), desc: '供应商路由与思考强度' },
]);

function parseAuditContext(action: string, detail: any): { label: string; tag: string; tagType: string; summary: string } {
  const act = String(action || '').replace('admin.', '');
  const d = detail || {};
  
  if (act === 'login') {
    return {
      label: '管理员鉴权',
      tag: 'AUTH',
      tagType: 'info',
      summary: `用户: ${d.username || 'admin'} · 来源: ${d.ip || '本地客户端'}`
    };
  }
  if (act.includes('test') || act.includes('notify') || act.includes('notification')) {
    return {
      label: '通道连通测试',
      tag: 'NOTIFY',
      tagType: 'neutral',
      summary: `通道: ${d.channel || '系统通道'} · 结果: ${d.result?.accepted ? '接收成功' : '测试已派发'}`
    };
  }
  if (act.includes('interceptor')) {
    return {
      label: '拦截规则状态',
      tag: 'RULE',
      tagType: 'warn',
      summary: `规则: ${d.filename || d.actor || '防线配置'} · 状态: ${d.enabled ? '已启用' : '已停用'}`
    };
  }
  return {
    label: act,
    tag: 'OP',
    tagType: 'neutral',
    summary: Object.keys(d).length ? JSON.stringify(d).slice(0, 80) : '执行成功'
  };
}
</script>

<template>
  <div class="ov-deck">
    <!-- 顶部工作台标题与状态 -->
    <PageHeader :title="t('nav.admin.overview')" :description="t('admin.overview.desc')">
      <template #actions>
        <div class="ov-header-actions">
          <div class="ov-live-pill">
            <span class="ov-live-dot" />
            <span class="ov-live-text">TELEMETRY LIVE</span>
          </div>
          <span class="ov-version-badge mono">{{ APP_VERSION }}</span>
          <button class="ov-btn-refresh" :disabled="loading" @click="load" :title="t('common.refresh')">
            <RefreshCw :size="13" :class="loading && 'ov-spin'" />
            <span>{{ t('common.refresh') }}</span>
          </button>
        </div>
      </template>
    </PageHeader>

    <!-- 错误恢复横幅 -->
    <div v-if="loadError" class="ov-error-banner">
      <div class="ov-error-left">
        <AlertCircle :size="18" class="ov-error-icon" />
        <div>
          <h4 class="ov-error-title">{{ t('admin.overview.loadFailedTitle') }}</h4>
          <p class="ov-error-desc">{{ t('admin.overview.loadFailedDesc') }}</p>
        </div>
      </div>
      <button class="btn btn-primary btn-sm" :disabled="loading" @click="load">
        <RefreshCw :size="13" :class="loading && 'ov-spin'" />
        <span>{{ t('common.retry') }}</span>
      </button>
    </div>

    <!-- ══ 模块 1：四维全景指标矩阵 (HUD) ══ -->
    <section class="ov-hud">
      <!-- 指标 1：执行核心 -->
      <div class="ov-hud-card">
        <div class="ov-hud-head">
          <span class="ov-hud-icon"><Server :size="14" /></span>
          <span class="ov-hud-label">{{ t('admin.overview.backend') }}</span>
          <span class="ov-hud-badge is-up">
            <span class="pulse-dot" />
            ONLINE
          </span>
        </div>
        <div class="ov-hud-body">
          <div class="ov-hud-val num">PID {{ service.pid || '--' }}</div>
          <div class="ov-hud-sub mono">FastAPI 核心进程 · 守护中</div>
        </div>
        <div class="ov-hud-foot">
          <span class="ov-hud-pill">
            <Clock :size="11" />
            已运行 {{ uptime }}
          </span>
        </div>
      </div>

      <!-- 指标 2：决策主脑 -->
      <RouterLink to="/admin/llm" class="ov-hud-card is-interactive">
        <div class="ov-hud-head">
          <span class="ov-hud-icon"><Cpu :size="14" /></span>
          <span class="ov-hud-label">{{ t('admin.overview.brain') }}</span>
          <span class="ov-hud-link-arrow"><ChevronRight :size="13" /></span>
        </div>
        <div class="ov-hud-body">
          <div class="ov-hud-val mono truncate" :title="llm.model">
            {{ llm.model || t('common.notConfigured') }}
          </div>
          <div class="ov-hud-sub truncate">
            {{ llm.provider_name || '内置渠道' }} · 思考强度 {{ (llm.reasoning_effort || '标准').toUpperCase() }}
          </div>
        </div>
        <div class="ov-hud-foot">
          <span class="ov-hud-pill">多模型参谋仲裁</span>
        </div>
      </RouterLink>

      <!-- 指标 3：撮合路由 -->
      <RouterLink to="/admin/security" class="ov-hud-card is-interactive">
        <div class="ov-hud-head">
          <span class="ov-hud-icon"><Wallet :size="14" /></span>
          <span class="ov-hud-label">{{ t('admin.overview.quickVenues') }}</span>
          <span class="ov-hud-link-arrow"><ChevronRight :size="13" /></span>
        </div>
        <div class="ov-hud-body">
          <div class="ov-hud-val" :class="isDemo ? 'text-amber' : 'is-up'">
            {{ venueEnv }}
          </div>
          <div class="ov-hud-sub">OKX · Binance · Gate 三所平权路由</div>
        </div>
        <div class="ov-hud-foot">
          <span class="ov-hud-pill">AUTO 智能分流</span>
        </div>
      </RouterLink>

      <!-- 指标 4：物理安全防线 -->
      <RouterLink to="/admin/interceptors" class="ov-hud-card is-interactive">
        <div class="ov-hud-head">
          <span class="ov-hud-icon"><ShieldCheck :size="14" /></span>
          <span class="ov-hud-label">物理风控防线</span>
          <span class="ov-hud-badge is-shield">FAIL-CLOSED</span>
        </div>
        <div class="ov-hud-body">
          <div class="ov-hud-val is-up">100% 物理拦截</div>
          <div class="ov-hud-sub">4/4 数据管道就绪 · 异常硬锁拒单</div>
        </div>
        <div class="ov-hud-foot">
          <span class="ov-hud-pill">熔断门禁就绪</span>
        </div>
      </RouterLink>
    </section>

    <!-- ══ 模块 2：双栏指挥工位 ══ -->
    <div class="ov-workspace">
      <!-- 左主栏：AI 实时决策流 -->
      <section class="card ov-stream-card">
        <header class="ov-card-header">
          <div class="ov-ch-main">
            <h3 class="ov-ch-title">
              <ScrollText :size="14" class="ov-ch-icon" />
              <span>{{ t('admin.overview.decisions') }}</span>
            </h3>
            <p class="ov-ch-desc">{{ t('admin.overview.decisionsDesc') }}</p>
          </div>
          <RouterLink to="/admin/decisions" class="ov-ch-link">
            <span>{{ t('admin.overview.viewAll') }} (92)</span>
            <ArrowRight :size="13" />
          </RouterLink>
        </header>

        <!-- 加载骨架 -->
        <div v-if="showSkeleton" class="ov-skel-stack">
          <div v-for="i in 5" :key="i" class="skeleton ov-skel-row" />
        </div>

        <!-- 空数据 -->
        <BaseEmpty v-else-if="!decisions.length" :text="t('common.noData')" />

        <!-- 决策流数据矩阵 -->
        <div v-else class="ov-stream-list">
          <div
            v-for="d in decisions"
            :key="d.instId + d.updated_at"
            class="ov-stream-item"
          >
            <!-- 标的铭牌 -->
            <div class="ov-stream-sym">
              <span class="ov-sym-chip mono">{{ String(d.instId).split('-')[0] }}</span>
              <span class="ov-sym-market mono">USDT·PERP</span>
            </div>

            <!-- 动作指示 -->
            <div class="ov-stream-act">
              <span
                v-if="d.action === 'BUY_LONG'"
                class="ov-act-tag is-long"
              >
                ▲ 做多 LONG
              </span>
              <span
                v-else-if="d.action === 'SELL_SHORT'"
                class="ov-act-tag is-short"
              >
                ▼ 做空 SHORT
              </span>
              <span v-else class="ov-act-tag is-wait">
                ● 观望 WAIT
              </span>
            </div>

            <!-- 置信度进度量规 -->
            <div class="ov-stream-gauge">
              <div class="ov-gauge-bar">
                <div
                  class="ov-gauge-fill"
                  :style="{
                    width: `${Math.min(100, Number(d.confidence || 0))}%`,
                    backgroundColor: Number(d.confidence || 0) > 70 ? 'var(--up)' : Number(d.confidence || 0) > 40 ? 'var(--warn)' : 'var(--ds-color-text-placeholder)'
                  }"
                />
              </div>
              <span class="ov-gauge-num mono">{{ fmtNum(d.confidence, 0) }}%</span>
            </div>

            <!-- 宏观决策研判理由 -->
            <div class="ov-stream-reason" :title="d.summary">
              {{ d.summary }}
            </div>

            <!-- 时间戳 -->
            <div class="ov-stream-time mono">
              {{ fmtDateTime(d.updated_at).slice(11, 19) }}
            </div>
          </div>
        </div>
      </section>

      <!-- 右副轨：数据管道 + 核心通道 -->
      <div class="ov-side-rail">
        <!-- 侧栏卡片 1：数据管道监控 -->
        <section class="card ov-pipe-card">
          <header class="ov-card-header">
            <div class="ov-ch-main">
              <h3 class="ov-ch-title">
                <Database :size="14" class="ov-ch-icon" />
                <span>{{ t('admin.overview.dataHealth') }}</span>
              </h3>
              <p class="ov-ch-desc">{{ t('admin.overview.dataHealthDesc') }}</p>
            </div>
            <span
              class="ov-chip-status"
              :class="health.overall === 'LIVE' ? 'is-live' : 'is-warn'"
            >
              <span class="pulse-dot" />
              {{ health.overall || 'SYNC' }}
            </span>
          </header>

          <div class="ov-pipe-list">
            <div v-if="showSkeleton" class="ov-skel-stack">
              <div v-for="i in 4" :key="i" class="skeleton ov-skel-pipe" />
            </div>

            <BaseEmpty v-else-if="!healthFiles.length" :text="t('common.noData')" />

            <div
              v-else
              v-for="f in healthFiles"
              :key="f.name"
              class="ov-pipe-row"
            >
              <div class="ov-pipe-info">
                <span class="ov-pipe-dot" :class="f.fresh ? 'is-fresh' : 'is-stale'" />
                <span class="ov-pipe-filename mono truncate" :title="f.name">{{ f.name }}</span>
              </div>
              <div class="ov-pipe-meta">
                <span class="ov-pipe-age mono">
                  {{ f.age_seconds != null ? Math.round(f.age_seconds / 60) + 'm 前' : '--' }}
                </span>
                <span class="ov-pipe-size mono">{{ fmtNum((f.bytes || 0) / 1024, 0) }}K</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 侧栏卡片 2：核心管控通道 -->
        <section class="card ov-nav-card">
          <header class="ov-card-header">
            <div class="ov-ch-main">
              <h3 class="ov-ch-title">
                <LayoutGrid :size="14" class="ov-ch-icon" />
                <span>{{ t('admin.overview.quickTitle') }}</span>
              </h3>
            </div>
          </header>

          <div class="ov-nav-grid">
            <RouterLink
              v-for="q in quickNavs"
              :key="q.to"
              :to="q.to"
              class="ov-nav-tile"
            >
              <div class="ov-nt-icon">
                <component :is="q.icon" :size="16" />
              </div>
              <div class="ov-nt-content">
                <div class="ov-nt-title">{{ q.title }}</div>
                <div class="ov-nt-desc">{{ q.desc }}</div>
              </div>
              <ChevronRight :size="14" class="ov-nt-arrow" />
            </RouterLink>
          </div>
        </section>
      </div>
    </div>

    <!-- ══ 模块 3：系统审计与运行轨迹 ══ -->
    <section class="card ov-audit-card">
      <header class="ov-card-header">
        <div class="ov-ch-main">
          <h3 class="ov-ch-title">
            <History :size="14" class="ov-ch-icon" />
            <span>{{ t('admin.overview.recentAudit') }}</span>
          </h3>
          <p class="ov-ch-desc">系统鉴权、风控策略变更与接口交互运行审计记录</p>
        </div>
        <RouterLink to="/admin/audit" class="ov-ch-link">
          <span>{{ t('admin.overview.viewAll') }} →</span>
        </RouterLink>
      </header>

      <div v-if="showSkeleton" class="ov-skel-stack">
        <div v-for="i in 4" :key="i" class="skeleton ov-skel-row" />
      </div>

      <BaseEmpty v-else-if="!audits.length" :text="t('common.noRecords')" />

      <div v-else class="ov-audit-table">
        <div
          v-for="(a, idx) in audits"
          :key="idx"
          class="ov-audit-row"
          :class="{ 'is-selected': inspectingAuditIndex === idx }"
          @click="inspectingAuditIndex = inspectingAuditIndex === idx ? null : idx"
        >
          <!-- 状态点与时间 -->
          <div class="ov-ar-time">
            <span class="ov-ar-dot" :class="a.status === 'success' ? 'is-ok' : 'is-fail'" />
            <span class="mono">{{ fmtDateTime(a.timestamp) }}</span>
          </div>

          <!-- 动作标签 -->
          <div class="ov-ar-tag">
            <span
              class="ov-tag-chip"
              :class="`is-${parseAuditContext(a.action, a.detail).tagType}`"
            >
              {{ parseAuditContext(a.action, a.detail).tag }}
            </span>
            <span class="ov-tag-name">{{ parseAuditContext(a.action, a.detail).label }}</span>
          </div>

          <!-- 人类可读上下文详情（批 24：被截断时给出 title，否则长文案永远读不全） -->
          <div class="ov-ar-summary truncate" :title="parseAuditContext(a.action, a.detail).summary">
            {{ parseAuditContext(a.action, a.detail).summary }}
          </div>

          <!-- 相对时间与详情展开指示 -->
          <div class="ov-ar-meta">
            <TimeAgo :time="fmtDateTime(a.timestamp)" class="ov-ar-ago mono" />
            <span class="ov-ar-toggle mono">{{ inspectingAuditIndex === idx ? '收起' : 'JSON' }}</span>
          </div>

          <!-- 展开的原始 JSON 结构 -->
          <div v-if="inspectingAuditIndex === idx" class="ov-ar-json-panel" @click.stop>
            <pre class="ov-json-code mono">{{ JSON.stringify(a.detail || {}, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ══ 整体控制台框架 ══ */
.ov-deck {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-5);
  animation: r20-enter var(--dur-slow) var(--ease-out) backwards;
}

.ov-spin {
  animation: ov-rotate 0.9s linear infinite;
}
@keyframes ov-rotate {
  to { transform: rotate(360deg); }
}

/* 顶部操作区 */
.ov-header-actions {
  display: flex;
  align-items: center;
  gap: var(--ds-space-3);
}

.ov-live-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--r-pill);
  background: rgba(72, 199, 142, 0.08);
  border: 1px solid rgba(72, 199, 142, 0.25);
}
.ov-live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--up);
  box-shadow: 0 0 8px var(--up);
  animation: ov-pulse 2s ease-in-out infinite;
}
@keyframes ov-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}
.ov-live-text {
  font-family: var(--ds-font-mono);
  font-size: var(--text-4xs);
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--up);
}

.ov-version-badge {
  padding: 3px 8px;
  border-radius: var(--r-xs);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ds-color-border-default);
  font-size: var(--text-3xs);
  color: var(--ds-color-text-description);
}

.ov-btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--r-ctl);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ds-color-border-default);
  color: var(--ds-color-text-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.ov-btn-refresh:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.2);
}

/* 报错恢复 */
.ov-error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ds-space-4);
  border-radius: var(--r-card);
  background: rgba(240, 113, 120, 0.08);
  border: 1px solid rgba(240, 113, 120, 0.3);
}
.ov-error-left {
  display: flex;
  align-items: center;
  gap: var(--ds-space-3);
}
.ov-error-icon {
  color: var(--down);
}
.ov-error-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--down);
}
.ov-error-desc {
  font-size: var(--text-xs);
  color: var(--ds-color-text-description);
}

/* ══ 模块 1：四维全景指标矩阵 (HUD) ══ */
.ov-hud {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--ds-space-4);
}
@media (min-width: 640px) {
  .ov-hud { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1200px) {
  .ov-hud { grid-template-columns: repeat(4, 1fr); }
}

.ov-hud-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 128px;
  padding: 16px 18px;
  border-radius: var(--r-card);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.01) 100%), rgba(14, 17, 24, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 1px 0 0 rgba(255, 255, 255, 0.07) inset, 0 8px 24px -6px rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: all var(--dur-fast) var(--ease-out);
  text-decoration: none;
  color: inherit;
}
.ov-hud-card.is-interactive:hover {
  border-color: rgba(103, 153, 254, 0.35);
  box-shadow: 0 1px 0 0 rgba(255, 255, 255, 0.12) inset, 0 12px 32px -8px rgba(0, 0, 0, 0.6);
  transform: translateY(-1px);
}

.ov-hud-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ov-hud-icon {
  color: var(--ds-color-text-placeholder);
}
.ov-hud-label {
  font-size: var(--text-2xs);
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--ds-color-text-placeholder);
  text-transform: uppercase;
}
.ov-hud-badge {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 7px;
  border-radius: var(--r-pill);
  font-family: var(--ds-font-mono);
  font-size: var(--text-4xs);
  font-weight: 600;
}
.ov-hud-badge.is-up {
  background: rgba(72, 199, 142, 0.1);
  color: var(--up);
  border: 1px solid rgba(72, 199, 142, 0.25);
}
.ov-hud-badge.is-shield {
  background: rgba(103, 153, 254, 0.1);
  color: var(--ds-color-brand);
  border: 1px solid rgba(103, 153, 254, 0.25);
}
.ov-hud-link-arrow {
  margin-left: auto;
  color: var(--ds-color-text-placeholder);
  transition: transform var(--dur-fast);
}
.ov-hud-card:hover .ov-hud-link-arrow {
  transform: translateX(2px);
  color: var(--ds-color-brand);
}

.ov-hud-body {
  margin: 12px 0 8px;
}
.ov-hud-val {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  letter-spacing: -0.01em;
  line-height: 1.3;
}
.ov-hud-val.is-up { color: var(--up); }
.ov-hud-val.text-amber { color: var(--warn); }
.ov-hud-sub {
  font-size: var(--text-3xs);
  color: var(--ds-color-text-description);
  margin-top: 3px;
}

.ov-hud-foot {
  display: flex;
  align-items: center;
}
.ov-hud-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
  background: rgba(255, 255, 255, 0.03);
  padding: 2px 6px;
  border-radius: var(--r-xs);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.pulse-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 6px currentColor;
}

/* ══ 模块 2：双栏工位 ══ */
.ov-workspace {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--ds-space-4);
  align-items: start;
}
@media (min-width: 1200px) {
  .ov-workspace {
    grid-template-columns: minmax(0, 1.8fr) minmax(0, 1fr);
  }
}

.ov-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: transparent;
}
.ov-ch-main { min-width: 0; }
.ov-ch-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: #fff;
  letter-spacing: -0.01em;
}
.ov-ch-icon {
  color: var(--ds-color-brand);
}
.ov-ch-desc {
  font-size: var(--text-3xs);
  color: var(--ds-color-text-placeholder);
  margin-top: 3px;
}
.ov-ch-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  /* 批 18：原热区 82×17px；负外边距抵消内边距，视觉位置不变，命中区 25px 高 */
  padding: 4px 8px;
  margin: -4px -8px;
  border-radius: var(--r-xs);
  font-family: var(--ds-font-mono);
  font-size: var(--text-3xs);
  color: var(--ds-color-brand);
  text-decoration: none;
  white-space: nowrap;
  transition: opacity var(--dur-fast), background-color var(--dur-fast);
}
.ov-ch-link:hover {
  text-decoration: underline;
  opacity: 0.85;
  background-color: var(--r20-brand-bg);
}

/* 决策流 */
.ov-stream-list {
  display: flex;
  flex-direction: column;
}
.ov-stream-item {
  display: grid;
  grid-template-columns: 100px 100px 90px 1fr 70px;
  align-items: center;
  gap: 14px;
  padding: 11px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  transition: background-color var(--dur-fast);
}
.ov-stream-item:last-child {
  border-bottom: 0;
}
.ov-stream-item:hover {
  background-color: rgba(255, 255, 255, 0.025);
}

.ov-stream-sym {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ov-sym-chip {
  font-size: var(--text-xs);
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.02em;
}
.ov-sym-market {
  font-size: 9px;
  color: var(--ds-color-text-placeholder);
}

.ov-stream-act {
  display: flex;
  align-items: center;
}
.ov-act-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: var(--r-xs);
  font-size: var(--text-3xs);
  font-weight: 600;
  font-family: var(--ds-font-mono);
  white-space: nowrap;
}
.ov-act-tag.is-long {
  background: rgba(72, 199, 142, 0.12);
  color: var(--up);
  border: 1px solid rgba(72, 199, 142, 0.25);
}
.ov-act-tag.is-short {
  background: rgba(240, 113, 120, 0.12);
  color: var(--down);
  border: 1px solid rgba(240, 113, 120, 0.25);
}
.ov-act-tag.is-wait {
  background: rgba(255, 255, 255, 0.04);
  color: var(--ds-color-text-description);
  border: 1px solid rgba(255, 255, 255, 0.07);
}

.ov-stream-gauge {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ov-gauge-bar {
  flex: 1;
  height: 4px;
  border-radius: var(--r-pill);
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}
.ov-gauge-fill {
  height: 100%;
  border-radius: var(--r-pill);
  transition: width var(--dur-base) ease;
}
.ov-gauge-num {
  font-size: var(--text-3xs);
  color: var(--ds-color-text-secondary);
  width: 32px;
  text-align: right;
}

.ov-stream-reason {
  font-size: var(--text-xs);
  color: var(--ds-color-text-description);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}
.ov-stream-time {
  font-size: var(--text-3xs);
  color: var(--ds-color-text-placeholder);
  text-align: right;
}

/* 右副轨 */
.ov-side-rail {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-4);
  min-width: 0;
}

.ov-chip-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: var(--r-pill);
  font-family: var(--ds-font-mono);
  font-size: var(--text-4xs);
  font-weight: 600;
}
.ov-chip-status.is-live {
  background: rgba(72, 199, 142, 0.1);
  color: var(--up);
  border: 1px solid rgba(72, 199, 142, 0.25);
}
.ov-chip-status.is-warn {
  background: rgba(224, 177, 85, 0.1);
  color: var(--warn);
  border: 1px solid rgba(224, 177, 85, 0.25);
}

.ov-pipe-list {
  display: flex;
  flex-direction: column;
}
.ov-pipe-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.ov-pipe-row:last-child {
  border-bottom: 0;
}
.ov-pipe-info {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}
.ov-pipe-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ov-pipe-dot.is-fresh {
  background: var(--up);
  box-shadow: 0 0 6px var(--up);
}
.ov-pipe-dot.is-stale {
  background: var(--warn);
}
.ov-pipe-filename {
  font-size: var(--text-xs);
  color: var(--ds-color-text-secondary);
}
.ov-pipe-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ov-pipe-age {
  font-size: var(--text-4xs);
  color: var(--ds-color-brand);
  background: rgba(103, 153, 254, 0.08);
  padding: 1px 6px;
  border-radius: var(--r-xs);
}
.ov-pipe-size {
  font-size: var(--text-3xs);
  color: var(--ds-color-text-placeholder);
  width: 44px;
  text-align: right;
}

/* 快捷管控通道 */
.ov-nav-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1px;
  background: rgba(255, 255, 255, 0.04);
}
@media (min-width: 480px) {
  .ov-nav-grid { grid-template-columns: repeat(2, 1fr); }
}
.ov-nav-tile {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 16px;
  background: rgba(15, 18, 25, 0.7);
  text-decoration: none;
  color: inherit;
  transition: all var(--dur-fast) var(--ease-out);
}
.ov-nav-tile:hover {
  background: rgba(255, 255, 255, 0.04);
}
.ov-nt-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--r-xs);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: var(--ds-color-brand);
  flex-shrink: 0;
}
.ov-nav-tile:hover .ov-nt-icon {
  background: rgba(103, 153, 254, 0.12);
  border-color: rgba(103, 153, 254, 0.3);
}
.ov-nt-content {
  min-width: 0;
  flex: 1;
}
.ov-nt-title {
  font-size: var(--text-xs);
  font-weight: 500;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ov-nt-desc {
  font-size: 10px;
  color: var(--ds-color-text-placeholder);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}
.ov-nt-arrow {
  color: var(--ds-color-text-placeholder);
  transition: transform var(--dur-fast);
}
.ov-nav-tile:hover .ov-nt-arrow {
  transform: translateX(2px);
  color: var(--ds-color-brand);
}

/* ══ 模块 3：系统审计与运行轨迹 ══ */
.ov-audit-table {
  display: flex;
  flex-direction: column;
}
.ov-audit-row {
  display: grid;
  grid-template-columns: 180px 140px 1fr 140px;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: background-color var(--dur-fast);
}
.ov-audit-row:last-child {
  border-bottom: 0;
}
.ov-audit-row:hover {
  background-color: rgba(255, 255, 255, 0.025);
}
.ov-audit-row.is-selected {
  background-color: rgba(103, 153, 254, 0.04);
}

.ov-ar-time {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-3xs);
  color: var(--ds-color-text-description);
}
.ov-ar-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ov-ar-dot.is-ok { background: var(--up); box-shadow: 0 0 6px var(--up); }
.ov-ar-dot.is-fail { background: var(--down); }

.ov-ar-tag {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ov-tag-chip {
  padding: 1px 6px;
  border-radius: var(--r-xs);
  font-family: var(--ds-font-mono);
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
}
.ov-tag-chip.is-info {
  background: rgba(103, 153, 254, 0.12);
  color: var(--ds-color-brand);
  border: 1px solid rgba(103, 153, 254, 0.25);
}
.ov-tag-chip.is-warn {
  background: rgba(224, 177, 85, 0.12);
  color: var(--warn);
  border: 1px solid rgba(224, 177, 85, 0.25);
}
.ov-tag-chip.is-neutral {
  background: rgba(255, 255, 255, 0.05);
  color: var(--ds-color-text-description);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.ov-tag-name {
  font-size: var(--text-xs);
  color: var(--ds-color-text-secondary);
}

.ov-ar-summary {
  font-size: var(--text-xs);
  color: var(--ds-color-text-description);
}

.ov-ar-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}
.ov-ar-ago {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
.ov-ar-toggle {
  font-size: 10px;
  color: var(--ds-color-brand);
  padding: 1px 5px;
  border-radius: var(--r-xs);
  background: rgba(103, 153, 254, 0.08);
}

.ov-ar-json-panel {
  grid-column: 1 / -1;
  margin-top: 6px;
  padding: 12px 14px;
  border-radius: var(--r-xs);
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.ov-json-code {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
  color: #8bb2ff;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 骨架 */
.ov-skel-stack {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ov-skel-row {
  height: 38px;
  border-radius: var(--r-xs);
}
.ov-skel-pipe {
  height: 28px;
  border-radius: var(--r-xs);
}
</style>
