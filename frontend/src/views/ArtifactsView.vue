<template>
  <v-container fluid class="pa-6">
    <div class="d-flex align-center justify-between mb-6 flex-wrap gap-3">
      <div>
        <h1 class="text-h4 font-weight-bold text-neon-blue">AI 成果物 & レビュー</h1>
        <p class="text-caption text-grey">AIワーカーが生成した成果物の確認とインラインバグ検知</p>
      </div>
      <v-spacer></v-spacer>
      
      <!-- Actions & Selector -->
      <div class="d-flex align-center gap-3">
        <v-btn
          v-if="selectedTaskId"
          variant="flat"
          class="bg-neon-gradient text-white font-weight-bold mr-2"
          prepend-icon="mdi-shield-check-outline"
          :loading="store.loading"
          @click="handleGovernanceAudit"
        >
          ガバナンス監査を実行
        </v-btn>
        
        <div style="width: 280px;">
          <v-select
            v-model="selectedTaskId"
            :items="tasksWithArtifacts"
            item-title="title"
            item-value="id"
            label="成果物ファイルを選択"
            variant="solo-filled"
            bg-color="rgba(255,255,255,0.05)"
            hide-details
            class="glass-input"
          ></v-select>
        </div>
      </div>
    </div>

    <v-row v-if="selectedTaskId">
      <!-- Left: Editor / Artifact Viewer -->
      <v-col cols="12" md="8">
        <v-card class="glass-panel border-neon-glow pa-4 h-100 d-flex flex-column" style="min-height: 500px;">
          <v-card-title class="text-subtitle-1 font-weight-bold d-flex align-center justify-between border-bottom pb-3 text-white">
            <div class="d-flex align-center">
              <v-icon start color="primary">{{ getFileIcon(fileName) }}</v-icon>
              <span>{{ fileName }}</span>
            </div>
            <v-chip size="small" color="primary" variant="tonal">EDITABLE PREVIEW</v-chip>
          </v-card-title>
          
          <v-card-text class="flex-grow-1 pt-4 pa-0 d-flex font-mono">
            <!-- Line Numbers -->
            <div class="line-numbers px-3 py-2 text-right text-grey-darken-1 select-none">
              <div
                v-for="idx in lineCount"
                :key="idx"
                :class="['line-num-item', {'line-num-highlighted': selectedLine === idx}]"
                @click="selectedLine = idx"
              >
                {{ idx }}
              </div>
            </div>
            
            <!-- Code content -->
            <div class="code-editor-body flex-grow-1 py-2 px-4 overflow-x-auto text-body-2 text-white">
              <div
                v-for="(lineText, idx) in codeLines"
                :key="idx"
                :class="[
                  'code-line-item', 
                  {'line-selected': selectedLine === idx + 1},
                  {'line-warn': hasCommentOnLine(idx + 1)}
                ]"
                @click="selectedLine = idx + 1"
              >
                <!-- Warning icon if line has comments -->
                <v-icon
                  v-if="hasCommentOnLine(idx + 1)"
                  size="12"
                  color="warning"
                  class="mr-2"
                >
                  mdi-alert-outline
                </v-icon>
                {{ lineText }}
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Right: Inline Comments -->
      <v-col cols="12" md="4">
        <InlineComments
          :task-id="selectedTaskId"
          :selected-line="selectedLine"
          @apply-fix="handleApplyFix"
        />
      </v-col>
    </v-row>
    <v-row v-else>
      <v-col cols="12" class="text-center py-12">
        <v-icon size="64" color="grey-darken-2" class="mb-4">mdi-file-code-outline</v-icon>
        <div class="text-subtitle-1 text-grey font-weight-bold">成果物を表示するタスクを選択してください</div>
        <p class="text-caption text-grey-darken-1">AIワーカーが実行を完了（REVIEW状態）したタスクのコードやドキュメントがここに表示されます。</p>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useProjectStore } from '../store/project'
import InlineComments from '../components/InlineComments.vue'

const store = useProjectStore()
const selectedTaskId = ref(null)
const selectedLine = ref(null)
const activeArtifact = ref(null)

const tasksWithArtifacts = computed(() => {
  // Only tasks that have subtasks with output_mock_path
  return store.tasks
    .filter(t => t.subtasks && t.subtasks.some(sub => sub.output_mock_path))
    .map(t => ({ id: t.id, title: t.title }))
})

// Mock file details based on selected task
const fileName = computed(() => {
  return activeArtifact.value ? activeArtifact.value.file_name : 'No file'
})

const activeContent = computed(() => {
  return activeArtifact.value ? activeArtifact.value.content : ''
})

const codeLines = computed(() => {
  return activeContent.value ? activeContent.value.split('\n') : []
})

const lineCount = computed(() => {
  return codeLines.value.length
})

const getFileIcon = (name) => {
  if (name.endsWith('.py')) return 'mdi-language-python'
  if (name.endsWith('.md')) return 'mdi-language-markdown'
  if (name.endsWith('.json')) return 'mdi-code-json'
  return 'mdi-file-document-outline'
}

const hasCommentOnLine = (line) => {
  return store.comments.some(c => c.line_number === line)
}

const handleGovernanceAudit = async () => {
  if (!selectedTaskId.value) return
  try {
    await store.runGovernanceAudit(selectedTaskId.value, activeContent.value)
    // Select the first warned line to highlight audit results
    const warnedComment = store.comments.find(c => c.task_id === selectedTaskId.value && c.line_number)
    if (warnedComment) {
      selectedLine.value = warnedComment.line_number
    }
  } catch (e) {
    console.error('Failed to run governance audit:', e)
  }
}

const handleApplyFix = async (line) => {
  try {
    const updated = await store.applyArtifactFix(selectedTaskId.value, line)
    if (updated) {
      activeArtifact.value = updated
    }
    await store.sendMessage('AI_PMO', 'AI_PMO', `インラインレビューに基づき、${fileName.value} の ${line}行目にAI修正案を自動適用しました！`, selectedTaskId.value)
  } catch (err) {
    console.error('Failed to apply fix:', err)
  }
}

watch(
  () => selectedTaskId.value,
  async (newId) => {
    selectedLine.value = null
    activeArtifact.value = null
    if (newId) {
      try {
        const art = await store.fetchTaskArtifact(newId)
        activeArtifact.value = art
      } catch (err) {
        console.warn('No artifacts found on server, using fallback schema', err)
        const t = store.tasks.find(x => x.id === newId)
        let name = 'readme_guide.md'
        let content = ''
        if (t && t.title.includes('API')) {
          name = 'app_api_routes.py'
          content = [
            "from fastapi import APIRouter",
            "import logging",
            "",
            "router = APIRouter()",
            "logger = logging.getLogger(__name__)",
            "",
            "@router.get('/v1/items')",
            "async def get_project_items():",
            "    # バグの恐れ：プロジェクトAの古いデータベース接続スキーマを参照しています",
            "    db_conn = connect_legacy_db()",
            "    return {'items': []}"
          ].join('\n')
        } else {
          name = 'spec_document.md'
          content = [
            "# プロジェクト管理要件定義書",
            "",
            "## 1. 概要",
            "本システムはAIエージェントと人間が協働するための管理プラットフォームである。",
            "",
            "## 2. アーキテクチャ構成",
            "- データベース: PostgreSQL 15 を標準使用します（注：現在の仕様は16）",
            "- ベクトルDB: Qdrant",
            "- フロントエンド: Vue 3 / Vuetify 3"
          ].join('\n')
        }
        activeArtifact.value = {
          file_name: name,
          content: content,
          lines: content.split('\n')
        }
      }
    }
  }
)

onMounted(async () => {
  await store.fetchTasks()
})
</script>

<style scoped>
.font-mono {
  font-family: 'JetBrains Mono', monospace !important;
}
.line-numbers {
  background: rgba(0, 0, 0, 0.2);
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 13px;
  line-height: 22px;
}
.line-num-item {
  cursor: pointer;
  padding: 0 4px;
  min-width: 24px;
}
.line-num-item:hover {
  color: #fff;
}
.line-num-highlighted {
  color: #00f2fe;
  font-weight: bold;
}
.code-editor-body {
  font-size: 13px;
  line-height: 22px;
  white-space: pre;
}
.code-line-item {
  cursor: pointer;
  padding: 0 8px;
  border-radius: 2px;
}
.code-line-item:hover {
  background: rgba(255, 255, 255, 0.03);
}
.line-selected {
  background: rgba(0, 242, 254, 0.08) !important;
}
.line-warn {
  background: rgba(255, 179, 0, 0.08) !important;
  border-left: 2px solid #ffb300;
}
.gap-2 {
  gap: 8px;
}
.gap-3 {
  gap: 12px;
}
.select-none {
  user-select: none;
}
</style>
