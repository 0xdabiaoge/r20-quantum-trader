<script setup lang="ts">
/**
 * PromptStudioPage.vue · 提示词工坊
 * ---------------------------------------------------------------------------
 * 骨架（推倒重来）：
 *   旧 = 简介行 + 工具栏 + 变量条
 *        + 三栏（方案列表 240 / 模块大卡堆 1fr / 预览 400）
 *        + **3 个手写 fixed 遮罩弹窗**（变量字典 / 导入 / 历史）
 *        + 原生 `confirm()` ×2 + 原生 `prompt()` ×2
 *   新 = 共享 PageHeader（动作集中）→ 方案总览带（4 项事实）
 *        → 三栏工作台：方案库 / **模块序列 + 单模块编辑器** / 编译预览
 *        → 4 个弹窗全部改用 BaseDialog；原生 confirm/prompt 全部改为对话框
 *
 * 最大结构变化：**N 张带 textarea 的大卡 → 一条模块序列 + 一个编辑器**。
 * 旧版每个模块都是一张卡、各自带一个 textarea，模块一多就是"textarea 墙"；
 * 新版把顺序与开关收进紧凑序列行，内容只在下方单一编辑器里改（复用原有
 * `activeEditingIdx`，本就是该页的设计意图）。
 *
 * 后端契约（逐字未改）：
 *   GET    /api/v1/admin/prompt-library
 *   PUT    /api/v1/admin/prompt-profiles/{id}              {name,description,enabled,editor_mode,pipelines}
 *   POST   /api/v1/admin/prompt-profiles/{id}/activate     {}
 *   POST   /api/v1/admin/prompt-profiles                   {name,description,source_id}
 *   DELETE /api/v1/admin/prompt-profiles/{id}
 *   GET    /api/v1/admin/prompt-profiles/{id}/history
 *   POST   /api/v1/admin/prompt-profiles/{id}/rollback     {revision_id}
 *   GET    /api/v1/admin/prompt-profiles/{id}/export
 *   POST   /api/v1/admin/prompt-profiles/import            {payload,name_override}
 * 纯逻辑仍全部走 ./promptStudioLogic（未改动）。
 */
import {
  renderSourceBadge, cloneModulesForEditing, compileWorkingModules,
  buildTemplatePreview, computeInsertTarget, appendVariableSlot, deriveImportName,
} from './promptStudioLogic';
import { fmtDate, fmtDateTime } from '../../utils/format';
import { useToast } from '../../composables/useToast';
import { useConfirm } from '../../composables/useConfirm';
const toast = useToast();
const { ask } = useConfirm();
import { ref, computed, onMounted } from 'vue';
import { useI18n } from '../../composables/useI18n';
import PageHeader from '../../components/admin/PageHeader.vue';
import BaseDialog from '../../components/base/BaseDialog.vue';
import BaseSwitch from '../../components/base/BaseSwitch.vue';
import BaseEmpty from '../../components/base/BaseEmpty.vue';
import CopyButton from '../../components/base/CopyButton.vue';
const { t } = useI18n();
import { useApi } from '../../composables/useApi';
import { useAuthStore } from '../../stores/auth';
import {
  Plus, ArrowUp, ArrowDown, Eye, CheckCircle2, Save, AlertTriangle,
  History, RotateCcw, Trash2, Copy, Download, Upload, FileUp,
  Sparkles, BookOpen, Layers, Loader2 } from 'lucide-vue-next';

const { api } = useApi();
const auth = useAuthStore();

const lib = ref<any>(null);
const loading = ref(true);
const loadError = ref('');

const selectedProfileId = ref<string>('');
const activePipeline = ref<'trading_system' | 'trading_user'>('trading_system');
const workingModules = ref<any[]>([]);
const dirty = ref(false);
const historyVisible = ref(false);
const historyList = ref<any[]>([]);

// Import Modal State
const importVisible = ref(false);
const importRawJson = ref('');
const importNameOverride = ref('');
const importFileError = ref('');

// Template Variables & Guide State
const variableGuideVisible = ref(false);
const showVarRibbon = ref(false);
const activeEditingIdx = ref<number>(0);
const previewMode = ref<'rendered' | 'template'>('rendered');

/** 模块来源徽标。三种来源的可信度由后端 update_profile 的逐模块对齐保证。
 * 纯逻辑见 ./promptStudioLogic.ts。 */
function sourceBadge(m: any) {
  return renderSourceBadge(m, t);
}
/** base → 中性；legacy → 警示；custom → 强调 */
function badgeTone(m: any): string {
  const b = sourceBadge(m);
  if (!b) return '';
  if (b.tone === 'legacy') return 'badge-warn';
  if (b.tone === 'custom') return 'badge-accent';
  return '';
}

const pipelines = computed(() => [
  { id: 'trading_system', label: t('admin.promptStudio.pipelines.tradingSystem'), desc: t('admin.promptStudio.pipelines.tradingSystemDesc') },
  { id: 'trading_user', label: t('admin.promptStudio.pipelines.tradingUser'), desc: t('admin.promptStudio.pipelines.tradingUserDesc') },
]);

const selectedProfile = computed(() => (lib.value?.profiles || []).find((p: any) => p.id === selectedProfileId.value) || null);
const templateVariables = computed(() => lib.value?.template_variables || []);

/** 当前编辑中的模块（activeEditingIdx 越界时为 null） */
const selectedModule = computed<any>(() => workingModules.value[activeEditingIdx.value] || null);
const enabledCount = computed(() => workingModules.value.filter((m) => m.enabled).length);
const activePipelineLabel = computed(
  () => pipelines.value.find((p) => p.id === activePipeline.value)?.label || '--',
);
const isActiveProfile = computed(() => selectedProfileId.value === lib.value?.active_profile_id);

const compiledPreview = computed(() => {
  if (previewMode.value === 'template') {
    return buildTemplatePreview(workingModules.value);
  }
  // 无 pipeline_views 时回退到后端给的生效模板（**不**本地编译）
  if (!selectedProfile.value?.pipeline_views) return lib.value?.effective_templates?.[activePipeline.value] || '';
  return compileLocal();
});

function compileLocal(): string {
  return compileWorkingModules(workingModules.value);
}

async function loadLib() {
  loading.value = true;
  loadError.value = '';
  try {
    lib.value = await api('/api/v1/admin/prompt-library');
    if (!selectedProfileId.value || !(lib.value.profiles || []).some((p: any) => p.id === selectedProfileId.value)) {
      selectedProfileId.value = lib.value.active_profile_id || lib.value.profiles?.[0]?.id || '';
    }
    loadWorkingModules();
  } catch (e: any) {
    loadError.value = e.message;
    toast.err(`加载失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

function loadWorkingModules() {
  const views = selectedProfile.value?.pipeline_views?.[activePipeline.value] || [];
  workingModules.value = cloneModulesForEditing(views);
  if (activeEditingIdx.value >= workingModules.value.length) {
    activeEditingIdx.value = Math.max(0, workingModules.value.length - 1);
  }
  dirty.value = false;
}

/** 未保存守卫：原生 confirm → 对话框 */
async function confirmDiscard(desc: string): Promise<boolean> {
  if (!dirty.value) return true;
  return await ask({
    title: t('admin.promptStudio.unsavedSwitchTitle'),
    desc,
    danger: true,
    okText: t('admin.promptStudio.continueAnyway'),
  });
}

async function selectProfile(id: string) {
  if (!(await confirmDiscard(t('admin.promptStudio.unsavedSwitchProfile')))) return;
  selectedProfileId.value = id;
  activeEditingIdx.value = 0;
  loadWorkingModules();
}

async function switchPipeline(id: any) {
  if (!(await confirmDiscard(t('admin.promptStudio.unsavedSwitchPipeline')))) return;
  activePipeline.value = id;
  activeEditingIdx.value = 0;
  loadWorkingModules();
}

function moveModule(idx: number, dir: -1 | 1) {
  const target = idx + dir;
  if (target < 0 || target >= workingModules.value.length) return;
  const arr = workingModules.value;
  ;[arr[idx], arr[target]] = [arr[target], arr[idx]];
  activeEditingIdx.value = target;
  dirty.value = true;
}

function toggleModule(m: any) {
  m.enabled = !m.enabled;
  dirty.value = true;
}

// 在当前激活模块中一键插入变量占位符
function insertVarIntoActiveModule(key: string) {
  const idx = computeInsertTarget(workingModules.value, activeEditingIdx.value);
  if (idx === null) return;
  const m = workingModules.value[idx];
  const { content, duplicate, tag } = appendVariableSlot(m.content, key);
  if (duplicate) {
    toast.warn(`模块「${m.title}」已包含变量 ${tag}`);
    return;
  }
  m.content = content;
  activeEditingIdx.value = idx;
  dirty.value = true;
  toast.ok(`已插入变量插槽 ${tag} 到模块「${m.title}」`);
}

async function saveProfile() {
  try {
    const pipelinesMap: Record<string, any[]> = {}
    for (const p of pipelines.value) {
      pipelinesMap[p.id] = p.id === activePipeline.value
        ? workingModules.value
        : JSON.parse(JSON.stringify(selectedProfile.value.pipeline_views?.[p.id] || [])).map((m: any) => ({ ...m, locked: false }))
    }
    await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: selectedProfile.value.name,
        description: selectedProfile.value.description || '',
        enabled: true,
        editor_mode: 'modules',
        pipelines: pipelinesMap,
      }),
    })
    toast.ok(`方案「${selectedProfile.value.name}」· ${pipelines.value.find(p => p.id === activePipeline.value)?.label} 模块布局已保存，下一轮推演自动生效`)
    dirty.value = false
    await loadLib()
  } catch (e: any) {
    toast.err(`保存失败：${e.message}`)
  }
}

async function activateProfile() {
  try {
    await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}/activate`, { method: 'POST', body: '{}' })
    toast.ok(`已激活方案「${selectedProfile.value?.name}」`)
    await loadLib()
  } catch (e: any) {
    toast.err(`激活失败：${e.message}`)
  }
}

/** 新建 / 复制共用的命名对话框（取代原生 prompt()） */
const nameDialog = ref<{ open: boolean; mode: 'create' | 'duplicate'; value: string; busy: boolean }>({
  open: false,
  mode: 'create',
  value: '',
  busy: false,
});

function openCreateProfile() {
  nameDialog.value = { open: true, mode: 'create', value: '我的策略', busy: false };
}

function openDuplicateProfile() {
  nameDialog.value = {
    open: true,
    mode: 'duplicate',
    value: `${selectedProfile.value?.name || ''} 副本`,
    busy: false,
  };
}

function closeNameDialog() {
  nameDialog.value = { ...nameDialog.value, open: false, value: '', busy: false };
}

async function submitNameDialog() {
  const name = nameDialog.value.value.trim();
  // 与旧版等价：空名称视为取消
  if (!name) return;
  const mode = nameDialog.value.mode;
  nameDialog.value.busy = true;
  try {
    const res = await api('/api/v1/admin/prompt-profiles', {
      method: 'POST',
      body: JSON.stringify({
        name,
        description: '',
        source_id: mode === 'duplicate' ? selectedProfileId.value : 'stable',
      }),
    });
    toast.ok(mode === 'duplicate'
      ? `已复制为可编辑方案「${res.profile.name}」`
      : `已创建可编辑方案「${res.profile.name}」，现在可以自由增删改模块`);
    selectedProfileId.value = res.profile.id;
    closeNameDialog();
    await loadLib();
  } catch (e: any) {
    toast.err(mode === 'duplicate' ? `复制失败：${e.message}` : `创建失败：${e.message}`);
  } finally {
    nameDialog.value.busy = false;
  }
}

function addModule() {
  workingModules.value.push({
    id: `module-${Date.now().toString(36)}`,
    title: `自定义规则模块 ${workingModules.value.length + 1}`,
    content: '',
    enabled: true,
    locked: false,
    source: 'custom',
  })
  activeEditingIdx.value = workingModules.value.length - 1
  dirty.value = true
}

async function removeModule(idx: number) {
  const _ok = await ask({ title: t('admin.promptStudio.confirmDelModuleTitle'), desc: t('admin.promptStudio.confirmDelModuleDesc'), danger: true, okText: t('common.del') })
  if (!_ok) return
  workingModules.value.splice(idx, 1)
  if (activeEditingIdx.value >= workingModules.value.length) {
    activeEditingIdx.value = Math.max(0, workingModules.value.length - 1)
  } else if (activeEditingIdx.value > idx) {
    activeEditingIdx.value -= 1
  }
  dirty.value = true
}

function duplicateModule(idx: number) {
  const m = workingModules.value[idx]
  if (!m) return
  workingModules.value.splice(idx + 1, 0, {
    ...JSON.parse(JSON.stringify(m)),
    id: `module-${Date.now().toString(36)}`,
    title: `${m.title} 副本`,
    locked: false,
    source: 'custom'
  })
  activeEditingIdx.value = idx + 1
  dirty.value = true
}

async function deleteProfile() {
  const _ok = await ask({ title: t('admin.promptStudio.confirmDelProfileTitle'), desc: t('admin.promptStudio.confirmDelProfileDesc', undefined, { name: selectedProfile.value?.name }), danger: true, okText: t('common.del') })
  if (!_ok) return
  try {
    await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}`, { method: 'DELETE' })
    selectedProfileId.value = ''
    await loadLib()
  } catch (e: any) {
    toast.err(`删除失败：${e.message}`)
  }
}

async function showHistory() {
  historyVisible.value = true
  try {
    const res = await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}/history`)
    historyList.value = res.history || []
  } catch (e: any) {
    toast.err(`历史加载失败：${e.message}`)
  }
}

async function rollback(revId: string) {
  const _ok = await ask({ title: t('admin.promptStudio.confirmRollbackTitle'), desc: t('admin.promptStudio.confirmRollbackDesc'), danger: true, okText: t('common.rollback') })
  if (!_ok) return
  try {
    await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ revision_id: revId }),
    })
    toast.ok('已回滚到所选历史版本')
    historyVisible.value = false
    await loadLib()
  } catch (e: any) {
    toast.err(`回滚失败：${e.message}`)
  }
}

// 导出策略方案为 JSON
async function exportProfile() {
  if (!selectedProfileId.value) return
  try {
    const res = await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}/export`)
    const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `r20-strategy-${selectedProfile.value?.name || 'profile'}-${fmtDate(new Date())}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.ok(`方案「${selectedProfile.value?.name}」已成功导出为 JSON 策略包`)
  } catch (e: any) {
    toast.err(`导出失败：${e.message}`)
  }
}

// 处理导入文件选择
function handleFileSelect(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const text = e.target?.result as string
      JSON.parse(text)
      importRawJson.value = text
      importFileError.value = ''
      if (!importNameOverride.value && file.name) {
        importNameOverride.value = deriveImportName(file.name)
      }
    } catch {
      importFileError.value = '文件内容不是合法的 JSON 格式'
    }
  }
  reader.readAsText(file)
}

// 提交导入
async function submitImport() {
  importFileError.value = ''
  if (!importRawJson.value.trim()) {
    importFileError.value = '请先选择 JSON 策略文件或粘贴 JSON 内容'
    return
  }
  try {
    const payload = JSON.parse(importRawJson.value.trim())
    const res = await api('/api/v1/admin/prompt-profiles/import', {
      method: 'POST',
      body: JSON.stringify({
        payload,
        name_override: importNameOverride.value.trim() || undefined,
      }),
    })
    toast.ok(`成功导入策略方案「${res.profile.name}」！`)
    importVisible.value = false
    importRawJson.value = ''
    importNameOverride.value = ''
    selectedProfileId.value = res.profile.id
    await loadLib()
  } catch (e: any) {
    importFileError.value = `导入失败：${e.message}`
  }
}

function copyPreview() {
  navigator.clipboard.writeText(compiledPreview.value)
  toast.ok('编译后实发 Prompt 已复制')
}

onMounted(loadLib)
</script>

<template>
  <div class="ps">
    <PageHeader :title="t('nav.admin.prompts')" :description="t('admin.promptStudio.pageDesc')">
      <template #actions>
        <button
          class="btn btn-sm"
          :class="showVarRibbon ? 'btn-primary' : 'btn-ghost'"
          :title="t('admin.promptStudio.toolbar.varRibbonTitle')"
          @click="showVarRibbon = !showVarRibbon"
        >
          <Layers :size="14" />
          <span>{{ showVarRibbon ? t('admin.promptStudio.toolbar.collapseRibbon') : t('admin.promptStudio.toolbar.insertVars') }}</span>
        </button>
        <button class="btn btn-ghost btn-sm" :title="t('admin.promptStudio.toolbar.dictTitle')" @click="variableGuideVisible = true">
          <BookOpen :size="14" />
          <span>{{ t('admin.promptStudio.toolbar.dictionary') }}</span>
        </button>
        <button class="btn btn-ghost btn-sm" :title="t('admin.promptStudio.toolbar.importTitle')" @click="importVisible = true">
          <Upload :size="14" />
          <span>{{ t('admin.promptStudio.toolbar.import') }}</span>
        </button>
        <button class="btn btn-ghost btn-sm" :title="t('admin.promptStudio.toolbar.exportTitle')" @click="exportProfile">
          <Download :size="14" />
          <span>{{ t('admin.promptStudio.toolbar.export') }}</span>
        </button>
      </template>
    </PageHeader>

    <!-- 载入失败 -->
    <div v-if="loadError" class="state-block is-error ps-error">
      <span class="state-icon"><AlertTriangle :size="17" /></span>
      <p class="state-title">{{ t('common.loadFailed') }}</p>
      <p class="state-desc">{{ t('common.networkError') }}</p>
      <button class="btn btn-ghost btn-sm" style="margin-top: 4px" :disabled="loading" @click="loadLib">
        <Loader2 v-if="loading" :size="14" class="ps-spin" />
        <RotateCcw v-else :size="14" />
        <span>{{ t('common.retry') }}</span>
      </button>
    </div>

    <template v-else>
      <!-- ══ 方案总览带 ══ -->
      <section class="card ps-band">
        <template v-if="loading">
          <div v-for="i in 4" :key="i" class="ps-fact">
            <div class="skeleton skeleton-text" style="width: 46%" />
            <div class="skeleton skeleton-text" style="width: 70%; height: 16px" />
            <div class="skeleton skeleton-text" style="width: 34%" />
          </div>
        </template>

        <template v-else>
          <div class="ps-fact">
            <span class="ps-fact-label">{{ t('admin.promptStudio.bandProfile') }}</span>
            <span class="ps-fact-value truncate" :title="selectedProfile?.name">{{ selectedProfile?.name || '--' }}</span>
            <span class="ps-fact-foot">
              <span v-if="isActiveProfile" class="badge badge-up">{{ t('admin.promptStudio.profiles.active') }}</span>
              <span v-else class="badge">{{ t('admin.promptStudio.bandInactiveFoot') }}</span>
            </span>
          </div>

          <div class="ps-fact">
            <span class="ps-fact-label">{{ t('admin.promptStudio.bandPipeline') }}</span>
            <span class="ps-fact-value truncate">{{ activePipelineLabel }}</span>
            <span class="ps-fact-foot">
              {{ pipelines.find((p) => p.id === activePipeline)?.desc }}
            </span>
          </div>

          <div class="ps-fact">
            <span class="ps-fact-label">{{ t('admin.promptStudio.bandModules') }}</span>
            <span class="ps-fact-value num">{{ workingModules.length }}</span>
            <span class="ps-fact-foot mono">
              {{ t('admin.promptStudio.bandModulesFoot', undefined, { on: enabledCount, total: workingModules.length }) }}
            </span>
          </div>

          <div class="ps-fact">
            <span class="ps-fact-label">{{ t('admin.promptStudio.bandState') }}</span>
            <span class="ps-fact-value" :class="dirty ? 'is-warn' : 'is-up'">
              {{ dirty ? t('admin.promptStudio.bandDirty') : t('admin.promptStudio.bandSynced') }}
            </span>
            <span class="ps-fact-foot">
              {{ dirty ? t('admin.promptStudio.bandDirtyFoot') : t('admin.promptStudio.bandActiveFoot') }}
            </span>
          </div>
        </template>
      </section>

      <!-- 说明条 -->
      <p class="ps-note">
        <Sparkles :size="13" />
        <span>{{ t('admin.promptStudio.intro.note') }}</span>
      </p>

      <!-- 变量快捷条 -->
      <section v-if="showVarRibbon" class="card ps-ribbon">
        <div class="ps-ribbon-head">
          <Layers :size="13" />
          <span class="label-caps">{{ t('admin.promptStudio.ribbon.title') }}</span>
        </div>
        <button
          v-for="v in templateVariables"
          :key="v.key"
          class="ps-var"
          :title="`${v.description}\n${t('admin.promptStudio.ribbon.clickToInsert', undefined, { n: activeEditingIdx + 1 })}`"
          @click="insertVarIntoActiveModule(v.key)"
        >
          <span class="ps-var-name">{{ v.label }}</span>
          <code class="ps-var-key">&#123;&#123;{{ v.key }}&#125;&#125;</code>
        </button>
      </section>

      <!-- ══ 三栏工作台 ══ -->
      <div v-if="loading" class="ps-skel-grid">
        <div v-for="i in 3" :key="i" class="card" style="padding: 16px">
          <div class="skeleton skeleton-text" style="width: 40%" />
          <div class="skeleton skeleton-row" style="margin-top: 12px" />
          <div class="skeleton skeleton-row" style="margin-top: 8px" />
          <div class="skeleton skeleton-row" style="margin-top: 8px" />
        </div>
      </div>

      <div v-else-if="lib" class="ps-grid">
        <!-- 方案库 -->
        <aside class="card ps-lib">
          <header class="card-head">
            <h2 class="card-title">{{ t('admin.promptStudio.profiles.title') }}</h2>
            <button v-if="auth.isSuperadmin" class="btn btn-quiet btn-icon btn-sm" :title="t('admin.promptStudio.profiles.create')" @click="openCreateProfile">
              <Plus :size="14" />
            </button>
          </header>

          <BaseEmpty v-if="!(lib.profiles || []).length" :text="t('admin.promptStudio.profiles.noDesc')" />

          <div v-else class="ps-profiles">
            <button
              v-for="p in lib.profiles"
              :key="p.id"
              class="ps-profile"
              :class="{ 'is-on': selectedProfileId === p.id }"
              @click="selectProfile(p.id)"
            >
              <span class="ps-profile-top">
                <span class="ps-profile-name truncate" :title="p.name">{{ p.name }}</span>
                <span v-if="p.id === lib.active_profile_id" class="dsh-status-dot active" />
              </span>
              <span class="ps-profile-desc truncate" :title="p.description || t('admin.promptStudio.profiles.noDesc')">
                {{ p.description || t('admin.promptStudio.profiles.noDesc') }}
              </span>
            </button>
          </div>
        </aside>

        <!-- 模块编排 -->
        <section class="card ps-center">
          <header class="card-head">
            <div class="seg">
              <button
                v-for="p in pipelines"
                :key="p.id"
                :class="{ 'seg-on': activePipeline === p.id }"
                @click="switchPipeline(p.id)"
              >
                {{ p.label }}
              </button>
            </div>
            <span class="ps-center-note">
              {{ t('admin.promptStudio.modules.currentProfile') }}<b>{{ selectedProfile?.name }}</b>
            </span>
          </header>

          <!-- 模块序列 -->
          <div class="ps-seq">
            <div class="ps-seq-head">
              <h3 class="label-caps">{{ t('admin.promptStudio.moduleSequence') }}</h3>
              <span class="ps-seq-desc">{{ t('admin.promptStudio.moduleSequenceDesc') }}</span>
            </div>

            <BaseEmpty v-if="!workingModules.length" :text="t('admin.promptStudio.noModules')" />

            <div v-else class="ps-seq-list">
              <div
                v-for="(m, idx) in workingModules"
                :key="m.id"
                class="ps-mod"
                :class="{ 'is-on': activeEditingIdx === idx, 'is-off': !m.enabled }"
                @click="activeEditingIdx = idx"
              >
                <span class="ps-mod-n mono">#{{ idx + 1 }}</span>
                <BaseSwitch
                  :model-value="m.enabled"
                  :disabled="!auth.isSuperadmin"
                  :label="m.enabled ? t('admin.promptStudio.modules.enabledTip') : t('admin.promptStudio.modules.disabledTip')"
                  @update:model-value="() => toggleModule(m)"
                />
                <span class="ps-mod-title truncate" :title="m.title">{{ m.title }}</span>
                <span v-if="sourceBadge(m)" class="badge" :class="badgeTone(m)" :title="sourceBadge(m)!.tone === 'base' ? t('admin.promptStudio.source.baseTip') : t('admin.promptStudio.source.otherTip')">
                  {{ sourceBadge(m)!.text }}
                </span>
                <span class="ps-mod-actions">
                  <button class="btn btn-quiet btn-icon btn-sm" :disabled="idx === 0" :title="t('admin.promptStudio.modules.moveUp')" @click.stop="moveModule(idx, -1)">
                    <ArrowUp :size="13" />
                  </button>
                  <button class="btn btn-quiet btn-icon btn-sm" :disabled="idx === workingModules.length - 1" :title="t('admin.promptStudio.modules.moveDown')" @click.stop="moveModule(idx, 1)">
                    <ArrowDown :size="13" />
                  </button>
                  <button class="btn btn-quiet btn-icon btn-sm" :title="t('admin.promptStudio.modules.duplicate')" @click.stop="duplicateModule(idx)">
                    <Copy :size="13" />
                  </button>
                  <button class="btn btn-quiet btn-icon btn-sm ps-del" :title="t('admin.promptStudio.modules.delete')" @click.stop="removeModule(idx)">
                    <Trash2 :size="13" />
                  </button>
                </span>
              </div>
            </div>

            <button class="btn btn-ghost btn-sm ps-add" @click="addModule">
              <Plus :size="14" />
              <span>{{ t('admin.promptStudio.modules.add') }}</span>
            </button>
          </div>

          <!-- 单模块编辑器 -->
          <div class="ps-editor">
            <BaseEmpty v-if="!selectedModule" :text="t('admin.promptStudio.moduleEditorEmpty')" />

            <template v-else>
              <div class="ps-editor-head">
                <h3 class="label-caps">{{ t('admin.promptStudio.moduleEditor') }}</h3>
                <span class="badge mono">#{{ activeEditingIdx + 1 }}</span>
              </div>
              <input
                v-model="selectedModule.title"
                class="field ps-title-input"
                :readonly="!auth.isSuperadmin"
                :placeholder="t('admin.promptStudio.modules.titlePlaceholder')"
                @input="dirty = true"
              />
              <textarea
                v-model="selectedModule.content"
                rows="12"
                class="field ps-textarea"
                :readonly="!auth.isSuperadmin"
                :placeholder="t('admin.promptStudio.modules.contentPlaceholder')"
                @input="dirty = true"
              />
            </template>
          </div>

          <!-- 动作栏 -->
          <footer class="ps-actions">
            <div class="ps-actions-left">
              <button class="btn btn-primary btn-sm" :disabled="!dirty || !auth.isSuperadmin" @click="saveProfile">
                <Save :size="14" />
                <span>{{ t('admin.promptStudio.modules.save') }}{{ dirty ? ' *' : '' }}</span>
              </button>
              <button
                v-if="!isActiveProfile && auth.isSuperadmin"
                class="btn btn-ghost btn-sm ps-activate"
                @click="activateProfile"
              >
                <CheckCircle2 :size="14" />
                <span>{{ t('admin.promptStudio.modules.activate') }}</span>
              </button>
            </div>

            <div class="ps-actions-right">
              <button v-if="auth.isSuperadmin" class="btn btn-ghost btn-sm" @click="openDuplicateProfile">
                <Copy :size="14" />
                <span>{{ t('admin.promptStudio.modules.duplicateProfile') }}</span>
              </button>
              <button class="btn btn-ghost btn-sm" @click="showHistory">
                <History :size="14" />
                <span>{{ t('admin.promptStudio.modules.history') }}</span>
              </button>
              <button v-if="!isActiveProfile && auth.isSuperadmin" class="btn btn-danger btn-sm" @click="deleteProfile">
                <Trash2 :size="14" />
                <span>{{ t('admin.promptStudio.modules.deleteProfile') }}</span>
              </button>
            </div>
          </footer>
        </section>

        <!-- 编译预览 -->
        <section class="card ps-prev">
          <header class="card-head">
            <h2 class="card-title"><Eye :size="14" />{{ t('admin.promptStudio.preview.title') }}</h2>
            <div class="ps-prev-actions">
              <div class="seg">
                <button :class="{ 'seg-on': previewMode === 'rendered' }" @click="previewMode = 'rendered'">
                  {{ t('admin.promptStudio.preview.rendered') }}
                </button>
                <button :class="{ 'seg-on': previewMode === 'template' }" @click="previewMode = 'template'">
                  {{ t('admin.promptStudio.preview.template') }}
                </button>
              </div>
              <CopyButton :text="compiledPreview" />
            </div>
          </header>

          <div class="ps-prev-meta">
            <span>{{ previewMode === 'rendered' ? t('admin.promptStudio.preview.hintRendered') : t('admin.promptStudio.preview.hintTemplate') }}</span>
            <span class="num ps-prev-count">{{ t('admin.promptStudio.preview.charCount', undefined, { n: compiledPreview.length }) }}</span>
          </div>

          <pre class="ps-preview">{{ compiledPreview || t('admin.promptStudio.preview.empty') }}</pre>

          <button class="btn btn-ghost btn-sm ps-prev-copy" @click="copyPreview">
            <Copy :size="13" />
            <span>{{ t('admin.promptStudio.preview.copy') }}</span>
          </button>
        </section>
      </div>
    </template>

    <!-- ══ 变量字典 ══ -->
    <BaseDialog
      :open="variableGuideVisible"
      :title="t('admin.promptStudio.dictionary.title')"
      :desc="t('admin.promptStudio.dictionary.desc')"
      size="xl"
      @close="variableGuideVisible = false"
    >
      <div class="ps-dict">
        <article v-for="v in templateVariables" :key="v.key" class="ps-dict-item">
          <header class="ps-dict-head">
            <span class="badge badge-accent">{{ v.category }}</span>
            <span class="ps-dict-label">{{ v.label }}</span>
            <code class="ps-dict-key">&#123;&#123;{{ v.key }}&#125;&#125;</code>
            <button
              class="btn btn-primary btn-sm ps-dict-insert"
              @click="insertVarIntoActiveModule(v.key); variableGuideVisible = false"
            >
              {{ t('admin.promptStudio.dictionary.insert') }}
            </button>
          </header>
          <p class="ps-dict-desc">{{ v.description }}</p>
          <pre v-if="v.sample" class="code-block ps-dict-sample">{{ v.sample }}</pre>
        </article>

        <BaseEmpty v-if="!templateVariables.length" :text="t('common.noData')" />
      </div>
    </BaseDialog>

    <!-- ══ 导入方案 ══ -->
    <BaseDialog
      :open="importVisible"
      :title="t('admin.promptStudio.import.title')"
      :desc="t('admin.promptStudio.import.desc')"
      size="lg"
      @close="importVisible = false"
    >
      <div class="ps-import">
        <div v-if="importFileError" class="ps-import-error">
          <AlertTriangle :size="13" />
          <span>{{ importFileError }}</span>
        </div>

        <div class="ps-field">
          <span class="form-label">{{ t('admin.promptStudio.import.methodOne') }}</span>
          <label class="ps-file">
            <FileUp :size="14" />
            <span>{{ t('admin.promptStudio.import.chooseFile') }}</span>
            <input type="file" accept=".json" class="ps-file-input" @change="handleFileSelect" />
          </label>
        </div>

        <div class="ps-field">
          <span class="form-label">{{ t('admin.promptStudio.import.methodTwo') }}</span>
          <textarea
            v-model="importRawJson"
            rows="7"
            class="field ps-textarea mono"
            placeholder='{"format": "r20-prompt-profile", "version": 3, "profile": { ... }}'
          />
        </div>

        <div class="ps-field">
          <span class="form-label">{{ t('admin.promptStudio.import.nameLabel') }}</span>
          <input
            v-model="importNameOverride"
            type="text"
            class="field"
            :placeholder="t('admin.promptStudio.import.namePlaceholder')"
          />
        </div>
      </div>

      <template #footer>
        <button class="btn btn-ghost btn-sm" @click="importVisible = false">
          {{ t('admin.promptStudio.import.cancel') }}
        </button>
        <button class="btn btn-primary btn-sm" @click="submitImport">
          <Upload :size="14" />
          <span>{{ t('admin.promptStudio.import.confirm') }}</span>
        </button>
      </template>
    </BaseDialog>

    <!-- ══ 版本历史 ══ -->
    <BaseDialog
      :open="historyVisible"
      :title="`${t('admin.promptStudio.history.title')} · ${selectedProfile?.name || ''}`"
      size="md"
      @close="historyVisible = false"
    >
      <BaseEmpty v-if="!historyList.length" :text="t('admin.promptStudio.history.empty')" />

      <div v-else class="ps-history">
        <div v-for="h in historyList" :key="h.id || h.revision_id" class="ps-history-row">
          <div class="ps-history-text">
            <span class="ps-history-note">{{ h.note || h.summary || h.id || h.revision_id }}</span>
            <span class="ps-history-meta mono">{{ fmtDateTime(h.created_at || h.time) }} · {{ h.actor || 'system' }}</span>
          </div>
          <button class="btn btn-ghost btn-sm" @click="rollback(h.id || h.revision_id)">
            <RotateCcw :size="13" />
            <span>{{ t('admin.promptStudio.history.rollback') }}</span>
          </button>
        </div>
      </div>
    </BaseDialog>

    <!-- ══ 新建 / 复制方案 ══ -->
    <BaseDialog
      :open="nameDialog.open"
      :title="nameDialog.mode === 'duplicate' ? t('admin.promptStudio.duplicateTitle') : t('admin.promptStudio.newProfileTitle')"
      :desc="nameDialog.mode === 'duplicate' ? t('admin.promptStudio.duplicateDesc') : t('admin.promptStudio.newProfileDesc')"
      size="sm"
      @close="closeNameDialog"
    >
      <label class="ps-field">
        <span class="form-label">{{ t('admin.promptStudio.nameLabel') }}</span>
        <input
          v-model="nameDialog.value"
          type="text"
          class="field"
          :placeholder="t('admin.promptStudio.namePlaceholder')"
          @keyup.enter="submitNameDialog"
        />
      </label>

      <template #footer>
        <button class="btn btn-ghost btn-sm" @click="closeNameDialog">{{ t('common.cancel') }}</button>
        <button
          class="btn btn-primary btn-sm"
          :disabled="!nameDialog.value.trim() || nameDialog.busy"
          @click="submitNameDialog"
        >
          {{ nameDialog.mode === 'duplicate' ? t('admin.promptStudio.duplicate') : t('admin.promptStudio.create') }}
        </button>
      </template>
    </BaseDialog>
  </div>
</template>

<style scoped>
.ps {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-4);
}
.ps-spin {
  animation: ps-rotate 0.9s linear infinite;
}
@keyframes ps-rotate {
  to {
    transform: rotate(360deg);
  }
}
.ps-error {
  border: 1px solid var(--down-line);
  border-radius: var(--r-card);
  background-color: var(--ds-color-bg-surface-card);
}

/* ══ 方案总览带 ══ */
.ps-band {
  display: grid;
  grid-template-columns: 1fr;
}
@media (min-width: 640px) {
  .ps-band {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (min-width: 1280px) {
  .ps-band {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.ps-fact {
  display: flex;
  flex-direction: column;
  gap:4px;
  min-width: 0;
  padding: var(--ds-space-4);
  border-top: 1px solid var(--ds-color-border-default);
}
.ps-fact:first-child {
  border-top: 0;
}
@media (min-width: 640px) {
  .ps-fact:nth-child(2) {
    border-top: 0;
  }
  .ps-fact:nth-child(even) {
    border-left: 1px solid var(--ds-color-border-default);
  }
}
@media (min-width: 1280px) {
  .ps-fact {
    border-top: 0;
  }
  .ps-fact + .ps-fact {
    border-left: 1px solid var(--ds-color-border-default);
  }
}
.ps-fact-label {
  font-size: var(--text-3xs);
  font-weight: 500;
  letter-spacing: var(--track-label);
  text-transform: uppercase;
  color: var(--ds-color-text-placeholder);
}
.ps-fact-value {
  font-size: var(--text-lg);
  font-weight: 500;
  letter-spacing: var(--track-display);
  line-height: 1.2;
  color: var(--ds-color-text-primary);
}
.ps-fact-value.is-warn {
  color: var(--warn);
}
.ps-fact-value.is-up {
  color: var(--up);
}
.ps-fact-foot {
  display: flex;
  align-items: center;
  font-size: var(--text-3xs);
  color: var(--ds-color-text-placeholder);
  min-width: 0;
}

/* 说明条 */
.ps-note {
  display: flex;
  align-items: flex-start;
  gap:8px;
  padding:10px var(--ds-space-4);
  border-radius: var(--r-ctl);
  background-color: var(--ds-color-bg-surface-inset);
  font-size: var(--text-3xs);
  line-height: var(--leading-body);
  color: var(--ds-color-text-description);
}
.ps-note > svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--ds-color-brand);
}

/* 变量条 */
.ps-ribbon {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: var(--ds-space-3) var(--ds-space-4);
}
.ps-ribbon-head {
  display: flex;
  align-items: center;
  gap:6px;
  color: var(--ds-color-brand);
  margin-right: 4px;
}
.ps-var {
  display: inline-flex;
  align-items: center;
  gap:6px;
  padding:4px 8px;
  border-radius: var(--r-xs);
  border: 1px solid var(--ds-color-border-default);
  background-color: var(--ds-color-bg-surface-1);
  cursor: pointer;
  transition: border-color var(--dur-fast), color var(--dur-fast);
}
.ps-var:hover {
  border-color: var(--ds-color-brand);
}
.ps-var-name {
  font-size: var(--text-3xs);
  color: var(--ds-color-text-secondary);
}
.ps-var-key {
  font-family: var(--ds-font-mono);
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}

/* ══ 三栏工作台 ══ */
.ps-skel-grid {
  display: grid;
  gap: var(--ds-space-4);
  grid-template-columns: 1fr;
}
@media (min-width: 1024px) {
  .ps-skel-grid {
    grid-template-columns: 250px minmax(0, 1fr);
  }
}
.ps-grid {
  display: grid;
  gap: var(--ds-space-4);
  align-items: start;
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: 'lib' 'center' 'prev';
}
@media (min-width: 1024px) {
  .ps-grid {
    grid-template-columns: 250px minmax(0, 1fr);
    grid-template-areas: 'lib center' 'prev prev';
  }
}
@media (min-width: 1280px) {
  .ps-grid {
    grid-template-columns: 250px minmax(0, 1fr) 380px;
    grid-template-areas: 'lib center prev';
    /* 批 18：三栏等高，方案库不再在下方留一大片空白（原 align-items:start） */
    align-items: stretch;
  }
  .ps-profiles {
    flex: 1 1 auto;
    min-height: 0;
    max-height: none;
  }
}
.ps-lib {
  grid-area: lib;
}
.ps-center {
  grid-area: center;
  min-width: 0;
}
.ps-prev {
  grid-area: prev;
  min-width: 0;
}

/* 方案库 */
.ps-profiles {
  display: flex;
  flex-direction: column;
  padding: var(--ds-space-1) 0;
  max-height: 60vh;
  overflow-y: auto;
}
.ps-profile {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px var(--ds-space-4);
  text-align: left;
  border-left: 2px solid transparent;
  cursor: pointer;
  transition: background-color var(--dur-fast);
}
.ps-profile:hover {
  background-color: var(--ds-color-bg-hover);
}
.ps-profile.is-on {
  background-color: var(--ds-color-bg-surface-1);
  border-left-color: var(--ds-color-brand);
}
.ps-profile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-2);
  min-width: 0;
}
.ps-profile-name {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--ds-color-text-primary);
}
.ps-profile-desc {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}

/* 模块序列 */
.ps-center-note {
  font-size: var(--text-3xs);
  color: var(--ds-color-text-placeholder);
}
.ps-center-note b {
  color: var(--ds-color-text-primary);
  font-weight: 600;
  margin-left:4px;
}
.ps-seq {
  padding: var(--ds-space-3) var(--ds-space-4);
  border-bottom: 1px solid var(--ds-color-border-default);
}
.ps-seq-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ds-space-3);
  flex-wrap: wrap;
  margin-bottom: var(--ds-space-2);
}
.ps-seq-desc {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
.ps-seq-list {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--ds-color-border-default);
  border-radius: var(--r-ctl);
  overflow: hidden;
}
.ps-mod {
  display: grid;
  grid-template-columns: 30px auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: var(--ds-space-3);
  min-height: 38px;
  padding: 0 var(--ds-space-3);
  border-bottom: 1px solid var(--ds-color-border-default);
  border-left: 2px solid transparent;
  cursor: pointer;
  transition: background-color var(--dur-fast);
}
.ps-mod:last-child {
  border-bottom: 0;
}
.ps-mod:hover {
  background-color: var(--ds-color-bg-hover);
}
.ps-mod.is-on {
  background-color: var(--ds-color-bg-surface-1);
  border-left-color: var(--ds-color-brand);
}
.ps-mod.is-off {
  opacity: 0.5;
}
.ps-mod-n {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
.ps-mod-title {
  font-size: var(--text-xs);
  color: var(--ds-color-text-primary);
  min-width: 0;
}
.ps-mod-actions {
  display: flex;
  align-items: center;
  gap: 1px;
}
.ps-del {
  color: var(--down);
}
.ps-add {
  margin-top: var(--ds-space-3);
  width: 100%;
  border: 1px dashed var(--ds-color-border-strong);
  justify-content: center;
}

/* 单模块编辑器 */
.ps-editor {
  padding: var(--ds-space-4);
}
.ps-editor-head {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  margin-bottom: var(--ds-space-3);
}
.ps-title-input {
  width: 100%;
  font-weight: 600;
  margin-bottom: var(--ds-space-3);
}
.ps-textarea {
  width: 100%;
  resize: vertical;
  line-height: var(--leading-body);
  font-family: inherit;
}

/* 动作栏 */
.ps-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
  flex-wrap: wrap;
  padding: var(--ds-space-3) var(--ds-space-4);
  border-top: 1px solid var(--ds-color-border-default);
  background-color: var(--ds-color-bg-surface-inset);
}
.ps-actions-left,
.ps-actions-right {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  flex-wrap: wrap;
}
.ps-activate {
  color: var(--up);
}

/* 预览 */
.ps-prev-actions {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
}
.ps-prev-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
  padding: var(--ds-space-3) var(--ds-space-4) 0;
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
.ps-prev-count {
  color: var(--ds-color-brand);
  white-space: nowrap;
}
.ps-preview {
  margin: var(--ds-space-3) var(--ds-space-4) 0;
  padding: var(--ds-space-3);
  border-radius: var(--r-ctl);
  background-color: var(--ds-color-bg-code);
  border: 1px solid var(--ds-color-border-default);
  font-family: var(--ds-font-mono);
  font-size: var(--text-2xs);
  line-height: var(--leading-body);
  color: var(--ds-color-text-secondary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 56vh;
  overflow-y: auto;
}
.ps-prev-copy {
  margin: var(--ds-space-3) var(--ds-space-4) var(--ds-space-4);
}

/* 变量字典 */
.ps-dict {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-3);
}
.ps-dict-item {
  padding: var(--ds-space-3);
  border-radius: var(--r-ctl);
  background-color: var(--ds-color-bg-surface-inset);
}
.ps-dict-head {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  flex-wrap: wrap;
}
.ps-dict-label {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ds-color-text-primary);
}
.ps-dict-key {
  padding: 2px 6px;
  border-radius: var(--r-xs);
  background-color: var(--ds-color-bg-surface-1);
  font-family: var(--ds-font-mono);
  font-size: var(--text-4xs);
  color: var(--warn);
}
.ps-dict-insert {
  margin-left: auto;
}
.ps-dict-desc {
  margin-top: 6px;
  font-size: var(--text-3xs);
  line-height: var(--leading-body);
  color: var(--ds-color-text-description);
}
.ps-dict-sample {
  margin-top: var(--ds-space-2);
  max-height: 120px;
  font-size: var(--text-4xs);
}

/* 导入 */
.ps-import {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-4);
}
.ps-import-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 10px;
  border-radius: var(--r-ctl);
  background-color: var(--down-bg);
  color: var(--down);
  font-size: var(--text-3xs);
}
.ps-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ps-file {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  align-self: flex-start;
  padding:8px 12px;
  border-radius: var(--r-ctl);
  border: 1px dashed var(--ds-color-border-strong);
  color: var(--ds-color-brand);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: border-color var(--dur-fast);
}
.ps-file:hover {
  border-color: var(--ds-color-brand);
}
.ps-file-input {
  display: none;
}

/* 历史 */
.ps-history {
  display: flex;
  flex-direction: column;
}
.ps-history-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
  padding: 10px 0;
  border-bottom: 1px solid var(--ds-color-border-default);
}
.ps-history-row:last-child {
  border-bottom: 0;
}
.ps-history-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.ps-history-note {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--ds-color-text-primary);
}
.ps-history-meta {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
</style>
