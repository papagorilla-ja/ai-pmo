<template>
  <div class="login-wrapper d-flex align-center justify-center">
    <div class="login-glow-circle circle-1"></div>
    <div class="login-glow-circle circle-2"></div>
    
    <div class="login-card pa-8 text-white">
      <div class="text-center mb-6">
        <v-avatar size="48" class="bg-neon-gradient mb-3">
          <v-icon size="28" color="white">mdi-shield-crown-outline</v-icon>
        </v-avatar>
        <h1 class="text-h4 font-weight-black text-neon-blue mb-1">AI-PMO</h1>
        <p class="text-caption text-grey-lighten-1">自律型プロジェクト管理システム</p>
      </div>

      <v-alert
        v-if="errorMessage"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-4 rounded-lg border-error-glow text-caption"
        closable
        @click:close="errorMessage = ''"
      >
        {{ errorMessage }}
      </v-alert>

      <form @submit.prevent="handleLogin">
        <div class="mb-4">
          <label for="email" class="text-caption font-weight-bold text-grey-lighten-2 d-block mb-1">メールアドレス</label>
          <v-text-field
            id="email"
            v-model="email"
            name="email"
            type="email"
            autocomplete="username"
            required
            variant="solo-filled"
            bg-color="rgba(255, 255, 255, 0.05)"
            class="glass-input rounded-lg"
            hide-details="auto"
            placeholder="nhigashira@example.com"
            prepend-inner-icon="mdi-email-outline"
            :disabled="loading"
          ></v-text-field>
        </div>

        <div class="mb-6">
          <div class="d-flex justify-space-between align-center mb-1">
            <label for="current-password" class="text-caption font-weight-bold text-grey-lighten-2">パスワード</label>
          </div>
          <v-text-field
            id="current-password"
            v-model="password"
            name="password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            required
            variant="solo-filled"
            bg-color="rgba(255, 255, 255, 0.05)"
            class="glass-input rounded-lg"
            hide-details="auto"
            placeholder="••••••••"
            prepend-inner-icon="mdi-lock-outline"
            :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
            @click:append-inner="showPassword = !showPassword"
            :disabled="loading"
          ></v-text-field>
        </div>

        <v-btn
          type="submit"
          block
          height="48"
          class="bg-neon-gradient text-white font-weight-bold rounded-lg login-btn"
          :loading="loading"
          :disabled="loading || !email || !password"
        >
          Sign In
        </v-btn>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '../store/project'

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const errorMessage = ref('')
const loading = ref(false)

const store = useProjectStore()
const router = useRouter()
const route = useRoute()

const handleLogin = async () => {
  if (!email.value || !password.value) return
  
  loading.value = true
  errorMessage.value = ''
  
  try {
    await store.login(email.value, password.value)
    
    // Redirect back to original target or home
    const redirectPath = route.query.redirect || '/'
    router.push(redirectPath)
  } catch (err) {
    console.error('Login failed:', err)
    errorMessage.value = err.response?.data?.detail || 'メールアドレスまたはパスワードが正しくありません。'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: #05070a;
  overflow: hidden;
  z-index: 9999; /* Ensure it covers the sidebar and WBS layout entirely */
}

.login-glow-circle {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.15;
  z-index: 0;
}

.circle-1 {
  top: 20%;
  left: 25%;
  width: 350px;
  height: 350px;
  background: #00f2fe;
}

.circle-2 {
  bottom: 20%;
  right: 25%;
  width: 350px;
  height: 350px;
  background: #4facfe;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: rgba(13, 17, 23, 0.65) !important;
  backdrop-filter: blur(25px) saturate(180%);
  -webkit-backdrop-filter: blur(25px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 24px;
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
  position: relative;
  z-index: 10;
}

.bg-neon-gradient {
  background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%) !important;
}

.text-neon-blue {
  color: #00f2fe;
  text-shadow: 0 0 15px rgba(0, 242, 254, 0.3);
}

.glass-input :deep(.v-field) {
  background: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 12px !important;
  transition: all 0.3s ease;
}

.glass-input :deep(.v-field--focused) {
  border-color: #00f2fe !important;
  box-shadow: 0 0 10px rgba(0, 242, 254, 0.2) !important;
}

.border-error-glow {
  border: 1px solid rgba(255, 82, 82, 0.3) !important;
  box-shadow: 0 0 8px rgba(255, 82, 82, 0.1) !important;
}

.login-btn {
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(0, 242, 254, 0.2);
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 242, 254, 0.4);
}
</style>
