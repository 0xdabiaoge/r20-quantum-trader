<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { LogIn, AlertCircle } from 'lucide-vue-next'

const auth = useAuthStore()
const router = useRouter()
const username = ref('admin')
const password = ref('')
const loading = ref(false)

async function handleLogin() {
  loading.value = true
  const ok = await auth.login(username.value, password.value)
  loading.value = false
  if (ok) {
    router.push('/admin/overview')
  }
}
</script>

<template>
  <div class="min-h-screen bg-[#080B10] flex items-center justify-center px-4">
    <div class="w-full max-w-[410px]">
      <!-- Brand -->
      <div class="flex items-center space-x-2.5 mb-6 justify-center">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20 ring-1 ring-white/20">
          <span class="text-white font-black text-lg tracking-wider">R</span>
        </div>
        <div>
          <div class="text-sm font-bold text-white tracking-wide">R20 CONTROL</div>
          <div class="text-[11px] text-[#707E94] font-mono">管理员账号登录</div>
        </div>
      </div>

      <!-- Card -->
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-6 shadow-2xl">
        <div v-if="auth.error" class="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono flex items-start gap-2">
          <AlertCircle class="w-4 h-4 shrink-0 mt-0.5" />
          <span>{{ auth.error }}</span>
        </div>

        <label class="block text-[11px] text-[#8997aa] mb-1.5 font-mono">管理员账号</label>
        <input
          v-model="username"
          type="text"
          autocomplete="username"
          class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2.5 text-sm font-mono outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/12 mb-3"
        />

        <label class="block text-[11px] text-[#8997aa] mb-1.5 font-mono">密码</label>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          placeholder="输入管理员密码"
          class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2.5 text-sm font-mono outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/12 mb-5"
          @keyup.enter="handleLogin"
        />

        <button
          @click="handleLogin"
          :disabled="loading"
          class="w-full flex items-center justify-center space-x-2 bg-gradient-to-b from-[#1d4680] to-[#173a6a] hover:from-[#235390] hover:to-[#1a4070] text-white font-bold text-sm py-2.5 rounded-lg border border-[#35649f] transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <LogIn v-if="!loading" class="w-4 h-4" />
          <RefreshCw v-else class="w-4 h-4 animate-spin" />
          <span>{{ loading ? '登录中...' : '登录控制台' }}</span>
        </button>

        <p class="mt-4 text-[10px] text-[#6f7d91] font-mono leading-relaxed">
          账号为 admin；密码是管理员系统迁移时设置或后续修改后的密码。连续失败 5 次会临时锁定 15 分钟。
        </p>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { RefreshCw } from 'lucide-vue-next'
</script>
