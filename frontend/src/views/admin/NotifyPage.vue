<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { MessageCircle, Zap, CheckCircle2, AlertCircle } from 'lucide-vue-next'

const { api } = useApi()
const config = ref<any>(null)
const loading = ref(true)
const testResults = ref<Record<string, any>>({})
const captureModal = ref(false)
const captureStatus = ref<any>(null)
let captureTimer: any = null

async function loadConfig() {
  loading.value = true
  try {
    config.value = await api('/api/v1/admin/notifications')
    const schedule = await api('/api/v1/admin/notifications/schedule')
    config.value._briefingTimes = schedule.briefing_times?.join(', ') || ''
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function toggleChannel(channel: string, enabled: boolean) {
  try {
    await api(`/api/v1/admin/channels/${channel}/toggle`, { method: 'PUT', body: JSON.stringify({ enabled }) })
    await loadConfig()
  } catch (e: any) {
    await loadConfig()
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
    alert(res.message || '保存成功')
    await loadConfig()
  } catch (e: any) {
    alert(e.message)
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
    alert(e.message)
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
    bindStatus.value = { qr: d.qr_data_uri || '', link: d.qr_data_uri ? '' : (d.connect_url || ''), text: `等待扫码…（${d.expires_in} 秒内有效）`, tone: 'blue' }
    bindModal.value = true
    stopBindPolling()
    bindTimer = setInterval(async () => {
      if (!bindTaskId) return
      try {
        const r = await api(`/api/v1/admin/notifications/qq/bind/${bindTaskId}`)
        if (r.status === 'bound') {
          bindStatus.value = { ...bindStatus.value, text: '绑定成功，凭证已写入本机加密库', tone: 'green' }
          stopBindPolling()
          await loadConfig()
          setTimeout(() => { bindModal.value = false }, 1800)
        } else if (r.status === 'awaiting_message') {
          stopBindPolling()
          bindModal.value = false
          alert('QQ 机器人授权成功，正在自动启动 OpenID 捕获…')
          startCapture()
        } else if (r.status === 'expired') {
          bindStatus.value = { ...bindStatus.value, text: '二维码已过期，请点击刷新', tone: 'amber' }
          stopBindPolling()
        } else if (r.status === 'failed') {
          bindStatus.value = { ...bindStatus.value, text: `绑定失败：${r.error || '未知错误'}`, tone: 'red' }
          stopBindPolling()
        } else {
          bindStatus.value = { ...bindStatus.value, text: `等待扫码…（${r.expires_in ?? '--'} 秒内有效）`, tone: 'blue' }
        }
      } catch (e: any) {
        bindStatus.value = { ...bindStatus.value, text: e.message, tone: 'red' }
        stopBindPolling()
      }
    }, 2000)
  } catch (e: any) {
    alert(e.message)
  }
}

function closeBindModal() {
  stopBindPolling()
  bindModal.value = false
}

// ---- protected test send ----
async function sendTest(channel: string) {
  const phrase = `SEND TEST ${channel.toUpperCase()}`
  const input = prompt(`发送真实测试通知到 ${channel} 通道\n输入确认短语：${phrase}`)
  if (!input) return
  try {
    const res = await api('/api/v1/admin/notifications/test', {
      method: 'POST',
      body: JSON.stringify({ channel, confirmation: input.trim().toUpperCase() }),
    })
    testResults.value[channel] = { status: res.result?.status || 'sent', detail: `${res.result?.detail || '已发送'} · ${res.meaning || ''}` }
  } catch (e: any) {
    testResults.value[channel] = { status: 'failed', detail: e.message }
  }
}

async function saveSchedule() {
  const times = String(config.value._briefingTimes || '').split(/[,，\s]+/).filter(Boolean)
  if (!times.length) { alert('请至少填写一个 HH:MM 时间'); return }
  try {
    await api('/api/v1/admin/notifications/schedule', { method: 'PUT', body: JSON.stringify({ briefing_times: times }) })
    alert('简报时间已保存')
  } catch (e: any) {
    alert(e.message)
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">逐通道配置、仅诊断、发送测试；最后统一保存投递时间。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">集成保障 · 1/3</span>
    </div>

    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]">正在加载通知配置...</div>

    <template v-else-if="config">
      <!-- QQ Channel -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center space-x-2">
            <span class="inline-block w-2 h-2 rounded-full" :class="config.qq.enabled ? 'bg-emerald-400' : 'bg-zinc-600'"></span>
            <h2 class="text-sm font-bold text-white font-mono">QQ 官方应用 Bot</h2>
          </div>
          <div class="flex items-center space-x-3">
            <button @click="startQqBind" class="px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold cursor-pointer">扫码绑定</button>
            <button @click="startCapture" class="flex items-center space-x-1 px-2.5 py-1 rounded-lg border border-blue-500/30 text-blue-400 bg-blue-500/10 text-xs font-mono cursor-pointer hover:bg-blue-500/20">
              <Zap class="w-3 h-3" />
              <span>⚡ 自动获取 OpenID</span>
            </button>
            <label class="flex items-center cursor-pointer">
              <input type="checkbox" :checked="config.qq.enabled" @change="toggleChannel('qq', ($event.target as HTMLInputElement).checked)" class="sr-only peer" />
              <div class="w-9 h-5 bg-zinc-600 rounded-full peer-checked:bg-emerald-500 transition-colors relative">
                <div class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4"></div>
              </div>
            </label>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="block text-[11px] text-[#8997aa] mb-1 font-mono">App ID</label><input v-model="config.qq.app_id" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" /></div>
          <div><label class="block text-[11px] text-[#8997aa] mb-1 font-mono">Client Secret</label><input v-model="config.qq._secret" type="password" placeholder="留空保持现有" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" /></div>
          <div class="col-span-2"><label class="block text-[11px] text-[#8997aa] mb-1 font-mono">目标用户 OpenID</label><input v-model="config.qq.openid" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" /></div>
        </div>
        <div class="flex space-x-2 mt-3">
          <button @click="diagnose('qq')" class="px-3 py-1.5 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">仅诊断</button>
          <button @click="sendTest('qq')" class="px-3 py-1.5 rounded-lg bg-[#111c2a] border border-emerald-500/30 text-xs font-mono text-emerald-400 cursor-pointer hover:bg-emerald-600/20">发送测试</button>
        </div>
        <div v-if="testResults.qq" class="mt-2 text-xs font-mono" :class="testResults.qq.status === 'ready' ? 'text-emerald-400' : 'text-amber-400'">{{ testResults.qq.status }} · {{ testResults.qq.detail }}</div>
      </div>

      <!-- Telegram -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center space-x-2">
            <span class="inline-block w-2 h-2 rounded-full" :class="config.telegram.enabled ? 'bg-emerald-400' : 'bg-zinc-600'"></span>
            <h2 class="text-sm font-bold text-white font-mono">Telegram Bot</h2>
          </div>
          <label class="flex items-center cursor-pointer">
            <input type="checkbox" :checked="config.telegram.enabled" @change="toggleChannel('telegram', ($event.target as HTMLInputElement).checked)" class="sr-only peer" />
            <div class="w-9 h-5 bg-zinc-600 rounded-full peer-checked:bg-emerald-500 transition-colors relative"><div class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4"></div></div>
          </label>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="block text-[11px] text-[#8997aa] mb-1 font-mono">Bot Token</label><input v-model="config.telegram._token" type="password" placeholder="留空保持现有" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" /></div>
          <div><label class="block text-[11px] text-[#8997aa] mb-1 font-mono">Chat ID</label><input v-model="config.telegram.chat_id" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" /></div>
          <div class="col-span-2"><label class="block text-[11px] text-[#8997aa] mb-1 font-mono">API Base URL (国内反代)</label><input v-model="config.telegram.api_base" placeholder="https://api.telegram.org" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" /></div>
        </div>
        <div class="flex space-x-2 mt-3"><button @click="diagnose('telegram')" class="px-3 py-1.5 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">仅诊断</button><button @click="sendTest('telegram')" class="px-3 py-1.5 rounded-lg bg-[#111c2a] border border-emerald-500/30 text-xs font-mono text-emerald-400 cursor-pointer hover:bg-emerald-600/20">发送测试</button></div>
        <div v-if="testResults.telegram" class="mt-2 text-xs font-mono" :class="testResults.telegram.status === 'ready' ? 'text-emerald-400' : 'text-amber-400'">{{ testResults.telegram.status }} · {{ testResults.telegram.detail }}</div>
      </div>

      <!-- WeChat + Webhook -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-2"><span class="inline-block w-2 h-2 rounded-full" :class="config.wechat.enabled ? 'bg-emerald-400' : 'bg-zinc-600'"></span><h2 class="text-sm font-bold text-white font-mono">企业微信</h2></div>
            <label class="flex items-center cursor-pointer"><input type="checkbox" :checked="config.wechat.enabled" @change="toggleChannel('wechat', ($event.target as HTMLInputElement).checked)" class="sr-only peer" /><div class="w-9 h-5 bg-zinc-600 rounded-full peer-checked:bg-emerald-500 transition-colors relative"><div class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4"></div></div></label>
          </div>
          <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">Webhook URL</label>
          <input v-model="config.wechat.webhook" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500 mb-3" />
          <button @click="diagnose('wechat')" class="px-3 py-1.5 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">仅诊断</button>
          <button @click="sendTest('wechat')" class="ml-2 px-3 py-1.5 rounded-lg bg-[#111c2a] border border-emerald-500/30 text-xs font-mono text-emerald-400 cursor-pointer hover:bg-emerald-600/20">发送测试</button>
          <div v-if="testResults.wechat" class="mt-2 text-xs font-mono" :class="testResults.wechat.status === 'ready' ? 'text-emerald-400' : 'text-amber-400'">{{ testResults.wechat.status }} · {{ testResults.wechat.detail }}</div>
        </div>
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-2"><span class="inline-block w-2 h-2 rounded-full" :class="config.webhook.enabled ? 'bg-emerald-400' : 'bg-zinc-600'"></span><h2 class="text-sm font-bold text-white font-mono">通用 Webhook</h2></div>
            <label class="flex items-center cursor-pointer"><input type="checkbox" :checked="config.webhook.enabled" @change="toggleChannel('webhook', ($event.target as HTMLInputElement).checked)" class="sr-only peer" /><div class="w-9 h-5 bg-zinc-600 rounded-full peer-checked:bg-emerald-500 transition-colors relative"><div class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4"></div></div></label>
          </div>
          <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">URL (智能兼容钉钉/飞书/Discord)</label>
          <input v-model="config.webhook.url" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500 mb-3" />
          <button @click="diagnose('webhook')" class="px-3 py-1.5 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">仅诊断</button>
          <button @click="sendTest('webhook')" class="ml-2 px-3 py-1.5 rounded-lg bg-[#111c2a] border border-emerald-500/30 text-xs font-mono text-emerald-400 cursor-pointer hover:bg-emerald-600/20">发送测试</button>
          <div v-if="testResults.webhook" class="mt-2 text-xs font-mono" :class="testResults.webhook.status === 'ready' ? 'text-emerald-400' : 'text-amber-400'">{{ testResults.webhook.status }} · {{ testResults.webhook.detail }}</div>
        </div>
      </div>

      <!-- Schedule + Save -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">每日量化简报时间 (北京时间)</label>
        <input v-model="config._briefingTimes" placeholder="08:00, 20:00" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500 mb-4" />
        <button @click="saveAll" class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold cursor-pointer transition-colors">保存全部通知通道</button>
        <button @click="saveSchedule" class="ml-2 px-4 py-2 rounded-lg bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer">保存通知时间</button>
      </div>
    </template>

    <!-- Capture Modal -->
    <div v-if="captureModal" class="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4" @click.self="captureModal = false">
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-6 w-full max-w-[520px] max-h-[88dvh] overflow-y-auto text-center">
        <h3 class="text-sm font-bold text-white mb-3">⚡ 自动捕获目标用户 OpenID</h3>
        <div class="text-4xl mb-3">📱 💬 🤖</div>
        <p class="text-sm font-bold text-white mb-2">{{ captureStatus?.bot_name || '连接中...' }}</p>
        <p class="text-xs text-[#707E94] font-mono mb-4 leading-relaxed">用手机 QQ 打开与机器人的私聊窗口，发送任意文字（如：绑定）。系统将自动捕获并填入你的 OpenID。</p>
        <div class="bg-[#080B10] border border-[#1A2232] rounded-lg p-3 mb-4">
          <div class="font-bold text-sm" :class="captureStatus?.status === 'captured' ? 'text-emerald-400' : 'text-blue-400'">
            {{ captureStatus?.status === 'captured' ? '捕获成功！' : '正在监听...' }}
          </div>
          <div v-if="captureStatus?.expires_in" class="text-[10px] text-[#707E94] font-mono mt-1">剩余时间：{{ captureStatus.expires_in }} 秒</div>
          <div v-if="captureStatus?.openid" class="text-xs text-emerald-400 font-mono mt-2">OpenID: {{ captureStatus.openid }}</div>
        </div>
        <button @click="captureModal = false" class="px-4 py-2 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">关闭</button>
      </div>
    </div>

    <!-- QQ Bind QR Modal -->
    <div v-if="bindModal" class="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4" @click.self="closeBindModal">
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-5 w-full max-w-[380px] max-h-[88dvh] overflow-y-auto text-center">
        <h3 class="text-sm font-bold text-white mb-2 font-mono">绑定 QQ 机器人</h3>
        <p class="text-[11px] text-[#707E94] font-mono mb-3">使用手机 QQ 扫一扫，或长按复制链接在 QQ 内打开。确认授权后本页自动完成绑定。</p>
        <img v-if="bindStatus?.qr" :src="bindStatus.qr" alt="QQ 绑定二维码" class="w-[220px] h-[220px] rounded-lg bg-white p-2.5 mx-auto mb-3" />
        <p v-if="bindStatus?.link" class="text-[10px] font-mono text-blue-400 break-all mb-3">{{ bindStatus.link }}</p>
        <p class="text-xs font-mono mb-4" :class="{ 'text-blue-400': bindStatus?.tone === 'blue', 'text-emerald-400': bindStatus?.tone === 'green', 'text-amber-400': bindStatus?.tone === 'amber', 'text-rose-400': bindStatus?.tone === 'red' }">{{ bindStatus?.text }}</p>
        <div class="flex justify-center space-x-2">
          <button @click="startQqBind" class="px-3 py-1.5 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">刷新二维码</button>
          <button @click="closeBindModal" class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono cursor-pointer">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>
