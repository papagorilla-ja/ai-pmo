<template>
  <v-card class="glass-panel text-white border-neon-glow h-100 d-flex flex-column">
    <v-card-title class="d-flex align-center pb-2 border-bottom">
      <v-avatar size="28" class="bg-neon-gradient mr-2">
        <v-icon size="16" color="white">mdi-comment-multiple-outline</v-icon>
      </v-avatar>
      <div>
        <div class="text-subtitle-1 font-weight-bold text-neon-purple">インラインAIレビュー</div>
        <div class="text-caption text-grey">仕様の矛盾・バグ検知アラート</div>
      </div>
    </v-card-title>
    
    <v-card-text class="flex-grow-1 overflow-y-auto pa-4 d-flex flex-column gap-3">
      <div v-if="!taskId" class="text-center text-caption text-grey-darken-1 my-auto">
        選択された成果物はありません。
      </div>
      <div v-else-if="comments.length === 0" class="text-center text-caption text-grey-darken-1 my-auto">
        この成果物に対するAIの指摘・レビューコメントはありません。
      </div>
      
      <div
        v-for="c in filteredComments"
        :key="c.id"
        class="glass-card pa-4 border-neon-glow"
      >
        <div class="d-flex align-center justify-between mb-2">
          <div class="d-flex align-center">
            <v-avatar size="20" class="bg-neon-gradient mr-2">
              <v-icon size="12" color="white">mdi-robot</v-icon>
            </v-avatar>
            <span class="text-caption font-weight-bold text-neon-blue">{{ c.author }}</span>
          </div>
          <span class="text-caption text-grey">{{ formatTime(c.created_at) }}</span>
        </div>
        
        <div v-if="c.line_number" class="text-caption text-primary mb-2">
          <v-icon size="12" start>mdi-format-line-spacing</v-icon> 行番号: {{ c.line_number }}行目
        </div>
        
        <div class="text-body-2 text-white style-pre-wrap mb-3">{{ c.content }}</div>
        
        <!-- Apply buttons or action mocks -->
        <div v-if="c.line_number" class="d-flex justify-end gap-2">
          <v-btn size="x-small" color="primary" variant="tonal" @click="applyFix(c.line_number)">
            修正案を適用する
          </v-btn>
        </div>
      </div>
    </v-card-text>
    
    <v-card-actions v-if="taskId" class="pa-3 border-top">
      <v-text-field
        v-model="newComment"
        placeholder="AIに質問・コメントを送信..."
        variant="solo-filled"
        bg-color="rgba(255, 255, 255, 0.05)"
        density="compact"
        class="glass-input rounded-lg flex-grow-1"
        hide-details
        @keydown.enter="postUserComment"
      >
        <template v-slot:append-inner>
          <v-btn
            icon="mdi-send"
            variant="text"
            color="secondary"
            size="small"
            :disabled="!newComment"
            @click="postUserComment"
          ></v-btn>
        </template>
      </v-text-field>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useProjectStore } from '../store/project'

const props = defineProps({
  taskId: {
    type: String,
    default: null
  },
  selectedLine: {
    type: Number,
    default: null
  }
})

const store = useProjectStore()
const newComment = ref('')

const comments = computed(() => {
  return store.comments
})

const filteredComments = computed(() => {
  if (props.selectedLine !== null) {
    return store.comments.filter(c => c.line_number === props.selectedLine)
  }
  return store.comments
})

const formatTime = (isoString) => {
  if (!isoString) return ''
  const d = new Date(isoString)
  return d.toLocaleDateString('ja-JP') + ' ' + d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
}

const postUserComment = async () => {
  if (!newComment.value) return
  const text = newComment.value
  newComment.value = ''
  
  await store.postComment(props.taskId, text, 'User', props.selectedLine)
}

const applyFix = (line) => {
  // Emit apply-fix event to parent
  emit('apply-fix', line)
}

const emit = defineEmits(['apply-fix'])

watch(
  () => props.taskId,
  async (newId) => {
    if (newId) {
      await store.fetchComments(newId)
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
.gap-3 {
  gap: 12px;
}
.style-pre-wrap {
  white-space: pre-wrap;
}
.border-top {
  border-top: 1px solid rgba(255, 255, 255, 0.08) !important;
}
</style>
