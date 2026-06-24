<template>
  <v-dialog v-model="visible" max-width="800px" content-class="glass-panel border-neon-glow" persistent>
    <v-card class="bg-transparent text-white border-0 pa-6" style="backdrop-filter: blur(20px);">
      <v-card-title class="d-flex justify-between align-center border-bottom pb-3">
        <div class="d-flex align-center">
          <v-avatar size="32" class="bg-neon-gradient mr-3">
            <v-icon size="18" color="white">mdi-calendar-sync</v-icon>
          </v-avatar>
          <div>
            <div class="text-h6 font-weight-bold text-neon-blue">朝会 (Daily Standup) サマリー</div>
            <div class="text-caption text-grey">昨夜のAI成果の要約と、本日必要な判断事項</div>
          </div>
        </div>
        <v-spacer></v-spacer>
        <v-btn icon="mdi-close" variant="text" size="small" color="white" @click="close"></v-btn>
      </v-card-title>

      <v-card-text class="pt-6">
        <v-row>
          <!-- Left: AI completed tasks -->
          <v-col cols="12" md="6" class="pr-md-4">
            <div class="d-flex align-center mb-4">
              <v-icon color="success" class="mr-2">mdi-check-circle-outline</v-icon>
              <span class="text-subtitle-1 font-weight-bold">昨夜のAIワーカー稼働実績</span>
            </div>
            
            <v-list class="bg-transparent pa-0">
              <div v-if="!store.standupSummary.ai_completed_summary.length" class="text-body-2 text-grey-darken-1 py-4">
                昨夜稼働したAIサブタスクはありません。
              </div>
              <v-list-item
                v-for="sub in store.standupSummary.ai_completed_summary"
                :key="sub.subtask_id"
                class="glass-card mb-3 pa-3"
              >
                <div class="d-flex align-center justify-between">
                  <div>
                    <div class="text-body-2 font-weight-bold text-white">{{ sub.subtask_title }}</div>
                    <div class="text-caption text-grey">{{ sub.parent_task_title }}</div>
                  </div>
                  <v-chip size="x-small" color="success" class="ml-2">REVIEW</v-chip>
                </div>
              </v-list-item>
            </v-list>
          </v-col>

          <!-- Right: Top 3 Human approvals -->
          <v-col cols="12" md="6" class="pl-md-4 border-left-md">
            <div class="d-flex align-center mb-4">
              <v-icon color="secondary" class="mr-2">mdi-lightning-bolt-outline</v-icon>
              <span class="text-subtitle-1 font-weight-bold text-neon-purple">本日の最優先確認・判断事項 (Top 3)</span>
            </div>

            <div v-if="!store.standupSummary.top_actions.length" class="text-body-2 text-grey-darken-1 py-4">
              本日必要な判断事項はありません。順調です！
            </div>
            <div
              v-for="action in store.standupSummary.top_actions"
              :key="action.target_id"
              class="glass-card border-neon-glow mb-4 pa-4"
            >
              <div class="d-flex align-start mb-2">
                <v-icon :color="getActionColor(action.type)" class="mr-2 mt-1">{{ getActionIcon(action.type) }}</v-icon>
                <div>
                  <div class="text-body-2 font-weight-bold text-white">{{ action.title }}</div>
                  <div class="text-caption text-grey-lighten-1">{{ action.description }}</div>
                </div>
              </div>
              
              <!-- Action Buttons -->
              <div class="d-flex justify-end gap-2 mt-3">
                <template v-if="action.type === 'APPROVE_PLAN'">
                  <v-btn size="x-small" color="grey" variant="text" @click="handleRejectPlan(action.target_id)">拒否</v-btn>
                  <v-btn size="x-small" variant="flat" class="bg-neon-gradient text-white" @click="handleApprovePlan(action.target_id)">GO (実行)</v-btn>
                </template>
                <template v-else-if="action.type === 'REVIEW_TASK'">
                  <v-btn size="x-small" color="primary" variant="outlined" @click="navigateToArtifacts">成果物を確認</v-btn>
                </template>
                <template v-else-if="action.type === 'HEARING_LATE'">
                  <v-btn size="x-small" color="warning" variant="outlined" @click="navigateToGantt">ヒアリングへ回答</v-btn>
                </template>
              </div>
            </div>
          </v-col>
        </v-row>
      </v-card-text>

      <v-card-actions class="d-flex justify-end pt-4">
        <v-btn variant="text" color="grey" @click="close">閉じる</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '../store/project'

const store = useProjectStore()
const router = useRouter()
const visible = ref(false)

const open = async () => {
  await store.fetchStandupSummary()
  visible.value = true
}

const close = () => {
  visible.value = false
}

const handleApprovePlan = async (taskId) => {
  await store.approvePlan(taskId)
  await store.fetchStandupSummary()
}

const handleRejectPlan = async (taskId) => {
  await store.rejectPlan(taskId)
  await store.fetchStandupSummary()
}

const navigateToArtifacts = () => {
  close()
  router.push('/artifacts')
}

const navigateToGantt = () => {
  close()
  router.push('/gantt')
}

const getActionColor = (type) => {
  if (type === 'APPROVE_PLAN') return 'primary'
  if (type === 'REVIEW_TASK') return 'success'
  if (type === 'HEARING_LATE') return 'warning'
  return 'grey'
}

const getActionIcon = (type) => {
  if (type === 'APPROVE_PLAN') return 'mdi-file-document-edit-outline'
  if (type === 'REVIEW_TASK') return 'mdi-file-code-outline'
  if (type === 'HEARING_LATE') return 'mdi-alert-circle-outline'
  return 'mdi-checkbox-blank-circle-outline'
}

defineExpose({ open })
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
@media (min-width: 960px) {
  .border-left-md {
    border-left: 1px solid rgba(255, 255, 255, 0.08);
  }
}
</style>
