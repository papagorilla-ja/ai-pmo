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
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useProjectStore } from '../store/project'

const store = useProjectStore()
const visible = ref(false)
const cmdText = ref('')
const responseMsg = ref('')
const executing = ref(false)
const inputField = ref(null)

const suggestions = [
  '@AI 遅延タスクの残工数をヒアリングして',
  '@AI 夜間クロールを起動',
  '@AI プランBを適用して',
  'タスク一覧の進捗をチェックして'
]

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
}

const submit = async () => {
  if (!cmdText.value || executing.value) return
  
  executing.value = true
  responseMsg.value = ''
  
  try {
    const res = await store.executeCommand(cmdText.value)
    if (res.success) {
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
