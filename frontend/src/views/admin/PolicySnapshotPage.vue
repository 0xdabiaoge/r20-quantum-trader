<script setup lang="ts">
import { fmtDateTime, utcStrToBj } from '../../utils/format';
import { useToast } from '../../composables/useToast'
import { useConfirm } from '../../composables/useConfirm'
const toast = useToast()
const { ask } = useConfirm()
import { ref, onMounted } from 'vue'
import { useI18n } from '../../composables/useI18n'
const { t } = useI18n()
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import {Layers,
  FileText,
  Sparkles,
  ShieldCheck,
  Users,
  RefreshCw,
  Hash,
  Activity,
  Clock,
  ArrowUpRight,
  BookmarkPlus,
  RotateCcw,
  Archive,
  Trash2} from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()

const loading = ref(true)
const refreshing = ref(false)
const archiving = ref(false)
const restoring = ref(false)
const deleting = ref<string | null>(null)

const snapshotData = ref<any>(null)
const archives = ref<any[]>([])
const errorMsg = ref<string | null>(null)

// Archive Dialog State
const showArchiveModal = ref(false)
const archiveName = ref('')
const archiveDesc = ref('')

async function fetchSnapshot() {
  refreshing.value = true
  errorMsg.value = null
  try {
    const [snapRes, arcRes] = await Promise.all([
      api('/api/v1/admin/policy/current-snapshot'),
      api('/api/v1/admin/policy/archives'),
    ])
    if (snapRes && snapRes.ok) {
      snapshotData.value = snapRes
    }
    if (arcRes && arcRes.ok) {
      archives.value = arcRes.archives || []
    }
  } catch (err: any) {
    errorMsg.value = err.message || t('admin.policySnapshot.err.fetchFailed')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function saveArchive() {
  if (!auth.isSuperadmin) {
    toast.err(t('admin.policySnapshot.err.notSuperadmin'))
    return
  }
  if (!archiveName.value.trim()) {
    toast.warn(t('admin.policySnapshot.err.nameRequired'))
    return
  }
  archiving.value = true
  try {
    const res = await api('/api/v1/admin/policy/archive', {
      method: 'POST',
      body: JSON.stringify({
        name: archiveName.value.trim(),
        description: archiveDesc.value.trim(),
      }),
    })
    if (res && res.ok) {
      toast.ok(t('admin.policySnapshot.toast.archivedOk', undefined, { name: res.entry?.name, hash: res.entry?.policy_hash }))
      showArchiveModal.value = false
      archiveName.value = ''
      archiveDesc.value = ''
      await fetchSnapshot()
    }
  } catch (err: any) {
    toast.err(t('admin.policySnapshot.err.archiveFailed', undefined, { msg: err.message }))
  } finally {
    archiving.value = false
  }
}

async function restorePolicy(hash: string, name: string) {
  if (!auth.isSuperadmin) return
  // 批C: 原生 confirm → 项目确认服务（恢复快照会覆盖当前生效策略）
  const _ok = await ask({ title: t('admin.policySnapshot.confirm.restore', undefined, { name, hash }), danger: true, okText: '恢复' })
  if (!_ok) return
  restoring.value = true
  try {
    const res = await api('/api/v1/admin/policy/restore', {
      method: 'POST',
      body: JSON.stringify({ policy_hash: hash }),
    })
    if (res && res.ok) {
      toast.ok(t('admin.policySnapshot.toast.restoredOk', undefined, { name, hash }))
      await fetchSnapshot()
    }
  } catch (err: any) {
    toast.err(t('admin.policySnapshot.err.restoreFailed', undefined, { msg: err.message }))
  } finally {
    restoring.value = false
  }
}

async function deleteArchive(hash: string, name: string) {
  if (!auth.isSuperadmin) return
  const _ok = await ask({ title: t('admin.policySnapshot.confirm.delete', undefined, { name, hash }), danger: true, okText: '删除' })
  if (!_ok) return
  deleting.value = hash
  try {
    const res = await api(`/api/v1/admin/policy/archive/${hash}`, {
      method: 'DELETE',
    })
    if (res && res.ok) {
      toast.ok(t('admin.policySnapshot.toast.deletedOk', undefined, { name }))
      await fetchSnapshot()
    }
  } catch (err: any) {
    toast.err(t('admin.policySnapshot.err.deleteFailed', undefined, { msg: err.message }))
  } finally {
    deleting.value = null
  }
}

function formatTimestamp(ts: number) {
  if (!ts) return t('admin.policySnapshot.notRecorded')
  return fmtDateTime(ts * 1000)
}

onMounted(() => {
  fetchSnapshot()
})
</script>

<template>
  <div class="space-y-4">
    <!-- Notice Banner -->
    <!-- Header Control Station -->
    <div
      class="rounded-2xl border p-4 sm:p-5 2xl:p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
      style="background-color: var(--surface-2); border-color: var(--line-1);"
    >
      <div class="flex items-center space-x-3">
        <div
          class="p-2.5 2xl:p-3 rounded-xl border"
          style="background-color: var(--accent-bg); border-color: var(--accent-line); color: var(--accent);"
        >
          <Layers class="w-5 h-5 2xl:w-6 2xl:h-6" />
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h2 class="text-sm 2xl:text-base font-bold" style="color: var(--ink-1);">
              {{ t('nav.admin.policy') }}
            </h2>
            <span
              v-if="snapshotData?.policy_version"
              class="text-[11px] 2xl:text-xs font-bold px-2 py-0.5 rounded border"
              style="background-color: var(--accent-bg); color: var(--accent); border-color: var(--accent-line);"
            >
              {{ snapshotData.policy_version }}
            </span>
          </div>
          <p class="text-xs 2xl:text-sm mt-0.5" style="color: var(--ink-2);">{{ t('admin.policySnapshot.desc') }}</p>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <!-- Archive Button -->
        <button
          @click="showArchiveModal = true"
          :disabled="!auth.isSuperadmin"
          class="flex items-center space-x-1.5 px-3 py-1.5 2xl:px-4 2xl:py-2 rounded-xl text-xs 2xl:text-sm font-bold cursor-pointer transition-all shadow-xs"
          style="background-color: var(--accent); color: var(--accent-ink);"
        >
          <BookmarkPlus class="w-3.5 h-3.5 2xl:w-4 2xl:h-4" />
          <span>{{ t('admin.policySnapshot.btn.archive') }}</span>
        </button>

        <!-- Refresh Button -->
        <button
          @click="fetchSnapshot"
          :disabled="refreshing"
          class="flex items-center space-x-1.5 px-3 py-1.5 2xl:px-4 2xl:py-2 rounded-xl border text-xs 2xl:text-sm font-bold cursor-pointer transition-all shadow-xs"
          style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);"
        >
          <RefreshCw class="w-3.5 h-3.5 2xl:w-4 2xl:h-4" :class="{ 'animate-spin': refreshing }" />
          <span>{{ refreshing ? t('admin.policySnapshot.btn.refreshing') : t('admin.policySnapshot.btn.refresh') }}</span>
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div
      v-if="errorMsg"
      class="p-3 rounded-xl text-xs border bg-rose-500/10 border-rose-500/20 text-rose-400"
    >
      {{ errorMsg }}
    </div>

    <!-- Loading Skeleton -->
    <div v-if="loading" class="py-12 text-center text-xs text-zinc-500">
      {{ t('admin.policySnapshot.loading') }}
    </div>

    <div v-else-if="snapshotData?.snapshot" class="space-y-4 2xl:space-y-6">
      <!-- 1. Master Identity Bar -->
      <div
        class="grid grid-cols-1 sm:grid-cols-3 gap-3 2xl:gap-4 p-4 2xl:p-5 rounded-2xl border text-xs 2xl:text-sm"
        style="background-color: var(--surface-1); border-color: var(--line-1);"
      >
        <div class="flex items-center space-x-2">
          <Hash class="w-4 h-4 2xl:w-5 2xl:h-5 text-purple-400 shrink-0" />
          <div>
            <div class="text-[11px] 2xl:text-xs text-[var(--ink-2)]">{{ t('admin.policySnapshot.identity.activeVersion') }}</div>
            <div class="font-bold text-sm 2xl:text-base mt-0.5" style="color: var(--ink-1);">
              {{ snapshotData.snapshot.policy_version }}
            </div>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <Activity class="w-4 h-4 2xl:w-5 2xl:h-5 text-cyan-400 shrink-0" />
          <div>
            <div class="text-[11px] 2xl:text-xs text-[var(--ink-2)]">{{ t('admin.policySnapshot.identity.hash') }}</div>
            <div class="font-bold text-sm 2xl:text-base mt-0.5 text-cyan-400">
              #{{ snapshotData.snapshot.policy_hash }}
            </div>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <Clock class="w-4 h-4 2xl:w-5 2xl:h-5 text-emerald-400 shrink-0" />
          <div>
            <div class="text-[11px] 2xl:text-xs text-[var(--ink-2)]">{{ t('admin.policySnapshot.identity.generatedAt') }}</div>
            <div class="font-bold text-sm 2xl:text-base mt-0.5 text-emerald-400">
              {{ formatTimestamp(snapshotData.snapshot.timestamp) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Four Strategy Units Matrix -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 2xl:gap-5">
        <!-- Unit 1: Prompt Policy -->
        <div
          class="p-4 sm:p-5 rounded-2xl border space-y-3 flex flex-col justify-between"
          style="background-color: var(--surface-2); border-color: var(--line-1);"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--line-1);">
              <div class="flex items-center space-x-2">
                <span class="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
                  <FileText class="w-4 h-4" />
                </span>
                <span class="font-bold text-xs" style="color: var(--ink-1);">{{ t('admin.policySnapshot.unit.prompt.title') }}</span>
              </div>
              <router-link
                to="/admin/promptlib"
                class="text-[11px] text-blue-400 flex items-center hover:underline"
              >
                <span>{{ t('admin.policySnapshot.unit.enter') }}</span>
                <ArrowUpRight class="w-3 h-3 ml-0.5" />
              </router-link>
            </div>

            <div class="space-y-1 text-xs">
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.prompt.profile') }}</span>
                <span class="font-bold" style="color: var(--ink-1);">
                  {{ snapshotData.snapshot.units?.prompt_profile?.active_profile_name || snapshotData.snapshot.units?.prompt_profile?.active_profile_id }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.prompt.layoutHash') }}</span>
                <span class="text-blue-400 font-bold">#{{ snapshotData.snapshot.units?.prompt_profile?.layout_hash }}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.prompt.mode') }}</span>
                <span style="color: var(--ink-1);">{{ snapshotData.snapshot.units?.prompt_profile?.editor_mode }}</span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.prompt.slotGuard') }}</span>
                <span class="text-emerald-400 font-bold">{{ t('admin.policySnapshot.unit.prompt.slotGuardValue') }}</span>
              </div>
            </div>
          </div>

          <div class="p-2 rounded-xl text-[11px]" style="background-color: var(--surface-1); color: var(--ink-2);">
            {{ t('admin.policySnapshot.unit.prompt.note') }}
          </div>
        </div>

        <!-- Unit 2: Evolution Shield -->
        <div
          class="p-4 sm:p-5 rounded-2xl border space-y-3 flex flex-col justify-between"
          style="background-color: var(--surface-2); border-color: var(--line-1);"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--line-1);">
              <div class="flex items-center space-x-2">
                <span class="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <Sparkles class="w-4 h-4" />
                </span>
                <span class="font-bold text-xs" style="color: var(--ink-1);">{{ t('admin.policySnapshot.unit.evolution.title') }}</span>
              </div>
              <router-link
                to="/admin/evolution"
                class="text-[11px] text-emerald-400 flex items-center hover:underline"
              >
                <span>{{ t('admin.policySnapshot.unit.enter') }}</span>
                <ArrowUpRight class="w-3 h-3 ml-0.5" />
              </router-link>
            </div>

            <div class="space-y-1 text-xs">
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.evolution.version') }}</span>
                <span class="text-emerald-400 font-bold truncate max-w-[180px]" :title="snapshotData.snapshot.units?.evolution_mind?.version">
                  {{ snapshotData.snapshot.units?.evolution_mind?.version }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.evolution.counts') }}</span>
                <span class="font-bold" style="color: var(--ink-1);">
                  {{ snapshotData.snapshot.units?.evolution_mind?.enabled_count }} / {{ snapshotData.snapshot.units?.evolution_mind?.total_count }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.evolution.review') }}</span>
                <span class="text-emerald-400 font-bold">{{ t('admin.policySnapshot.unit.evolution.reviewValue') }}</span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.evolution.concurrency') }}</span>
                <span class="text-emerald-400 font-bold">{{ t('admin.policySnapshot.unit.evolution.concurrencyValue') }}</span>
              </div>
            </div>
          </div>

          <div class="p-2 rounded-xl text-[11px]" style="background-color: var(--surface-1); color: var(--ink-2);">
            {{ t('admin.policySnapshot.unit.evolution.note') }}
          </div>
        </div>

        <!-- Unit 3: Interceptor Plugins -->
        <div
          class="p-4 sm:p-5 rounded-2xl border space-y-3 flex flex-col justify-between"
          style="background-color: var(--surface-2); border-color: var(--line-1);"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--line-1);">
              <div class="flex items-center space-x-2">
                <span class="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
                  <ShieldCheck class="w-4 h-4" />
                </span>
                <span class="font-bold text-xs" style="color: var(--ink-1);">{{ t('admin.policySnapshot.unit.interceptor.title') }}</span>
              </div>
              <router-link
                to="/admin/interceptors"
                class="text-[11px] text-amber-400 flex items-center hover:underline"
              >
                <span>{{ t('admin.policySnapshot.unit.enter') }}</span>
                <ArrowUpRight class="w-3 h-3 ml-0.5" />
              </router-link>
            </div>

            <div class="space-y-1 text-xs">
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.interceptor.core') }}</span>
                <span class="text-amber-400 font-bold">{{ t('admin.policySnapshot.unit.interceptor.coreValue') }}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.interceptor.pluginsHash') }}</span>
                <span class="text-amber-400 font-bold">#{{ snapshotData.snapshot.units?.physical_interceptors?.plugins_hash }}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.interceptor.enabled') }}</span>
                <span class="font-bold" style="color: var(--ink-1);">
                  {{ t('admin.policySnapshot.unit.interceptor.enabledValue', undefined, { n: snapshotData.snapshot.units?.physical_interceptors?.enabled_count, t: snapshotData.snapshot.units?.physical_interceptors?.total_count }) }}
                </span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.interceptor.recheck') }}</span>
                <span class="text-emerald-400 font-bold">{{ t('admin.policySnapshot.unit.interceptor.recheckValue') }}</span>
              </div>
            </div>
          </div>

          <div class="p-2 rounded-xl text-[11px]" style="background-color: var(--surface-1); color: var(--ink-2);">
            {{ t('admin.policySnapshot.unit.interceptor.note') }}
          </div>
        </div>

        <!-- Unit 4: Trading Desk Council -->
        <div
          class="p-4 sm:p-5 rounded-2xl border space-y-3 flex flex-col justify-between"
          style="background-color: var(--surface-2); border-color: var(--line-1);"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--line-1);">
              <div class="flex items-center space-x-2">
                <span class="p-1.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
                  <Users class="w-4 h-4" />
                </span>
                <span class="font-bold text-xs" style="color: var(--ink-1);">{{ t('admin.policySnapshot.unit.council.title') }}</span>
              </div>
              <router-link
                to="/admin/council"
                class="text-[11px] text-purple-400 flex items-center hover:underline"
              >
                <span>{{ t('admin.policySnapshot.unit.enter') }}</span>
                <ArrowUpRight class="w-3 h-3 ml-0.5" />
              </router-link>
            </div>

            <div class="space-y-1 text-xs">
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.council.status') }}</span>
                <span
                  class="font-bold"
                  :style="snapshotData.snapshot.units?.model_council?.enabled ? { color: 'var(--up)' } : { color: 'var(--ink-3)' }"
                >
                  {{ snapshotData.snapshot.units?.model_council?.enabled ? t('admin.policySnapshot.unit.council.statusEnabled') : t('admin.policySnapshot.unit.council.statusDisabled') }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.council.consensus') }}</span>
                <span class="text-purple-400 font-bold">
                  {{ snapshotData.snapshot.units?.model_council?.consensus_mode === 'cross_examination' ? t('admin.policySnapshot.unit.council.consensusCross') : t('admin.policySnapshot.unit.council.consensusStandard') }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--line-1);">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.council.seats') }}</span>
                <span class="font-bold" style="color: var(--ink-1);">
                  {{ t('admin.policySnapshot.unit.council.seatsValue', undefined, { n: snapshotData.snapshot.units?.model_council?.active_roles?.length || 0 }) }}
                </span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-[var(--ink-2)]">{{ t('admin.policySnapshot.unit.council.adopted') }}</span>
                <span class="text-emerald-400 font-bold">{{ t('admin.policySnapshot.unit.council.adoptedValue') }}</span>
              </div>
            </div>
          </div>

          <div class="p-2 rounded-xl text-[11px]" style="background-color: var(--surface-1); color: var(--ink-2);">
            {{ t('admin.policySnapshot.unit.council.note') }}
          </div>
        </div>
      </div>

      <!-- 3. Policy Archive Vault (历史策略版本库) -->
      <div
        class="rounded-2xl border p-4 sm:p-5 shadow-xs space-y-3"
        style="background-color: var(--surface-2); border-color: var(--line-1);"
      >
        <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--line-1);">
          <div class="flex items-center space-x-2">
            <Archive class="w-4 h-4 text-purple-400" />
            <h3 class="text-sm font-bold" style="color: var(--ink-1);">
              {{ t('admin.policySnapshot.archive.title') }}
            </h3>
            <span class="text-[11px] px-2 py-0.5 rounded border" style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-2);">
              {{ t('admin.policySnapshot.archive.count', undefined, { n: archives.length }) }}
            </span>
          </div>
          <span class="text-[11px] text-[var(--ink-2)]">
            {{ t('admin.policySnapshot.archive.hint') }}
          </span>
        </div>

        <div v-if="archives.length === 0" class="py-8 text-center text-xs text-zinc-500">
          {{ t('admin.policySnapshot.archive.empty') }}
        </div>

        <div v-else class="divide-y" style="border-color: var(--line-1);">
          <div
            v-for="arc in archives"
            :key="arc.policy_hash"
            class="py-3 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs hover:bg-[var(--surface-3)] px-2 rounded-xl transition-colors"
          >
            <div class="space-y-1 flex-1 min-w-0">
              <div class="flex items-center space-x-2">
                <span class="font-bold text-sm" style="color: var(--ink-1);">{{ arc.name }}</span>
                <span class="text-[11px] px-2 py-0.5 rounded border text-cyan-400 border-cyan-500/30 bg-cyan-500/10">
                  #{{ arc.policy_hash }}
                </span>
                <span
                  v-if="arc.policy_hash === snapshotData.snapshot.policy_hash"
                  class="text-[11px] font-bold px-2 py-0.2 rounded border text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                >
                  {{ t('admin.policySnapshot.archive.running') }}
                </span>
              </div>
              <p v-if="arc.description" class="text-[11px]" style="color: var(--ink-2);">
                {{ arc.description }}
              </p>
              <div class="flex flex-wrap items-center gap-3 text-[11px] text-[var(--ink-2)]">
                <span>{{ t('admin.policySnapshot.archive.archivedAt') }}: {{ utcStrToBj(arc.archived_at, true) }}</span>
                <span>{{ t('admin.policySnapshot.archive.author') }}: {{ arc.author }}</span>
                <span class="truncate max-w-md">{{ arc.summary }}</span>
              </div>
            </div>

            <div class="flex items-center space-x-2 shrink-0">
              <button
                @click="restorePolicy(arc.policy_hash, arc.name)"
                :disabled="restoring || !auth.isSuperadmin || arc.policy_hash === snapshotData.snapshot.policy_hash"
                class="flex items-center space-x-1 px-3 py-1.5 rounded-xl border text-xs font-bold cursor-pointer disabled:opacity-40 transition-all shadow-xs"
                :style="arc.policy_hash === snapshotData.snapshot.policy_hash
                  ? { backgroundColor: 'var(--surface-1)', borderColor: 'var(--line-1)', color: 'var(--ink-3)' }
                  : { backgroundColor: 'var(--up-bg)', borderColor: 'var(--up-line)', color: 'var(--up)' }"
              >
                <RotateCcw class="w-3.5 h-3.5" :class="{ 'animate-spin': restoring }" />
                <span>{{ arc.policy_hash === snapshotData.snapshot.policy_hash ? t('admin.policySnapshot.archive.isCurrent') : t('admin.policySnapshot.archive.restore') }}</span>
              </button>

              <button
                @click="deleteArchive(arc.policy_hash, arc.name)"
                :disabled="deleting === arc.policy_hash || !auth.isSuperadmin"
                class="flex items-center space-x-1 px-2.5 py-1.5 rounded-xl border text-xs cursor-pointer transition-all hover:bg-rose-500/10 text-rose-400 border-rose-500/20"
                :title="t('admin.policySnapshot.archive.deleteTitle')"
              >
                <Trash2 class="w-3.5 h-3.5" :class="{ 'animate-pulse': deleting === arc.policy_hash }" />
                <span>{{ t('admin.policySnapshot.archive.delete') }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Archive Dialog Modal -->
    <div
      v-if="showArchiveModal"
      class="fixed inset-0 z-[var(--z-dialog)] flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
    >
      <div
        class="w-full max-w-md rounded-2xl border p-5 shadow-2xl space-y-4"
        style="background-color: var(--surface-2); border-color: var(--line-2);"
      >
        <div class="flex items-center space-x-2">
          <BookmarkPlus class="w-5 h-5 text-purple-400" />
          <h3 class="text-sm font-bold" style="color: var(--ink-1);">
            {{ t('admin.policySnapshot.modal.title') }}
          </h3>
        </div>

        <p class="text-xs leading-relaxed" style="color: var(--ink-2);">
          {{ t('admin.policySnapshot.modal.desc') }}
        </p>

        <div class="space-y-3 text-xs">
          <div>
            <label class="block text-[11px] mb-1 font-bold" style="color: var(--ink-2);">{{ t('admin.policySnapshot.modal.nameLabel') }}</label>
            <input
              v-model="archiveName"
              :placeholder="t('admin.policySnapshot.modal.namePlaceholder')"
              class="w-full rounded-xl px-3 py-2 text-xs outline-none border transition-colors"
              style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);"
            />
          </div>
          <div>
            <label class="block text-[11px] mb-1 font-bold" style="color: var(--ink-2);">{{ t('admin.policySnapshot.modal.descLabel') }}</label>
            <textarea
              v-model="archiveDesc"
              rows="3"
              :placeholder="t('admin.policySnapshot.modal.descPlaceholder')"
              class="w-full rounded-xl p-3 text-xs outline-none border transition-colors resize-none"
              style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);"
            ></textarea>
          </div>
        </div>

        <div class="flex items-center justify-end space-x-2 pt-2 border-t" style="border-color: var(--line-1);">
          <button
            @click="showArchiveModal = false"
            class="px-3.5 py-1.5 rounded-xl border text-xs cursor-pointer transition-colors"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-2);"
          >
            {{ t('admin.policySnapshot.modal.cancel') }}
          </button>
          <button
            @click="saveArchive"
            :disabled="archiving"
            class="px-4 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all shadow-xs"
            style="background-color: var(--accent); color: var(--accent-ink);"
          >
            {{ archiving ? t('admin.policySnapshot.modal.archiving') : t('admin.policySnapshot.modal.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
