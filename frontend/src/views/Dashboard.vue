<template>
  <v-container fluid class="pa-6">
    <div class="d-flex align-center justify-between mb-6 flex-wrap gap-3">
      <div>
        <h1 class="text-h4 font-weight-bold text-neon-blue">AI-PMO プロジェクトダッシュボード</h1>
        <p class="text-caption text-grey">自律協働型エージェントとの協働ダッシュボード</p>
      </div>
      <v-spacer></v-spacer>
      <div class="d-flex align-center gap-4 flex-wrap">
        <v-switch
          v-model="isExecutiveView"
          label="エグゼクティブ・ビュー"
          color="secondary"
          hide-details
          inset
          density="compact"
          class="mr-4"
          @change="onExecutiveToggle"
        ></v-switch>
        <v-btn
          variant="flat"
          class="bg-neon-gradient text-white font-weight-bold"
          prepend-icon="mdi-calendar-sync"
          @click="openStandup"
        >
          朝会サマリーを開く
        </v-btn>
      </div>
    </div>

    <!-- Executive View Content -->
    <v-row v-if="isExecutiveView" class="mb-6">
      <!-- EVM metrics row -->
      <v-col cols="12" md="6">
        <v-card class="glass-card border-neon-glow pa-6 h-100">
          <v-card-title class="text-subtitle-1 font-weight-bold d-flex align-center pb-4 text-neon-blue">
            <v-icon start color="primary">mdi-chart-timeline-variant</v-icon>
            EVM (Earned Value Management) 指標
          </v-card-title>
          
          <v-row class="mt-2">
            <v-col cols="12" sm="6">
              <div class="d-flex flex-column align-center justify-center pa-4 bg-glass rounded-lg border-subtle">
                <span class="text-caption text-grey mb-2">SPI (スケジュール効率指数)</span>
                <v-progress-circular
                  :model-value="Math.min((store.executiveSummary?.spi || 1.0) * 100, 100)"
                  :size="120"
                  :width="12"
                  :color="(store.executiveSummary?.spi || 1.0) >= 1.0 ? 'success' : 'error'"
                >
                  <span class="text-h5 font-weight-bold text-white">{{ store.executiveSummary?.spi || '1.0' }}</span>
                </v-progress-circular>
                <v-chip
                  :color="(store.executiveSummary?.spi || 1.0) >= 1.0 ? 'success' : 'error'"
                  size="small"
                  class="mt-4 font-weight-bold"
                >
                  {{ (store.executiveSummary?.spi || 1.0) >= 1.0 ? 'オンスケジュール' : 'スケジュール遅延あり' }}
                </v-chip>
              </div>
            </v-col>
            
            <v-col cols="12" sm="6">
              <div class="d-flex flex-column align-center justify-center pa-4 bg-glass rounded-lg border-subtle">
                <span class="text-caption text-grey mb-2">CPI (コスト効率指数)</span>
                <v-progress-circular
                  :model-value="Math.min((store.executiveSummary?.cpi || 1.0) * 100, 100)"
                  :size="120"
                  :width="12"
                  :color="(store.executiveSummary?.cpi || 1.0) >= 1.0 ? 'success' : 'error'"
                >
                  <span class="text-h5 font-weight-bold text-white">{{ store.executiveSummary?.cpi || '1.0' }}</span>
                </v-progress-circular>
                <v-chip
                  :color="(store.executiveSummary?.cpi || 1.0) >= 1.0 ? 'success' : 'error'"
                  size="small"
                  class="mt-4 font-weight-bold"
                >
                  {{ (store.executiveSummary?.cpi || 1.0) >= 1.0 ? '予算内' : '予算超過' }}
                </v-chip>
              </div>
            </v-col>
          </v-row>

          <div class="mt-6 text-caption text-grey">
            ※ SPI/CPIは、プロジェクト全体のWBSタスクの進捗、重みづけ優先度、および実際発生したコストの集計値からリアルタイムに算出されています。
          </div>
        </v-card>
      </v-col>

      <!-- CFO / executive translator report -->
      <v-col cols="12" md="6">
        <v-card class="glass-card border-neon-glow pa-6 h-100">
          <v-card-title class="text-subtitle-1 font-weight-bold d-flex align-center pb-4 text-neon-purple">
            <v-icon start color="secondary">mdi-translate</v-icon>
            AIエグゼクティブ翻訳サマリー (CFO/役員向け報告)
          </v-card-title>
          
          <div v-if="store.loading" class="d-flex justify-center align-center py-12">
            <v-progress-circular indeterminate color="secondary"></v-progress-circular>
          </div>
          
          <div v-else class="text-body-2 text-white white-space-pre-wrap report-box pa-4 rounded-lg bg-glass border-subtle">
            {{ store.executiveSummary?.summary_report }}
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Normal View Content -->
    <div v-else>
      <!-- Quick Stats Row -->
      <v-row class="mb-6">
        <v-col cols="12" sm="6" md="3">
          <v-card class="glass-card pa-4 d-flex align-center gap-3">
            <v-avatar color="rgba(0, 242, 254, 0.1)" size="48" rounded="lg">
              <v-icon color="primary" size="24">mdi-format-list-bulleted</v-icon>
            </v-avatar>
            <div>
              <div class="text-caption text-grey">総タスク数</div>
              <div class="text-h5 font-weight-bold text-white">{{ store.tasks.length }}</div>
            </div>
          </v-card>
        </v-col>

        <v-col cols="12" sm="6" md="3">
          <v-card class="glass-card pa-4 d-flex align-center gap-3">
            <v-avatar color="rgba(0, 230, 118, 0.1)" size="48" rounded="lg">
              <v-icon color="success" size="24">mdi-progress-check</v-icon>
            </v-avatar>
            <div>
              <div class="text-caption text-grey">完了済みタスク</div>
              <div class="text-h5 font-weight-bold text-white">{{ completedTasksCount }}</div>
            </div>
          </v-card>
        </v-col>

        <v-col cols="12" sm="6" md="3">
          <v-card class="glass-card pa-4 d-flex align-center gap-3">
            <v-avatar color="rgba(255, 23, 68, 0.1)" size="48" rounded="lg">
              <v-icon color="error" size="24">mdi-alert-octagon-outline</v-icon>
            </v-avatar>
            <div>
              <div class="text-caption text-grey">遅延中タスク</div>
              <div class="text-h5 font-weight-bold text-error">{{ delayedTasksCount }}</div>
            </div>
          </v-card>
        </v-col>

        <v-col cols="12" sm="6" md="3">
          <v-card class="glass-card pa-4 d-flex align-center gap-3">
            <v-avatar color="rgba(155, 81, 224, 0.1)" size="48" rounded="lg">
              <v-icon color="secondary" size="24">mdi-clock-alert-outline</v-icon>
            </v-avatar>
            <div>
              <div class="text-caption text-grey">承認待ち方針</div>
              <div class="text-h5 font-weight-bold text-neon-purple">{{ pendingApprovalsCount }}</div>
            </div>
          </v-card>
        </v-col>
      </v-row>

      <!-- Content Split: Task Board & AI Activity -->
      <v-row>
        <!-- Task board -->
        <v-col cols="12" md="8">
          <v-card class="glass-panel border-neon-glow pa-4 h-100">
            <v-card-title class="text-subtitle-1 font-weight-bold d-flex align-center pb-4 text-white">
              <v-icon start color="primary">mdi-calendar-check-outline</v-icon>
              タスク進捗状況
            </v-card-title>
            
            <v-table class="bg-transparent text-white">
              <thead>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.08);">
                  <th class="text-left text-grey text-caption">タスク名</th>
                  <th class="text-left text-grey text-caption">担当</th>
                  <th class="text-left text-grey text-caption">ステータス</th>
                  <th class="text-left text-grey text-caption">期限</th>
                  <th class="text-left text-grey text-caption" style="width: 120px;">進捗</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="store.tasks.length === 0">
                  <td colspan="5" class="text-center py-6 text-grey-darken-1 text-body-2">
                    タスクがありません。
                  </td>
                </tr>
                <tr
                  v-for="t in store.tasks"
                  :key="t.id"
                  style="border-bottom: 1px solid rgba(255,255,255,0.05);"
                >
                  <td class="py-3 text-body-2 font-weight-bold">
                    {{ t.title }}
                    <v-chip v-if="t.delay_days > 0" size="x-small" color="error" class="ml-2">遅延 {{ t.delay_days }}日</v-chip>
                  </td>
                  <td class="py-3">
                    <v-chip size="small" :color="t.assignee_type === 'AI' ? 'primary' : 'grey'" variant="outlined">
                      <v-icon start size="12" v-if="t.assignee_type === 'AI'">mdi-robot</v-icon>
                      {{ t.assignee_name || '未アサイン' }}
                    </v-chip>
                  </td>
                  <td class="py-3">
                    <v-chip size="small" :color="getStatusColor(t.status)">
                      {{ t.status }}
                    </v-chip>
                  </td>
                  <td class="py-3 text-caption text-grey">
                    {{ formatDate(t.planned_end) }}
                  </td>
                  <td class="py-3">
                    <div class="d-flex align-center gap-2">
                      <v-progress-linear
                        v-model="t.progress"
                        color="primary"
                        height="6"
                        rounded
                        class="flex-grow-1"
                      ></v-progress-linear>
                      <span class="text-caption font-weight-bold">{{ t.progress }}%</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-col>

        <!-- Right: AI Activity Feed -->
        <v-col cols="12" md="4">
          <v-card class="glass-panel border-neon-glow pa-4 h-100">
            <v-card-title class="text-subtitle-1 font-weight-bold d-flex align-center pb-4 text-neon-purple">
              <v-icon start color="secondary">mdi-rss-box</v-icon>
              AIワーカーアクティビティ
            </v-card-title>

            <div v-if="!recentSubtasks.length" class="text-center py-6 text-caption text-grey-darken-1">
              最近のAIアクティビティはありません。
            </div>
            <v-timeline side="end" align="start" density="compact">
              <v-timeline-item
                v-for="sub in recentSubtasks"
                :key="sub.subtask_id"
                dot-color="primary"
                size="x-small"
              >
                <div>
                  <div class="text-body-2 font-weight-bold text-white">{{ sub.subtask_title }}</div>
                  <div class="text-caption text-grey mb-1">{{ sub.parent_task_title }}</div>
                  <v-chip size="x-small" color="success">完了 (REVIEW)</v-chip>
                </div>
              </v-timeline-item>
            </v-timeline>
          </v-card>
        </v-col>
      </v-row>
    </div>

    <!-- Daily Standup Popup component -->
    <DailyStandup ref="standupPopup" />
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useProjectStore } from '../store/project'
import DailyStandup from '../components/DailyStandup.vue'

const store = useProjectStore()
const standupPopup = ref(null)
const isExecutiveView = ref(false)

const completedTasksCount = computed(() => {
  return store.tasks.filter(t => t.status === 'DONE').length
})

const delayedTasksCount = computed(() => {
  return store.tasks.filter(t => t.delay_days > 0).length
})

const pendingApprovalsCount = computed(() => {
  return store.standupSummary.top_actions.filter(a => a.type === 'APPROVE_PLAN').length
})

const recentSubtasks = computed(() => {
  return store.standupSummary.ai_completed_summary.slice(0, 5)
})

const openStandup = () => {
  if (standupPopup.value) {
    standupPopup.value.open()
  }
}

const onExecutiveToggle = async () => {
  if (isExecutiveView.value) {
    await store.fetchExecutiveSummary()
  }
}

const getStatusColor = (status) => {
  if (status === 'TODO') return 'grey'
  if (status === 'IN_PROGRESS') return 'primary'
  if (status === 'REVIEW') return 'warning'
  if (status === 'DONE') return 'success'
  return 'grey'
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return dateStr.split('T')[0]
}

onMounted(async () => {
  await store.fetchTasks()
  await store.fetchStandupSummary()
  // Trigger open standup on initial load to wow user
  setTimeout(() => {
    openStandup()
  }, 500)
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
.gap-3 {
  gap: 12px;
}
.gap-4 {
  gap: 16px;
}
.bg-glass {
  background: rgba(255, 255, 255, 0.03);
}
.border-subtle {
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.white-space-pre-wrap {
  white-space: pre-wrap;
}
.report-box {
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
}
</style>
