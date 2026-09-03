<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import { HardDrive, RefreshCw, PlugZap, Save, PlayCircle, Archive, AlertCircle } from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()

const simple = ref<any>(null)
const targetTypes = ref<any[]>([])
const status = ref<any>(null)
const loading = ref(true)
const busy = ref('')
const bannerMsg = ref<{ text: string; type: 'ok' | 'err' | 'warn' } | null>(null)

// form
const enabled = ref(true)
const destination = ref('')
const scheduleTime = ref('02:00')
const retention = ref(3)
const endpoint = ref('')
const bucket = ref('')
const credentials = ref<Record<string, string>>({})

const remoteDest = computed(() => ['s3', 'oss', 'webdav', 'baidu_oauth'].includes(destination.value))
const needsBucket = computed(() => destination.value === 's3' || destination.value === 'oss')
const credentialFields = computed(() => {
  if (destination.value === 's3' || destination.value === 'oss') return ['access_key_id', 'secret_access_key']
  if (destination.value === 'baidu_oauth') return ['app_key', 'app_secret', 'refresh_token']
  return []
})

async function load() {
  loading.value = true
  try {
    const [s, t, st] = await Promise.all([
      api('/api/v1/admin/backups/simple'),
      api('/api/v1/admin/backup-target-types'),
      api('/api/v1/admin/backups'),
    ])
    simple.value = s
    targetTypes.value = t.target_types || []
    status.value = st
    enabled.value = s.enabled
    destination.value = s.destination
    scheduleTime.value = s.schedule_time || '02:00'
    retention.value = s.retention || 3
    endpoint.value = s.target?.endpoint || ''
    bucket.value = s.target?.bucket || ''
  } catch (e: any) {
    bannerMsg.value = { text: `加载失败：${e.message}`, type: 'err' }
  } finally {
    loading.value = false
  }
}

function payload() {
  return {
    enabled: enabled.value,
    schedule_time: scheduleTime.value,
    destination: destination.value,
    retention: Number(retention.value) || 3,
    endpoint: endpoint.value.trim(),
    bucket: bucket.value.trim(),
    credentials: credentials.value,
  }
}

async function testConnection() {
  busy.value = 'test'
  bannerMsg.value = null
  try {
    const res = await api('/api/v1/admin/backups/simple/test', { method: 'POST', body: JSON.stringify(payload()) })
    bannerMsg.value = { text: `✅ ${res.detail}`, type: 'ok' }
  } catch (e: any) {
    bannerMsg.value = { text: `测试失败：${e.message}`, type: 'err' }
  } finally {
    busy.value = ''
  }
}

async function save() {
  busy.value = 'save'
  bannerMsg.value = null
  try {
    await api('/api/v1/admin/backups/simple', { method: 'PUT', body: JSON.stringify(payload()) })
    bannerMsg.value = { text: '✅ 灾备配置已保存，每天北京时间 ' + scheduleTime.value + ' 自动执行', type: 'ok' }
    await load()
  } catch (e: any) {
    bannerMsg.value = { text: `保存失败：${e.message}`, type: 'err' }
  } finally {
    busy.value = ''
  }
}

async function runNow() {
  const phrase = prompt('立即执行完整灾备（打包并按已启用目标上传）需输入确认短语：BACKUP R20')
  if (!phrase) return
  busy.value = 'run'
  bannerMsg.value = null
  try {
    const res = await api('/api/v1/admin/backups/run', { method: 'POST', body: JSON.stringify({ confirmation: phrase.trim().toUpperCase() }) })
    bannerMsg.value = { text: `✅ 灾备执行完成（${(res.output || '').length} 字符输出已记录）`, type: 'ok' }
    await load()
  } catch (e: any) {
    bannerMsg.value = { text: `灾备失败：${e.message}`, type: 'err' }
  } finally {
    busy.value = ''
  }
}

function fmtBytes(n: number) {
  if (!n) return '--'
  return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.round(n / 1024) + ' KB'
}
function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' })
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">像 Duplicati / Kopia 一样，只配置内容、位置、时间和保留数量；上传成功后自动清理本地压缩包保持 0 磁盘占用。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">集成与保障 · 2/3</span>
    </div>

    <div v-if="bannerMsg" class="p-3 rounded-lg text-xs font-mono border" :class="bannerMsg.type === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : bannerMsg.type === 'warn' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'">
      <div class="flex items-start gap-2"><AlertCircle v-if="bannerMsg.type !== 'ok'" class="w-4 h-4 shrink-0 mt-0.5" /><span>{{ bannerMsg.text }}</span></div>
    </div>

    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]"><RefreshCw class="w-5 h-5 animate-spin inline mr-1.5 text-blue-400" />正在加载灾备配置...</div>

    <template v-else-if="simple">
      <!-- Simple Config -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center space-x-2">
            <HardDrive class="w-4 h-4 text-blue-400" />
            <h2 class="text-sm font-bold text-white font-mono">自动灾备</h2>
          </div>
          <label class="flex items-center space-x-2 text-xs font-mono cursor-pointer">
            <input v-model="enabled" type="checkbox" class="accent-blue-500 w-4 h-4" :disabled="!auth.isSuperadmin" />
            <span :class="enabled ? 'text-emerald-400' : 'text-[#707E94]'">{{ enabled ? '每日自动灾备已启用' : '已停用' }}</span>
          </label>
        </div>

        <div v-if="simple.legacy_bypy" class="mb-4 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/25 text-amber-400 text-[11px] font-mono">⚠ {{ simple.migration_note }}</div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">1. 备份内容</label>
            <select disabled class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono opacity-70">
              <option>R20 系统、策略、配置与运行数据</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">2. 保存位置</label>
            <select v-model="destination" :disabled="!auth.isSuperadmin" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500">
              <option value="local">本地滚动归档</option>
              <option value="s3">S3 兼容存储</option>
              <option value="oss">阿里云 OSS</option>
              <option value="webdav">WebDAV / OpenList</option>
              <option value="baidu_oauth">百度网盘（官方 OAuth）</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">3. 每天执行时间（北京时间）</label>
            <input v-model="scheduleTime" type="time" :disabled="!auth.isSuperadmin" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">4. 保留最近几份{{ destination === 'local' ? '（本地）' : '' }}</label>
            <input v-model="retention" type="number" min="1" max="365" :disabled="!auth.isSuperadmin" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
        </div>

        <!-- Remote Credentials -->
        <div v-if="remoteDest" class="mt-4 p-3 rounded-lg bg-[#080B10] border border-[#1A2232]">
          <div class="text-[11px] text-[#8997aa] font-mono mb-2">连接信息（保存进本机加密密文库，不回显明文）</div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div v-if="destination !== 'baidu_oauth'">
              <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">Endpoint</label>
              <input v-model="endpoint" :disabled="!auth.isSuperadmin" placeholder="https://s3.us-west-004.backblazeb2.com" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
            </div>
            <div v-if="needsBucket">
              <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">Bucket</label>
              <input v-model="bucket" :disabled="!auth.isSuperadmin" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
            </div>
            <div v-for="f in credentialFields" :key="f">
              <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">{{ f }}</label>
              <input v-model="credentials[f]" type="password" :disabled="!auth.isSuperadmin" :placeholder="simple.configured ? '留空保持现有值' : ''" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
            </div>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 mt-4">
          <template v-if="auth.isSuperadmin">
            <button @click="testConnection" :disabled="busy !== ''" class="flex items-center space-x-1 px-3 py-2 rounded-lg bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer disabled:opacity-40"><PlugZap class="w-3.5 h-3.5" /><span>{{ busy === 'test' ? '测试中...' : '测试连接' }}</span></button>
            <button @click="save" :disabled="busy !== ''" class="flex items-center space-x-1 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold cursor-pointer disabled:opacity-40"><Save class="w-3.5 h-3.5" /><span>{{ busy === 'save' ? '保存中...' : '保存灾备' }}</span></button>
            <button @click="runNow" :disabled="busy !== ''" class="flex items-center space-x-1 px-3 py-2 rounded-lg bg-[#4d1924] hover:bg-[#5d2230] border border-[#873044] text-xs font-mono text-[#ffdce1] cursor-pointer disabled:opacity-40"><PlayCircle class="w-3.5 h-3.5" /><span>{{ busy === 'run' ? '执行中（最长10分钟）...' : '立即备份' }}</span></button>
          </template>
          <span v-else class="text-[10px] font-mono text-[#707E94]">只读视图 · 修改需超级管理员登录</span>
          <span class="ml-auto text-[10px] font-mono" :class="simple.configured ? 'text-emerald-400' : 'text-amber-400'">{{ simple.configured ? '● 目标已配置' : '● 目标未配置' }}</span>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Latest -->
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <h2 class="text-xs font-bold text-white font-mono uppercase mb-3">最近一次灾备</h2>
          <div v-if="simple.latest" class="space-y-1.5 text-xs font-mono">
            <div class="flex justify-between bg-[#080B10] border border-[#1A2232] rounded-lg px-3 py-2"><span class="text-[#707E94]">时间</span><span class="text-white">{{ simple.latest.created_at || simple.latest.time || JSON.stringify(simple.latest).slice(0, 60) }}</span></div>
            <div class="flex justify-between bg-[#080B10] border border-[#1A2232] rounded-lg px-3 py-2"><span class="text-[#707E94]">状态</span><span class="text-emerald-400">{{ simple.latest.status || 'success' }}</span></div>
          </div>
          <div v-else class="py-6 text-center text-xs text-[#707E94] font-mono">尚无匹配的灾备清单记录</div>
          <div class="text-[10px] text-[#6f7d91] font-mono mt-3 leading-relaxed">{{ status?.schedule }}</div>
        </div>

        <!-- Local archives -->
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center space-x-2 mb-3"><Archive class="w-4 h-4 text-cyan-400" /><h2 class="text-xs font-bold text-white font-mono uppercase">本地待清归档 ({{ status?.local_archives?.length ?? 0 }})</h2></div>
          <table v-if="status?.local_archives?.length" class="w-full text-left text-xs font-mono">
            <thead><tr class="text-[#707E94] border-b border-[#1A2232]"><th class="pb-1.5">文件</th><th class="pb-1.5 text-right">大小</th><th class="pb-1.5 text-right">时间</th></tr></thead>
            <tbody class="divide-y divide-[#1A2232]/50">
              <tr v-for="a in status.local_archives.slice(0, 8)" :key="a.name">
                <td class="py-1.5 text-zinc-300 truncate max-w-[220px]">{{ a.name }}</td>
                <td class="py-1.5 text-right text-zinc-300">{{ fmtBytes(a.bytes) }}</td>
                <td class="py-1.5 text-right text-[#707E94]">{{ fmtTime(a.mtime) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="py-6 text-center text-xs text-emerald-400 font-mono">✓ 本地 0 归档占用（上传成功后已物理清理）</div>
        </div>
      </div>
    </template>
  </div>
</template>
