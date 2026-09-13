<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from '../../composables/useI18n'
const { t } = useI18n()
import { useApi } from '../../composables/useApi'
import { useResource } from '../../composables/useResource'
import { useAsyncAction } from '../../composables/useAsyncAction'
import { Info, GitBranch, Download, RefreshCw, CheckCircle2, AlertTriangle, ShieldCheck, Terminal } from 'lucide-vue-next'

const { api } = useApi()

// F2：取数样板收成一行。原实现出错只 console.error（页面不显示），
// 这里保持同样的可见性（页面无错误位），错误仍可从 error 取。
const { data: about, loading } = useResource<any>('/api/v1/admin/about', {
  onError: (e) => console.error(e),
})

const updateResult = ref<any>(null)
const showConfirmModal = ref(false)
const confirmPhrase = ref('')

// F2：动作类样板（busy + 统一错误出口）。原实现的错误出口是写进 updateResult，
// 故用 onError 一对一保留，不弹 toast、不改变页面表现。
const { run: checkUpdate, busy: updateChecking } = useAsyncAction(async () => {
  updateResult.value = null
  const res = await api<any>('/api/v1/admin/update/check', { method: 'POST' })
  if (about.value) {
    about.value.update = res
  }
  updateResult.value = res.error
    // 模板以 .error 键判红（审计①#8）：git 失败回 HTTP 200+error 字段，必须走红分支
    ? { error: `更新检查失败：${res.error}（无法确认是否落后，安全补丁可能静默脱班）`, data: res }
    : {
        ok: true,
        message: res.behind > 0
          ? t('admin.about.checkBehind', undefined, { behind: res.behind, remote: res.remote })
          : t('admin.about.checkUpToDate'),
        data: res,
      }
}, { onError: (e) => { updateResult.value = { error: e.message } } })

function openUpdateModal() {
  confirmPhrase.value = ''
  showConfirmModal.value = true
}

const { run: executeUpdate, busy: updateRunning } = useAsyncAction(async () => {
  if (confirmPhrase.value.trim().toUpperCase() !== 'UPDATE R20') return
  updateResult.value = null
  const res = await api<any>('/api/v1/admin/update', {
    method: 'POST',
    body: JSON.stringify({ confirmation: 'UPDATE R20' }),
  })
  showConfirmModal.value = false
  updateResult.value = {
    ok: true,
    updated: res.updated,
    message: res.updated ? t('admin.about.updateSuccess') : t('admin.about.updateNoop'),
    git_output: res.git_output,
    restart_note: res.restart_note,
  }
  if (about.value && res.after) {
    about.value.update = res.after
  }
}, { onError: (e) => { updateResult.value = { error: e.message } } })
</script>

<template>
  <div class="space-y-4 text-xs">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[var(--ink-3)]">{{ t('admin.about.intro') }}</p>
      <span class="text-[11px] text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">{{ t('admin.about.badge') }}</span>
    </div>

    <div v-if="loading" class="py-12 text-center" style="color: var(--ink-2);">{{ t('admin.about.loading') }}</div>

    <template v-else-if="about">
      <!-- About Cards -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--line-1);">
            <div class="flex items-center space-x-2">
              <Info class="w-4 h-4" style="color: var(--accent);" />
              <h2 class="text-sm font-bold" style="color: var(--ink-1);">{{ t('nav.admin.about') }}</h2>
            </div>
            <span class="text-[11px] px-2 py-0.5 rounded border font-bold" style="background-color: var(--up-bg); color: var(--up); border-color: var(--up-line);">OPEN SOURCE</span>
          </div>
          <div class="space-y-1.5" style="color: var(--ink-2);">
            <div>{{ t('admin.about.productArchitecture') }} <strong style="color: var(--ink-1);">{{ about.product?.name }}</strong></div>
            <div>{{ t('admin.about.systemVersion') }} <strong style="color: var(--accent);">v{{ about.product?.version }}</strong></div>
            <div>{{ t('admin.about.controlPlane') }} <span style="color: var(--ink-1);">{{ about.product?.control_plane }} (v{{ about.product?.gateway_version }})</span></div>
            <div>{{ t('admin.about.runtime') }} <span style="color: var(--ink-1);">Python {{ about.runtime?.python }}</span></div>
          </div>
          <a href="https://github.com/555cute/r20-quantum-trader" target="_blank" class="inline-flex items-center space-x-1.5 mt-4 px-3 py-1.5 rounded-lg border text-xs font-bold transition-all cursor-pointer shadow-xs" style="background-color: var(--accent); color: var(--accent-ink);">
            <GitBranch class="w-3.5 h-3.5" />
            <span>{{ t('admin.about.repoLink') }}</span>
          </a>
        </div>

        <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--line-1);">
            <h2 class="text-sm font-bold" style="color: var(--ink-1);">{{ t('admin.about.componentsTitle') }}</h2>
            <span class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.about.componentsSub') }}</span>
          </div>
          <div class="table-scroll-container">
            <table class="w-full text-left whitespace-nowrap">
              <tbody>
                <tr v-for="c in about.components" :key="c.name" class="border-b last:border-b-0 hover:bg-[var(--surface-3)] transition-colors" style="border-color: var(--line-1);">
                  <td class="py-2" style="color: var(--ink-2);">{{ c.name }}</td>
                  <td class="py-2 font-bold num" style="color: var(--ink-1);">{{ c.version }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Update Section -->
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--line-1);">
          <div class="flex items-center space-x-2">
            <ShieldCheck class="w-4 h-4 text-emerald-500" />
            <h2 class="text-sm font-bold" style="color: var(--ink-1);">{{ t('admin.about.securityUpdate') }}</h2>
          </div>
          <span class="text-[11px] px-2 py-0.5 rounded border font-bold" style="background-color: var(--accent-bg); color: var(--accent); border-color: var(--accent-line);">FF-ONLY</span>
        </div>

        <!-- Git Status Telemetry Grid -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-4">
          <div class="p-2.5 rounded-lg border" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.about.currentBranch') }}</div>
            <div class="text-xs font-bold mt-0.5" style="color: var(--ink-1);">{{ about.update?.branch || 'main' }}</div>
          </div>
          <div class="p-2.5 rounded-lg border" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.about.localCommit') }}</div>
            <div class="text-xs font-bold mt-0.5 text-blue-400">{{ about.update?.local || '--' }}</div>
          </div>
          <div class="p-2.5 rounded-lg border" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.about.remoteCommit') }}</div>
            <div class="text-xs font-bold mt-0.5" style="color: var(--ink-1);">{{ about.update?.remote || t('admin.about.pending') }}</div>
          </div>
          <div class="p-2.5 rounded-lg border" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.about.syncGap') }}</div>
            <div class="text-xs font-bold mt-0.5" :class="(about.update?.behind || 0) > 0 ? 'text-amber-400' : 'text-emerald-400'">
              {{ (about.update?.behind || 0) > 0 ? t('admin.about.behind', undefined, { n: about.update?.behind }) : t('admin.about.upToDate') }}
              <span v-if="about.update?.ahead" class="text-[11px] text-gray-400 font-normal"> {{ t('admin.about.ahead', undefined, { n: about.update.ahead }) }}</span>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex flex-wrap items-center gap-2.5">
          <button
            @click="checkUpdate"
            :disabled="updateChecking || updateRunning"
            class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold transition-all cursor-pointer shadow-xs"
            style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);"
          >
            <RefreshCw class="w-3.5 h-3.5" :class="updateChecking ? 'animate-spin' : ''" />
            <span>{{ updateChecking ? t('admin.about.connecting') : t('admin.about.checkUpdate') }}</span>
          </button>

          <button
            @click="openUpdateModal"
            :disabled="updateChecking || updateRunning"
            class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold transition-all cursor-pointer shadow-xs text-white"
            style="background-color: var(--accent); border-color: var(--accent); color: var(--accent-ink);"
          >
            <Download class="w-3.5 h-3.5" />
            <span>{{ t('admin.about.runUpdate') }}</span>
          </button>
        </div>

        <!-- Result / Feedback Banner -->
        <div v-if="updateResult" class="mt-3.5 space-y-2">
          <div
            class="text-xs p-3 rounded-lg border flex items-start space-x-2"
            :style="updateResult.error
              ? { backgroundColor: 'var(--down-bg)', borderColor: 'var(--down-line)', color: 'var(--down)' }
              : { backgroundColor: 'var(--up-bg)', borderColor: 'var(--up-line)', color: 'var(--up)' }"
          >
            <AlertTriangle v-if="updateResult.error" class="w-4 h-4 shrink-0 mt-0.5" />
            <CheckCircle2 v-else class="w-4 h-4 shrink-0 mt-0.5" />
            <div class="flex-1 space-y-1">
              <div class="font-bold">{{ updateResult.error || updateResult.message }}</div>
              <div v-if="updateResult.restart_note" class="text-[11px] opacity-90">
                💡 {{ updateResult.restart_note }}
              </div>
            </div>
          </div>

          <div v-if="updateResult.git_output" class="p-3 rounded-lg border bg-black/40 text-[11px] text-gray-300 space-y-1">
            <div class="flex items-center space-x-1 text-gray-400 text-[11px]">
              <Terminal class="w-3 h-3" />
              <span>{{ t('admin.about.gitOutput') }}</span>
            </div>
            <pre class="whitespace-pre-wrap leading-relaxed">{{ updateResult.git_output }}</pre>
          </div>
        </div>

        <p class="mt-3 text-[11px] leading-relaxed" style="color: var(--ink-3);">
          {{ t('admin.about.safetyNote') }}
        </p>
      </div>
    </template>

    <!-- Confirmation Modal -->
    <div
      v-if="showConfirmModal"
      class="fixed inset-0 z-[var(--z-dialog)] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
    >
      <div
        class="w-full max-w-md rounded-2xl border p-5 shadow-2xl space-y-4"
        style="background-color: var(--surface-2); border-color: var(--line-2);"
      >
        <div class="flex items-center space-x-2 pb-3 border-b" style="border-color: var(--line-1);">
          <AlertTriangle class="w-5 h-5 text-amber-500 shrink-0" />
          <div>
            <h3 class="text-sm font-bold" style="color: var(--ink-1);">{{ t('admin.about.confirmTitle') }}</h3>
            <p class="text-[11px]" style="color: var(--ink-2);"> {{ t('admin.about.confirmSubtitle') }} </p>
          </div>
        </div>

        <div class="space-y-2 text-xs" style="color: var(--ink-2);">
          <p>
            {{ t('admin.about.confirmPrefix') }} <strong class="text-red-400 font-bold">UPDATE R20</strong>{{ t('admin.about.confirmSuffix') }}
          </p>
          <input
            v-model="confirmPhrase"
            :placeholder="t('admin.about.phrasePlaceholder')"
            class="w-full rounded-lg px-3 py-2 text-xs outline-none border uppercase"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
            @keyup.enter="executeUpdate"
          />
        </div>

        <div class="flex justify-end space-x-2 pt-2">
          <button
            @click="showConfirmModal = false"
            :disabled="updateRunning"
            class="px-3 py-1.5 rounded-lg border text-xs cursor-pointer"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-2);"
          >
            {{ t('admin.about.cancel') }}
          </button>
          <button
            @click="executeUpdate"
            :disabled="confirmPhrase.trim().toUpperCase() !== 'UPDATE R20' || updateRunning"
            class="flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-bold text-white transition-all cursor-pointer shadow-xs disabled:opacity-40 disabled:cursor-not-allowed"
            style="background-color: var(--accent); border-color: var(--accent); color: var(--accent-ink);"
          >
            <RefreshCw v-if="updateRunning" class="w-3.5 h-3.5 animate-spin" />
            <span>{{ updateRunning ? t('admin.about.updating') : t('admin.about.confirmNow') }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
