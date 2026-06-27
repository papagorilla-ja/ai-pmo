<template>
  <v-dialog v-model="visible" max-width="700px" content-class="glass-panel border-neon-glow" persistent>
    <v-card class="bg-transparent text-white border-0 pa-4" style="backdrop-filter: blur(20px);">
      <v-card-title class="d-flex justify-between align-center border-bottom pb-2">
        <span class="text-neon-blue font-weight-bold"><v-icon start color="primary">mdi-console</v-icon> コマンドパレット (Cmd + K)</span>
        <v-spacer></v-spacer>
        <v-btn icon="mdi-close" variant="text" size="small" color="white" @click="close"></v-btn>
      </v-card-title>
      
      <v-card-text class="pt-4">
        <!-- Input box -->
        <v-text-field
          ref="inputField"
          v-model="cmdText"
          placeholder="@AI コマンドを入力してください (例: @AI ヒアリング, @AI crawl)"
          variant="solo-filled"
          bg-color="rgba(255,255,255,0.05)"
          class="glass-input rounded-lg mb-4"
          hide-details
          clearable
          @keydown.enter="submit"
        ></v-text-field>

        <!-- Screen context badge -->
        <div v-if="store.currentProjectId || store.selectedTaskId" class="mb-3 d-flex align-center gap-2 flex-wrap">
          <v-chip size="x-small" color="info" label prepend-icon="mdi-map-marker">
            {{ SCREEN_LABELS[route.name] || route.name }}
          </v-chip>
          <v-chip
            v-if="store.currentProjectId"
            size="x-small"
            color="primary"
            label
            prepend-icon="mdi-folder-outline"
          >
            {{ store.portfolioProjects.find(p => p.id === store.currentProjectId)?.name || store.currentProjectId }}
          </v-chip>
          <v-chip
            v-if="store.selectedTaskId"
            size="x-small"
            color="secondary"
            label
            prepend-icon="mdi-checkbox-marked-outline"
          >
            {{ store.tasks.find(t => t.id === store.selectedTaskId)?.title || store.selectedTaskId }}
          </v-chip>
        </div>

        <!-- Command suggestions -->
        <div v-if="!executing && !responseMsg" class="mb-4">
          <div class="text-caption text-grey-darken-1 mb-2">利用可能なクイックコマンド</div>
          <v-chip-group>
            <v-chip
              v-for="s in suggestions"
              :key="s"
              size="small"
              color="primary"
              variant="outlined"
              class="mr-2 mb-2"
              @click="selectSuggestion(s)"
            >
              {{ s }}
            </v-chip>
          </v-chip-group>
        </div>

        <!-- Progress linear -->
        <v-progress-linear
          v-if="executing"
          indeterminate
          color="primary"
          class="my-4"
        ></v-progress-linear>

        <!-- Response Area -->
        <div v-if="responseMsg" class="pa-4 rounded-lg rgba-bg mt-4 glass-card">
          <div class="d-flex align-center mb-2">
            <v-avatar size="24" class="bg-neon-gradient mr-2">
              <v-icon size="14" color="white">mdi-robot</v-icon>
            </v-avatar>
            <span class="text-neon-blue font-weight-bold text-caption">AI PMO レスポンス</span>
          </div>
          <p class="text-body-2 text-white style-pre-wrap">{{ responseMsg }}</p>
        </div>

        <!-- Repo selection chips (shown after SELECT_REPO action) -->
        <div v-if="repoOptions.length > 0" class="mt-3">
          <div class="text-caption text-grey-darken-1 mb-2">リポジトリを選択:</div>
          <v-chip-group>
            <v-chip
              v-for="repo in repoOptions"
              :key="repo.full_name"
              size="small"
              color="success"
              variant="outlined"
              class="mr-2 mb-2"
              prepend-icon="mdi-source-repository"
              @click="selectRepo(repo.full_name)"
            >
              {{ repo.full_name }}
            </v-chip>
          </v-chip-group>
        </div>
      </v-card-text>

      <v-card-actions class="d-flex justify-end pt-2">
        <v-btn variant="text" color="grey" @click="close">閉じる</v-btn>
        <v-btn
          variant="flat"
          class="bg-neon-gradient text-white"
          :disabled="!cmdText || executing"
          @click="submit"
        >
          送信
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '../store/project'

const store = useProjectStore()
const route = useRoute()
const visible = ref(false)
const cmdText = ref('')
const responseMsg = ref('')
const executing = ref(false)
const inputField = ref(null)
const repoOptions = ref([])

const SCREEN_LABELS = {
  Dashboard: 'ダッシュボード',
  GanttView: 'ガントチャート',
  KnowledgeView: 'ナレッジ管理',
  ArtifactsView: '成果物管理',
  AdminView: 'システム管理',
}

const suggestions = computed(() => {
  const routeName = route.name
  if (routeName === 'GanttView') {
    const base = [
      '@AI このスケジュールを最適化して',
      '@AI 遅延タスクの残工数をヒアリングして',
      '@AI プランBを適用して',
      '@AI Giteaクロール',
    ]
    if (store.selectedTaskId) base.unshift('@AI このタスクをヒアリングして')
    return base
  }
  if (routeName === 'Dashboard') {
    return [
      '@AI EVM分析の根拠を詳しく説明して',
      '@AI 遅延タスクの残工数をヒアリングして',
      'タスク一覧の進捗をチェックして',
    ]
  }
  if (routeName === 'ArtifactsView') {
    return [
      '@AI この成果物のリスクを説明して',
      'タスク一覧の進捗をチェックして',
    ]
  }
  return [
    '@AI 遅延タスクの残工数をヒアリングして',
    '@AI 夜間クロールを起動',
    '@AI Giteaクロール',
    '@AI プランBを適用して',
    'タスク一覧の進捗をチェックして',
  ]
})

const buildScreenContext = () => {
  const ctx = {
    screen: route.name || 'Unknown',
    screen_label: SCREEN_LABELS[route.name] || route.name || '不明',
  }
  if (store.currentProjectId) {
    const proj = store.portfolioProjects.find(p => p.id === store.currentProjectId)
    ctx.project_id = store.currentProjectId
    ctx.project_name = proj?.name || null
  }
  if (store.selectedTaskId) {
    const task = store.tasks.find(t => t.id === store.selectedTaskId)
    ctx.task_id = store.selectedTaskId
    ctx.task_title = task?.title || null
  }
  return ctx
}

const togglePalette = () => {
  visible.value = !visible.value
  if (visible.value) {
    cmdText.value = ''
    responseMsg.value = ''
    nextTick(() => {
      // Focus input field
      const inputEl = document.querySelector('.glass-input input')
      if (inputEl) inputEl.focus()
    })
  }
}

const selectSuggestion = (text) => {
  cmdText.value = text
  submit()
}

const close = () => {
  visible.value = false
  repoOptions.value = []
}

const submit = async () => {
  if (!cmdText.value || executing.value) return
  
  executing.value = true
  responseMsg.value = ''
  repoOptions.value = []
  
  try {
    const res = await store.executeCommand(cmdText.value, buildScreenContext())
    if (res.action === 'SELECT_REPO') {
      responseMsg.value = res.message
      repoOptions.value = res.repos || []
    } else if (res.success) {
      responseMsg.value = res.message
    } else {
      responseMsg.value = `エラー: ${res.message}`
    }
  } catch (err) {
    responseMsg.value = `実行エラー: ${err.message}`
  } finally {
    executing.value = false
  }
}

const selectRepo = (fullName) => {
  cmdText.value = `@AI Giteaクロール ${fullName}`
  submit()
}

// Global key bindings
const handleKeyDown = (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    togglePalette()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

defineExpose({ togglePalette })
</script>

<style scoped>
.style-pre-wrap {
  white-space: pre-wrap;
}
.rgba-bg {
  background: rgba(255,255,255,0.02);
}
</style>
