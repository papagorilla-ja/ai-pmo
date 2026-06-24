<template>
  <v-app class="app-background">
    <!-- Navigation Drawer (Only shown if logged in and not on login page) -->
    <v-navigation-drawer
      v-if="$route.path !== '/login'"
      permanent
      class="glass-panel border-neon-glow ma-4 rounded-xl"
      elevation="0"
      width="260"
      style="height: calc(100vh - 32px); background: rgba(13,17,23,0.6) !important; backdrop-filter: blur(20px);"
    >
      <div class="pa-4 d-flex align-center gap-2 border-bottom">
        <v-avatar size="36" class="bg-neon-gradient">
          <v-icon size="20" color="white">mdi-shield-crown-outline</v-icon>
        </v-avatar>
        <div>
          <span class="text-h6 font-weight-black text-neon-blue">AI-PMO</span>
          <span class="text-caption d-block text-grey">自律型プロジェクト管理</span>
        </div>
      </div>
      
      <!-- Logged-in User Panel -->
      <div class="px-4 py-4 border-bottom" v-if="store.currentUser">
        <div class="text-caption text-grey mb-2 font-weight-bold d-flex align-center">
          <v-icon size="14" class="mr-1">mdi-account-outline</v-icon>
          <span>ログインユーザー</span>
        </div>
        <div class="d-flex align-center justify-space-between mb-3">
          <div class="user-info-text overflow-hidden mr-2">
            <div class="text-body-2 font-weight-bold text-white text-truncate">{{ store.currentUser.name }}</div>
            <div class="text-caption text-grey text-truncate">{{ store.currentUser.role }}</div>
          </div>
          <v-chip size="x-small" :color="roleColor" variant="flat" class="text-white font-weight-bold shrink-0">
            {{ store.currentRole }}
          </v-chip>
        </div>
        <v-btn
          block
          size="small"
          variant="tonal"
          color="error"
          class="rounded-lg"
          prepend-icon="mdi-logout"
          @click="handleLogout"
        >
          ログアウト
        </v-btn>
      </div>
      
      <v-list density="comfortable" class="mt-4 px-2">
        <v-list-item
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="rounded-lg mb-2 text-white glass-item"
          base-color="primary"
          link
        >
          <template v-slot:prepend>
            <v-icon :color="$route.path === item.path ? 'primary' : 'grey'">{{ item.icon }}</v-icon>
          </template>
          <v-list-item-title class="font-weight-medium">{{ item.title }}</v-list-item-title>
        </v-list-item>
      </v-list>

      <template v-slot:append>
        <div class="pa-4">
          <v-btn
            block
            variant="outlined"
            color="primary"
            class="rounded-lg border-neon-glow"
            prepend-icon="mdi-console"
            @click="triggerPalette"
          >
            コマンドパレット
          </v-btn>
          <div class="text-center text-caption text-grey mt-2">Press <kbd class="glass-kbd">Cmd + K</kbd> anywhere</div>
        </div>
      </template>
    </v-navigation-drawer>

    <!-- Main View Content Area -->
    <v-main
      class="main-content-area"
      :class="{ 'ma-4 pl-0': $route.path !== '/login' }"
      :style="$route.path !== '/login' ? 'padding-left: 276px !important;' : 'padding-left: 0px !important; margin: 0 !important;'"
    >
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </v-main>

    <!-- Command Palette component (Only if logged in) -->
    <CommandPalette v-if="$route.path !== '/login'" ref="cmdPalette" />
  </v-app>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import CommandPalette from './components/CommandPalette.vue'
import { useProjectStore } from './store/project'

const cmdPalette = ref(null)
const store = useProjectStore()
const router = useRouter()

const roleColor = computed(() => {
  switch (store.currentRole) {
    case '管理者': return 'primary'
    case 'マネージャ': return 'warning'
    case 'メンバー': return 'success'
    default: return 'grey'
  }
})

const handleLogout = () => {
  store.logout()
  router.push('/login')
}

const navItems = computed(() => {
  const items = [
    { title: 'ダッシュボード', icon: 'mdi-view-dashboard-outline', path: '/' },
    { title: 'WBS', icon: 'mdi-chart-gantt', path: '/gantt' },
    { title: 'ナレッジベース', icon: 'mdi-database-cog-outline', path: '/knowledge' },
    { title: '成果物レビュー', icon: 'mdi-file-code-outline', path: '/artifacts' }
  ]
  
  if (store.currentRole !== 'メンバー') {
    items.push({ title: 'システム管理', icon: 'mdi-cog-outline', path: '/admin' })
  }
  
  return items
})

const triggerPalette = () => {
  if (cmdPalette.value) {
    cmdPalette.value.togglePalette()
  }
}
</script>

<style>
.app-background {
  background-color: #05070a !important;
}
.main-content-area {
  height: calc(100vh - 32px);
  overflow-y: auto;
}
.border-bottom {
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.gap-2 {
  gap: 8px;
}
.shrink-0 {
  flex-shrink: 0;
}
.glass-kbd {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 11px;
}
.glass-item {
  transition: background-color 0.2s ease, border-color 0.2s ease;
}
.glass-item:hover {
  background: rgba(255, 255, 255, 0.04) !important;
}
.glass-item.v-list-item--active {
  background: rgba(0, 242, 254, 0.08) !important;
  border: 1px solid rgba(0, 242, 254, 0.2) !important;
}
.user-info-text {
  flex: 1;
}
</style>
