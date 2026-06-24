<template>
  <v-card class="glass-panel text-white border-neon-glow h-100 d-flex flex-column" style="min-height: 450px;">
    <v-card-title class="d-flex align-center pb-2 border-bottom">
      <v-avatar size="28" class="bg-neon-gradient mr-2">
        <v-icon size="16" color="white">mdi-chat-processing-outline</v-icon>
      </v-avatar>
      <div>
        <div class="text-subtitle-1 font-weight-bold text-neon-blue">AI-PMO コパイロット</div>
        <div class="text-caption text-grey">タスク遅延リスク・残工数ヒアリング</div>
      </div>
    </v-card-title>
    
    <!-- Chat Messages body -->
    <v-card-text class="flex-grow-1 overflow-y-auto pa-4 d-flex flex-column gap-3" ref="chatBody">
      <div v-if="!taskId" class="text-center text-caption text-grey-darken-1 my-auto">
        <v-icon size="32" class="mb-2" color="grey">mdi-gesture-tap-select</v-icon>
        <div>ガントチャートのタスクをクリックするか、遅延タスクを選択するとヒアリングチャットが開きます。</div>
      </div>
      <div v-else-if="messages.length === 0" class="text-center text-caption text-grey-darken-1 my-auto">
        AIとの会話履歴はありません。遅延が発生すると自動的にヒアリングが開始されます。
      </div>
      
      <div
        v-for="msg in messages"
        :key="msg.id"
        :class="['d-flex', msg.sender_type === 'USER' ? 'justify-end' : 'justify-start']"
      >
        <div class="d-flex max-w-75 align-end gap-1 flex-row">
          <!-- AI Avatar -->
          <v-avatar
            v-if="msg.sender_type !== 'USER'"
            size="24"
            class="bg-neon-gradient mr-1 mb-1"
          >
            <v-icon size="12" color="white">mdi-robot</v-icon>
          </v-avatar>
          
          <div>
            <div class="text-caption text-grey ml-1 mb-1">
              {{ msg.sender_name }} • {{ formatTime(msg.created_at) }}
            </div>
            
            <div
              :class="[
                'pa-3 rounded-lg text-body-2',
                msg.sender_type === 'USER'
                  ? 'bg-neon-gradient text-white rounded-br-0'
                  : 'glass-card border-neon-glow rounded-bl-0'
              ]"
            >
              {{ msg.content }}
            </div>
          </div>
        </div>
      </div>
    </v-card-text>
    
    <!-- Chat Input footer -->
    <v-card-actions v-if="taskId" class="pa-3 border-top">
      <v-text-field
        v-model="replyText"
        placeholder="残工数を入力してください... (例: あと5時間, 2人日)"
        variant="solo-filled"
        bg-color="rgba(255, 255, 255, 0.05)"
        density="compact"
        class="glass-input rounded-lg flex-grow-1"
        hide-details
        clearable
        :disabled="sending"
        @keydown.enter="sendReply"
      >
        <template v-slot:append-inner>
          <v-btn
            icon="mdi-send"
            variant="text"
            color="primary"
            size="small"
            :disabled="!replyText || sending"
            @click="sendReply"
          ></v-btn>
        </template>
      </v-text-field>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useProjectStore } from '../store/project'

const props = defineProps({
  taskId: {
    type: String,
    default: null
  }
})

const store = useProjectStore()
const replyText = ref('')
const sending = ref(false)
const chatBody = ref(null)

const messages = computed(() => {
  return store.getMessagesByTask(props.taskId)
})

const formatTime = (isoString) => {
  if (!isoString) return ''
  const d = new Date(isoString)
  return d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTo({
        top: chatBody.value.scrollHeight,
        behavior: 'smooth'
      })
    }
  })
}

const sendReply = async () => {
  if (!replyText.value || sending.value) return
  
  sending.value = true
  const text = replyText.value
  replyText.value = ''
  
  try {
    // Send message which triggers RAG/effort recalculation on backend
    await store.submitHearing(props.taskId, text)
    scrollToBottom()
  } catch (err) {
    console.error('Failed to submit reply:', err)
  } finally {
    sending.value = false
  }
}

// Watch messages to auto-scroll
watch(
  () => messages.value,
  () => {
    scrollToBottom()
  },
  { deep: true }
)

// Watch taskId changes to load chats
watch(
  () => props.taskId,
  async (newId) => {
    if (newId) {
      await store.fetchMessages(newId)
      scrollToBottom()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.gap-1 {
  gap: 4px;
}
.gap-3 {
  gap: 12px;
}
.max-w-75 {
  max-width: 75%;
}
.border-top {
  border-top: 1px solid rgba(255, 255, 255, 0.08) !important;
}
</style>
