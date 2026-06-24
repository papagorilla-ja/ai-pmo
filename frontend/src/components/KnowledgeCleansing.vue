<template>
  <div class="glass-panel border-neon-glow pa-6 text-white">
    <div class="d-flex align-center justify-between mb-6 flex-wrap gap-3">
      <div>
        <h2 class="text-h5 font-weight-bold text-neon-blue d-flex align-center">
          <v-icon start color="primary">mdi-database-eye-outline</v-icon>
          ナレッジ・コントロールパネル (RAG)
        </h2>
        <p class="text-caption text-grey">AIが参照するベクトルDB (Qdrant) 内の記述と、その確定度の管理</p>
      </div>
      <v-spacer></v-spacer>
      <div class="d-flex gap-2">
        <v-btn
          variant="outlined"
          color="primary"
          prepend-icon="mdi-sync"
          :loading="store.loading"
          @click="store.triggerNightlyCrawl"
        >
          夜間同期バッチ手動実行
        </v-btn>
      </div>
    </div>

    <!-- Alert for flagged knowledge -->
    <v-alert
      v-if="flaggedCount > 0"
      type="warning"
      variant="tonal"
      class="mb-6 rounded-lg border-neon-glow"
      icon="mdi-alert-outline"
    >
      現在、適合度（不確定な表現）が低いナレッジが <strong>{{ flaggedCount }}件</strong> 検出されています。
      不要な古い情報や推測データである場合は、クレンジング（削除）を行うことを推奨します。
    </v-alert>

    <!-- Table of registered knowledge -->
    <v-table class="bg-transparent text-white border rounded-lg overflow-hidden glass-card">
      <thead class="bg-black">
        <tr>
          <th class="text-left text-grey text-caption">ソース種別</th>
          <th class="text-left text-grey text-caption">内容（チャンクテキスト）</th>
          <th class="text-left text-grey text-caption" style="width: 120px;">信頼・適合度</th>
          <th class="text-left text-grey text-caption" style="width: 120px;">状態</th>
          <th class="text-right text-grey text-caption" style="width: 140px;">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="store.knowledges.length === 0">
          <td colspan="5" class="text-center py-6 text-grey-darken-1 text-body-2">
            ナレッジベースにデータがありません。夜間同期バッチを実行してください。
          </td>
        </tr>
        <tr
          v-for="k in store.knowledges"
          :key="k.id"
          :class="{'flagged-row': k.status === 'FLAGGED'}"
          style="border-bottom: 1px solid rgba(255,255,255,0.05);"
        >
          <td class="py-3">
            <v-chip size="small" :color="getSourceColor(k.source)" variant="tonal">
              {{ k.source.toUpperCase() }}
            </v-chip>
          </td>
          <td class="py-3 text-body-2 max-width-content">
            {{ k.content }}
          </td>
          <td class="py-3 font-weight-bold" :class="getScoreClass(k.confidence_score)">
            {{ (k.confidence_score * 100).toFixed(0) }}%
          </td>
          <td class="py-3">
            <v-chip size="x-small" :color="k.status === 'FLAGGED' ? 'warning' : 'success'">
              {{ k.status }}
            </v-chip>
          </td>
          <td class="py-3 text-right">
            <v-btn
              icon="mdi-trash-can-outline"
              variant="text"
              color="error"
              size="small"
              title="クレンジング（DBとベクトルDBから物理削除）"
              @click="store.deleteKnowledge(k.id)"
            ></v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useProjectStore } from '../store/project'

const store = useProjectStore()

const flaggedCount = computed(() => {
  return store.knowledges.filter(k => k.status === 'FLAGGED').length
})

const getSourceColor = (source) => {
  if (source === 'task') return 'primary'
  if (source === 'subtask') return 'secondary'
  if (source === 'message') return 'accent'
  return 'grey'
}

const getScoreClass = (score) => {
  if (score >= 0.85) return 'text-success'
  if (score >= 0.7) return 'text-warning'
  return 'text-error'
}

onMounted(() => {
  store.fetchKnowledge()
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
.gap-3 {
  gap: 12px;
}
.max-width-content {
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.flagged-row {
  background: rgba(255, 179, 0, 0.02) !important;
}
.bg-black {
  background-color: rgba(0, 0, 0, 0.4) !important;
}
</style>
