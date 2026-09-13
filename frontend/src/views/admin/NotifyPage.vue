<script setup lang="ts">
import { useToast } from '../../composables/useToast'
const toast = useToast()
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import PageHeader from '../../components/admin/PageHeader.vue'
import { useI18n } from '../../composables/useI18n'
const { t } = useI18n()
import { useApi } from '../../composables/useApi'
import {Zap} from 'lucide-vue-next'

const { api } = useApi()
const config = ref<any>(null)
const loading = ref(true)
const testResults = ref<Record<string, any>>({})
const captureModal = ref(false)
const captureStatus = ref<any>(null)
let captureTimer: any = null

const enabledChannelsCount = computed(() => {
  if (!config.value) return 0
  return ['qq', 'telegram', 'wechat', 'webhook'].filter(k => config.value[k]?.enabled).length
})

async function loadConfig(silent = false) {
  if (!silent) loading.value = true
  try {
    const res = await api('/api/v1/admin/notifications')
    // Preserve local un-submitted secret inputs if any
    if (config.value) {
      if (config.value.qq?._secret) res.qq._secret = config.value.qq._secret
      if (config.value.telegram?._token) res.telegram._token = config.value.telegram._token
    }
    const schedule = await api('/api/v1/admin/notifications/schedule')
    res._briefingTimes = schedule.briefing_times?.join(', ') || ''
    config.value = res
  } catch (e: any) {
    console.error(e)
    toast.err('加载通知配置失败: ' + (e.message || String(e)))
  } finally {
    if (!silent) loading.value = false
  }
}

async function toggleChannel(channel: string, enabled: boolean) {
  try {
    const payload: any = { enabled }
    if (config.value) {
      if (channel === 'wechat' && config.value.wechat?.webhook) payload.wechat_webhook = config.value.wechat.webhook
      if (channel === 'webhook' && config.value.webhook?.url) payload.webhook_url = config.value.webhook.url
      if (channel === 'telegram') {
        if (config.value.telegram?._token) payload.telegram_bot_token = config.value.telegram._token
        if (config.value.telegram?.chat_id) payload.telegram_chat_id = config.value.telegram.chat_id
        if (config.value.telegram?.api_base) payload.telegram_api_base = config.value.telegram.api_base
      }
      if (channel === 'qq') {
        if (config.value.qq?.app_id) payload.qq_app_id = config.value.qq.app_id
        if (config.value.qq?._secret) payload.qq_client_secret = config.value.qq._secret
        if (config.value.qq?.openid) payload.qq_openid = config.value.qq.openid
      }
      // Optimistically flip visual state immediately
      if (config.value[channel]) {
        config.value[channel].enabled = enabled
      }
    }
    const res = await api(`/api/v1/admin/channels/${channel}/toggle`, { method: 'PUT', body: JSON.stringify(payload) })
    toast.ok(res.message || `${channel} 通道已成功${enabled ? '开启' : '关闭'}`)
    await loadConfig(true)
  } catch (e: any) {
    toast.err(e.message || '通道状态切换失败')
    await loadConfig(true)
  }
}

async function saveAll() {
  try {
    const body: any = {
      webhook_enabled: config.value.webhook.enabled,
      webhook_url: config.value.webhook.url,
      wechat_enabled: config.value.wechat.enabled,
      wechat_webhook: config.value.wechat.webhook,
      telegram_enabled: config.value.telegram.enabled,
      telegram_bot_token: config.value.telegram._token || undefined,
      telegram_chat_id: config.value.telegram.chat_id,
      telegram_api_base: config.value.telegram.api_base || undefined,
      qq_enabled: config.value.qq.enabled,
      qq_app_id: config.value.qq.app_id,
      qq_client_secret: config.value.qq._secret || undefined,
      qq_openid: config.value.qq.openid,
    }
    const res = await api('/api/v1/admin/notifications', { method: 'PUT', body: JSON.stringify(body) })
    toast.ok(res.message || '全部通知通道配置已保存')
    await loadConfig(true)
  } catch (e: any) {
    toast.err(e.message || '保存配置失败')
  }
}

async function diagnose(channel: string) {
  try {
    const res = await api('/api/v1/admin/notifications/diagnose', { method: 'POST', body: JSON.stringify({ channel }) })
    testResults.value[channel] = res.result
  } catch (e: any) {
    testResults.value[channel] = { status: 'failed', detail: e.message }
  }
}

async function startCapture() {
  try {
    const res = await api('/api/v1/admin/notifications/qq/capture-openid/start', { method: 'POST', body: JSON.stringify({ timeout: 60 }) })
    captureModal.value = true
    captureStatus.value = res
    pollCapture(res.capture_id)
  } catch (e: any) {
    toast.err(e.message)
  }
}

function pollCapture(captureId: string) {
  if (captureTimer) clearInterval(captureTimer)
  captureTimer = setInterval(async () => {
    try {
      const res = await api(`/api/v1/admin/notifications/qq/capture-openid/${captureId}`)
      captureStatus.value = res
      if (res.status === 'captured' || res.status === 'expired' || res.status === 'failed') {
        clearInterval(captureTimer)
        captureTimer = null
        if (res.status === 'captured') {
          await loadConfig()
          setTimeout(() => { captureModal.value = false }, 1800)
        }
      }
    } catch (e: any) {
      clearInterval(captureTimer)
      captureTimer = null
    }
  }, 1500)
}

// ---- QQ scan bind ----
const bindModal = ref(false)
const bindStatus = ref<any>(null)
let bindTimer: any = null
let bindTaskId = ''

function stopBindPolling() {
  if (bindTimer) { clearInterval(bindTimer); bindTimer = null }
}

async function startQqBind() {
  try {
    const d = await api('/api/v1/admin/notifications/qq/bind/start', { method: 'POST', body: '{}' })
    bindTaskId = d.task_id
    bindStatus.value = { qr: d.qr_data_uri || '', link: d.qr_data_uri ? '' : (d.connect_url || ''), text: t('admin.notify.waitScan', undefined, { n: d.expires_in }), tone: 'blue' }
    bindModal.value = true
    stopBindPolling()
    bindTimer = setInterval(async () => {
      if (!bindTaskId) return
      try {
        const r = await api(`/api/v1/admin/notifications/qq/bind/${bindTaskId}`)
        if (r.status === 'bound') {
          bindStatus.value = { ...bindStatus.value, text: t('admin.notify.bindSuccess'), tone: 'green' }
          stopBindPolling()
          await loadConfig()
          setTimeout(() => { bindModal.value = false }, 1800)
        } else if (r.status === 'awaiting_message') {
          stopBindPolling()
          bindModal.value = false
          toast.ok('QQ 机器人授权成功，正在自动启动 OpenID 捕获…')
          startCapture()
        } else if (r.status === 'expired') {
          bindStatus.value = { ...bindStatus.value, text: t('admin.notify.qrExpired'), tone: 'amber' }
          stopBindPolling()
        } else if (r.status === 'failed') {
          bindStatus.value = { ...bindStatus.value, text: t('admin.notify.bindFailed', undefined, { error: r.error || t('admin.notify.unknownError') }), tone: 'red' }
          stopBindPolling()
        } else {
          bindStatus.value = { ...bindStatus.value, text: t('admin.notify.waitScan', undefined, { n: r.expires_in ?? '--' }), tone: 'blue' }
        }
      } catch (e: any) {
        bindStatus.value = { ...bindStatus.value, text: e.message, tone: 'red' }
        stopBindPolling()
      }
    }, 2000)
  } catch (e: any) {
    toast.err(e.message)
  }
}

function closeBindModal() {
  stopBindPolling()
  bindModal.value = false
}

// ---- protected test send ----
async function sendTest(channel: string) {
  try {
    testResults.value[channel] = { status: 'testing', detail: t('admin.notify.requestingTest') }
    const res = await api('/api/v1/admin/notifications/test', {
      method: 'POST',
      body: JSON.stringify({ channel, confirmation: `SEND TEST ${channel.toUpperCase()}` }),
    })
    testResults.value[channel] = { status: res.result?.[channel]?.startsWith('accepted:') ? 'ready' : (res.result?.status || 'sent'), detail: `${res.result?.[channel] || res.result?.detail || t('admin.notify.sent')} · ${res.meaning || ''}` }
  } catch (e: any) {
    testResults.value[channel] = { status: 'failed', detail: e.message }
  }
}

async function saveSchedule() {
  const times = String(config.value._briefingTimes || '').split(/[,，\s]+/).filter(Boolean)
  if (!times.length) { toast.warn('请至少填写一个 HH:MM 时间'); return }
  try {
    await api('/api/v1/admin/notifications/schedule', { method: 'PUT', body: JSON.stringify({ briefing_times: times }) })
    toast.ok('简报时间已保存')
  } catch (e: any) {
    toast.err(e.message)
  }
}

onMounted(() => {
  loadConfig()
})

// 批B(2026-09-13)·离场清理：旧实现仅在「终态/异常」清定时器，离开本页后 QQ
// OpenID 捕获/扫码绑定仍每 1.5s 打一次管理接口（最长持续到服务端过期，失败还被
// 静默吞）。组件卸载即停全部轮询。
onBeforeUnmount(() => {
  if (captureTimer) { clearInterval(captureTimer); captureTimer = null }
  stopBindPolling()
})
</script>

<template>
  <div class="space-y-4 max-w-[2048px] mx-auto">
    <PageHeader :title="t('nav.admin.notify')" :description="t('admin.notify.desc')">
      <template #actions>
        <span class="chip">{{ t('admin.notify.channelsChip') }} <b class="num">{{ enabledChannelsCount }}/4</b></span>
      </template>
    </PageHeader>

    <!-- Alert / Banner Message -->
    <div v-if="loading" class="py-12 text-center text-xs" style="color: var(--ink-2);">{{ t('admin.notify.loading') }}</div>

    <template v-else-if="config">
      <!-- QQ Channel -->
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center space-x-2">
            <span class="inline-block w-2 h-2 rounded-full" :class="config.qq.enabled ? 'bg-emerald-500' : 'bg-zinc-500'"></span>
            <h2 class="text-sm font-bold" style="color: var(--ink-1);">{{ t('nav.admin.notify') }}</h2>
          </div>
          <div class="flex items-center space-x-3">
            <button @click="startQqBind" class="px-2.5 py-1 rounded-lg text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--accent); color: var(--accent-ink);">{{ t('admin.notify.scanBind') }}</button>
            <button @click="startCapture" class="flex items-center space-x-1 px-2.5 py-1 rounded-lg border text-xs cursor-pointer transition-all shadow-xs" style="background-color: var(--accent-bg); border-color: var(--accent-line); color: var(--accent);">
              <Zap class="w-3 h-3" />
              <span>{{ t('admin.notify.autoOpenId') }}</span>
            </button>
            <div class="flex items-center space-x-2">
              <button
                type="button"
                @click="toggleChannel('qq', !config.qq.enabled)"
                class="relative inline-flex items-center cursor-pointer focus:outline-none"
                :title="config.qq.enabled ? t('admin.notify.qqOff') : t('admin.notify.qqOn')"
              >
                <div
                  class="w-10 h-5 rounded-full transition-colors relative"
                  :style="{ backgroundColor: config.qq.enabled ? 'var(--up)' : 'var(--line-2)' }"
                >
                  <div
                    class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-xs"
                    :class="config.qq.enabled ? 'translate-x-5' : 'translate-x-0'"
                  ></div>
                </div>
              </button>
              <span
                class="text-xs font-bold select-none cursor-pointer"
                @click="toggleChannel('qq', !config.qq.enabled)"
                :style="{ color: config.qq.enabled ? 'var(--up)' : 'var(--ink-2)' }"
              >
                {{ config.qq.enabled ? t('admin.notify.enabled') : t('admin.notify.disabled') }}
              </span>
            </div>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div><label class="block text-[11px] mb-1" style="color: var(--ink-2);">App ID</label><input v-model="config.qq.app_id" class="w-full rounded-lg px-3 py-2 text-xs outline-none border" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" /></div>
          <div><label class="block text-[11px] mb-1" style="color: var(--ink-2);">Client Secret</label><input v-model="config.qq._secret" type="password" :placeholder="t('admin.notify.keepExisting')" class="w-full rounded-lg px-3 py-2 text-xs outline-none border" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" /></div>
          <div class="sm:col-span-2"><label class="block text-[11px] mb-1" style="color: var(--ink-2);">{{ t('admin.notify.targetOpenId') }}</label><input v-model="config.qq.openid" class="w-full rounded-lg px-3 py-2 text-xs outline-none border" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" /></div>
        </div>
        <div class="flex space-x-2 mt-3">
          <button @click="diagnose('qq')" class="px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">{{ t('admin.notify.diagnose') }}</button>
          <button @click="sendTest('qq')" class="px-3 py-1.5 rounded-lg border text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--up-bg); border-color: var(--up-line); color: var(--up);">{{ t('admin.notify.sendTest') }}</button>
        </div>
        <div v-if="testResults.qq" class="mt-2 text-xs" :class="testResults.qq.status === 'ready' ? 'text-emerald-500' : 'text-amber-500'">{{ testResults.qq.status }} · {{ testResults.qq.detail }}</div>
      </div>

      <!-- Telegram -->
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center space-x-2">
            <span class="inline-block w-2 h-2 rounded-full" :class="config.telegram.enabled ? 'bg-emerald-500' : 'bg-zinc-500'"></span>
            <h2 class="text-sm font-bold" style="color: var(--ink-1);">Telegram Bot</h2>
          </div>
          <div class="flex items-center space-x-2">
            <button
              type="button"
              @click="toggleChannel('telegram', !config.telegram.enabled)"
              class="relative inline-flex items-center cursor-pointer focus:outline-none"
              :title="config.telegram.enabled ? t('admin.notify.telegramOff') : t('admin.notify.telegramOn')"
            >
              <div
                class="w-10 h-5 rounded-full transition-colors relative"
                :style="{ backgroundColor: config.telegram.enabled ? 'var(--up)' : 'var(--line-2)' }"
              >
                <div
                  class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-xs"
                  :class="config.telegram.enabled ? 'translate-x-5' : 'translate-x-0'"
                ></div>
              </div>
            </button>
            <span
              class="text-xs font-bold select-none cursor-pointer"
              @click="toggleChannel('telegram', !config.telegram.enabled)"
              :style="{ color: config.telegram.enabled ? 'var(--up)' : 'var(--ink-2)' }"
            >
              {{ config.telegram.enabled ? t('admin.notify.enabled') : t('admin.notify.disabled') }}
            </span>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div><label class="block text-[11px] mb-1" style="color: var(--ink-2);">Bot Token</label><input v-model="config.telegram._token" type="password" :placeholder="t('admin.notify.keepExisting')" class="w-full rounded-lg px-3 py-2 text-xs outline-none border" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" /></div>
          <div><label class="block text-[11px] mb-1" style="color: var(--ink-2);">Chat ID</label><input v-model="config.telegram.chat_id" class="w-full rounded-lg px-3 py-2 text-xs outline-none border" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" /></div>
          <div class="sm:col-span-2"><label class="block text-[11px] mb-1" style="color: var(--ink-2);">{{ t('admin.notify.apiBaseLabel') }}</label><input v-model="config.telegram.api_base" placeholder="https://api.telegram.org" class="w-full rounded-lg px-3 py-2 text-xs outline-none border" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" /></div>
        </div>
        <div class="flex space-x-2 mt-3">
          <button @click="diagnose('telegram')" class="px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">{{ t('admin.notify.diagnose') }}</button>
          <button @click="sendTest('telegram')" class="px-3 py-1.5 rounded-lg border text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--up-bg); border-color: var(--up-line); color: var(--up);">{{ t('admin.notify.sendTest') }}</button>
        </div>
        <div v-if="testResults.telegram" class="mt-2 text-xs" :class="testResults.telegram.status === 'ready' ? 'text-emerald-500' : 'text-amber-500'">{{ testResults.telegram.status }} · {{ testResults.telegram.detail }}</div>
      </div>

      <!-- WeChat + Webhook -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-2"><span class="inline-block w-2 h-2 rounded-full" :class="config.wechat.enabled ? 'bg-emerald-500' : 'bg-zinc-500'"></span><h2 class="text-sm font-bold" style="color: var(--ink-1);">{{ t('admin.notify.wechatTitle') }}</h2></div>
            <div class="flex items-center space-x-2">
              <button
                type="button"
                @click="toggleChannel('wechat', !config.wechat.enabled)"
                class="relative inline-flex items-center cursor-pointer focus:outline-none"
                :title="config.wechat.enabled ? t('admin.notify.wechatOff') : t('admin.notify.wechatOn')"
              >
                <div
                  class="w-10 h-5 rounded-full transition-colors relative"
                  :style="{ backgroundColor: config.wechat.enabled ? 'var(--up)' : 'var(--line-2)' }"
                >
                  <div
                    class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-xs"
                    :class="config.wechat.enabled ? 'translate-x-5' : 'translate-x-0'"
                  ></div>
                </div>
              </button>
              <span
                class="text-xs font-bold select-none cursor-pointer"
                @click="toggleChannel('wechat', !config.wechat.enabled)"
                :style="{ color: config.wechat.enabled ? 'var(--up)' : 'var(--ink-2)' }"
              >
                {{ config.wechat.enabled ? t('admin.notify.enabled') : t('admin.notify.disabled') }}
              </span>
            </div>
          </div>
          <label class="block text-[11px] mb-1" style="color: var(--ink-2);">Webhook URL</label>
          <input v-model="config.wechat.webhook" class="w-full rounded-lg px-3 py-2 text-xs outline-none border mb-3" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" />
          <button @click="diagnose('wechat')" class="px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">{{ t('admin.notify.diagnose') }}</button>
          <button @click="sendTest('wechat')" class="ml-2 px-3 py-1.5 rounded-lg border text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--up-bg); border-color: var(--up-line); color: var(--up);">{{ t('admin.notify.sendTest') }}</button>
          <div v-if="testResults.wechat" class="mt-2 text-xs" :class="testResults.wechat.status === 'ready' ? 'text-emerald-500' : 'text-amber-500'">{{ testResults.wechat.status }} · {{ testResults.wechat.detail }}</div>
        </div>
        <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-2"><span class="inline-block w-2 h-2 rounded-full" :class="config.webhook.enabled ? 'bg-emerald-500' : 'bg-zinc-500'"></span><h2 class="text-sm font-bold" style="color: var(--ink-1);">{{ t('admin.notify.webhookTitle') }}</h2></div>
            <div class="flex items-center space-x-2">
              <button
                type="button"
                @click="toggleChannel('webhook', !config.webhook.enabled)"
                class="relative inline-flex items-center cursor-pointer focus:outline-none"
                :title="config.webhook.enabled ? t('admin.notify.webhookOff') : t('admin.notify.webhookOn')"
              >
                <div
                  class="w-10 h-5 rounded-full transition-colors relative"
                  :style="{ backgroundColor: config.webhook.enabled ? 'var(--up)' : 'var(--line-2)' }"
                >
                  <div
                    class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-xs"
                    :class="config.webhook.enabled ? 'translate-x-5' : 'translate-x-0'"
                  ></div>
                </div>
              </button>
              <span
                class="text-xs font-bold select-none cursor-pointer"
                @click="toggleChannel('webhook', !config.webhook.enabled)"
                :style="{ color: config.webhook.enabled ? 'var(--up)' : 'var(--ink-2)' }"
              >
                {{ config.webhook.enabled ? t('admin.notify.enabled') : t('admin.notify.disabled') }}
              </span>
            </div>
          </div>
          <label class="block text-[11px] mb-1" style="color: var(--ink-2);">{{ t('admin.notify.webhookUrlLabel') }}</label>
          <input v-model="config.webhook.url" class="w-full rounded-lg px-3 py-2 text-xs outline-none border mb-3" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" />
          <button @click="diagnose('webhook')" class="px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">{{ t('admin.notify.diagnose') }}</button>
          <button @click="sendTest('webhook')" class="ml-2 px-3 py-1.5 rounded-lg border text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--up-bg); border-color: var(--up-line); color: var(--up);">{{ t('admin.notify.sendTest') }}</button>
          <div v-if="testResults.webhook" class="mt-2 text-xs" :class="testResults.webhook.status === 'ready' ? 'text-emerald-500' : 'text-amber-500'">{{ testResults.webhook.status }} · {{ testResults.webhook.detail }}</div>
        </div>
      </div>

      <!-- Schedule + Notification Categories + Save -->
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors space-y-4" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div>
          <h2 class="text-sm font-bold mb-1" style="color: var(--ink-1);">{{ t('admin.notify.categoriesTitle') }}</h2>
          <p class="text-xs" style="color: var(--ink-2);">{{ t('admin.notify.categoriesDesc') }}</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 text-xs">
          <div class="p-3 rounded-lg border space-y-1" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="flex items-center space-x-1.5 font-bold text-emerald-400">
              <span>{{ t('admin.notify.catOpen') }} <code class="mono text-[10px] opacity-60">trade.opened</code></span>
            </div>
            <p class="text-[11px] leading-relaxed" style="color: var(--ink-2);">
              {{ t('admin.notify.catOpenDesc') }}
            </p>
          </div>

          <div class="p-3 rounded-lg border space-y-1" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="flex items-center space-x-1.5 font-bold text-blue-400">
              <span>{{ t('admin.notify.catClosed') }} <code class="mono text-[10px] opacity-60">trade.closed</code></span>
            </div>
            <p class="text-[11px] leading-relaxed" style="color: var(--ink-2);">
              {{ t('admin.notify.catClosedDesc') }}
            </p>
          </div>

          <div class="p-3 rounded-lg border space-y-1" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="flex items-center space-x-1.5 font-bold text-indigo-400">
              <span>{{ t('admin.notify.catBreakEven') }} <code class="mono text-[10px] opacity-60">trade.sl_updated</code></span>
            </div>
            <p class="text-[11px] leading-relaxed" style="color: var(--ink-2);">
              {{ t('admin.notify.catBreakEvenDesc') }}
            </p>
          </div>

          <div class="p-3 rounded-lg border space-y-1" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="flex items-center space-x-1.5 font-bold text-purple-400">
              <span>{{ t('admin.notify.catEvolution') }} <code class="mono text-[10px] opacity-60">evolution.completed</code></span>
            </div>
            <p class="text-[11px] leading-relaxed" style="color: var(--ink-2);">
              {{ t('admin.notify.catEvolutionDesc') }}
            </p>
          </div>

          <div class="p-3 rounded-lg border space-y-1" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="flex items-center space-x-1.5 font-bold text-red-400">
              <span>{{ t('admin.notify.catRisk') }} <code class="mono text-[10px] opacity-60">risk.triggered</code></span>
            </div>
            <p class="text-[11px] leading-relaxed" style="color: var(--ink-2);">
              {{ t('admin.notify.catRiskDesc') }}
            </p>
          </div>

          <div class="p-3 rounded-lg border space-y-1" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="flex items-center space-x-1.5 font-bold text-amber-400">
              <span>{{ t('admin.notify.catBriefing') }} <code class="mono text-[10px] opacity-60">briefing.ready</code></span>
            </div>
            <p class="text-[11px] leading-relaxed" style="color: var(--ink-2);">
              {{ t('admin.notify.catBriefingDesc') }}
            </p>
          </div>
        </div>

        <div class="pt-2 border-t" style="border-color: var(--line-1);">
          <label class="block text-[11px] mb-1 font-bold" style="color: var(--ink-2);">{{ t('admin.notify.scheduleLabel') }}</label>
          <input v-model="config._briefingTimes" placeholder="08:00, 20:00" class="w-full rounded-lg px-3 py-2 text-xs outline-none border mb-4" style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);" />
          <div class="flex items-center space-x-3">
            <button @click="saveAll" class="px-4 py-2 rounded-lg text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--accent); color: var(--accent-ink);">{{ t('admin.notify.saveAll') }}</button>
            <button @click="saveSchedule" class="px-4 py-2 rounded-lg border text-xs cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">{{ t('admin.notify.saveSchedule') }}</button>
          </div>
        </div>
      </div>
    </template>

    <!-- Capture Modal -->
    <div v-if="captureModal" class="fixed inset-0 z-[var(--z-dialog)] bg-black/60 backdrop-blur-xs flex items-center justify-center p-4" @click.self="captureModal = false">
      <div class="rounded-xl border p-6 w-full max-w-[520px] max-h-[88dvh] overflow-y-auto text-center shadow-2xl transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <h3 class="text-sm font-bold mb-3" style="color: var(--ink-1);">{{ t('admin.notify.captureTitle') }}</h3>
        <div class="text-4xl mb-3">📱 💬 🤖</div>
        <p class="text-sm font-bold mb-2" style="color: var(--ink-1);">{{ captureStatus?.bot_name || t('admin.notify.connecting') }}</p>
        <p class="text-xs mb-4 leading-relaxed" style="color: var(--ink-2);">{{ t('admin.notify.captureGuide') }}</p>
        <div class="border rounded-lg p-3 mb-4" style="background-color: var(--surface-1); border-color: var(--line-1);">
          <div class="font-bold text-sm" :class="captureStatus?.status === 'captured' ? 'text-emerald-500' : 'text-blue-500'">
            {{ captureStatus?.status === 'captured' ? t('admin.notify.captured') : t('admin.notify.listening') }}
          </div>
          <div v-if="captureStatus?.expires_in" class="text-[11px] mt-1" style="color: var(--ink-3);">{{ t('admin.notify.remainingSeconds', undefined, { n: captureStatus.expires_in }) }}</div>
          <div v-if="captureStatus?.openid" class="text-xs mt-2" style="color: var(--accent);">OpenID: {{ captureStatus.openid }}</div>
        </div>
        <button @click="captureModal = false" class="px-4 py-2 rounded-lg border text-xs cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">{{ t('admin.notify.close') }}</button>
      </div>
    </div>

    <!-- QQ Bind QR Modal -->
    <div v-if="bindModal" class="fixed inset-0 z-[var(--z-dialog)] bg-black/60 backdrop-blur-xs flex items-center justify-center p-4" @click.self="closeBindModal">
      <div class="rounded-xl border p-5 sm:p-6 w-full max-w-[380px] max-h-[88dvh] overflow-y-auto text-center shadow-2xl transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <h3 class="text-sm font-bold mb-2" style="color: var(--ink-1);">{{ t('admin.notify.bindTitle') }}</h3>
        <p class="text-[11px] mb-3" style="color: var(--ink-2);">{{ t('admin.notify.bindGuide') }}</p>
        <img v-if="bindStatus?.qr" :src="bindStatus.qr" :alt="t('admin.notify.qrAlt')" class="w-[220px] h-[220px] rounded-lg bg-white p-2.5 mx-auto mb-3 shadow-xs border" style="border-color: var(--line-1);" />
        <p v-if="bindStatus?.link" class="text-[11px] break-all mb-3" style="color: var(--accent);">{{ bindStatus.link }}</p>
        <p class="text-xs mb-4" :class="{ 'text-blue-500': bindStatus?.tone === 'blue', 'text-emerald-500': bindStatus?.tone === 'green', 'text-amber-500': bindStatus?.tone === 'amber', 'text-rose-500': bindStatus?.tone === 'red' }">{{ bindStatus?.text }}</p>
        <div class="flex justify-center space-x-2">
          <button @click="startQqBind" class="px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">{{ t('admin.notify.refreshQr') }}</button>
          <button @click="closeBindModal" class="px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--accent); color: var(--accent-ink);">{{ t('admin.notify.close') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
