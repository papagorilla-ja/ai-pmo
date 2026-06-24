<template>
  <div class="wbs-gantt-panel glass-card pa-4">
    <!-- Legend Card -->
    <v-card class="glass-card pa-3 mb-4 d-flex align-center justify-space-between flex-wrap gap-4" style="background: rgba(255, 255, 255, 0.02) !important;">
      <div class="d-flex align-center flex-wrap gap-3">
        <span class="text-caption text-grey mr-2 font-weight-bold">WBS表示凡例:</span>
        <div class="d-flex align-center gap-1"><v-badge inline dot color="#0088ff" class="mr-1"></v-badge><span class="text-caption text-white">未開始</span></div>
        <div class="d-flex align-center gap-1"><v-badge inline dot color="#ff9800" class="mr-1"></v-badge><span class="text-caption text-white">対応中/レビュー</span></div>
        <div class="d-flex align-center gap-1"><v-badge inline dot color="#4caf50" class="mr-1"></v-badge><span class="text-caption text-white">完了</span></div>
        <div class="d-flex align-center gap-1"><v-badge inline dot color="#ff3366" class="mr-1"></v-badge><span class="text-caption font-weight-bold text-red">遅延</span></div>
        <div class="d-flex align-center gap-1"><v-badge inline dot color="#9c27b0" class="mr-1"></v-badge><span class="text-caption text-white">サマリー(Phase/Feature)</span></div>
      </div>
      <div class="text-caption text-grey"><v-icon size="14" class="mr-1">mdi-information-outline</v-icon>バーをドラッグして変更・保存できます。子を持つ親バーは子の範囲に自動追従します。</div>
    </v-card>

    <div class="gantt-wrapper">
      <GanttChart
        :tasks="ganttTasks"
        :enable-parent-task-auto-schedule="true"
        :expand-all="true"
        locale="en-US"
        :locale-messages="jaMessages"
        :row-height="44"
        @task-click="onTaskClick"
        @taskbar-drag-end="onBarChange"
        @taskbar-resize-end="onBarChange"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { GanttChart } from 'jordium-gantt-vue3'
import 'jordium-gantt-vue3/dist/assets/jordium-gantt-vue3.css'
import { useProjectStore } from '../store/project'
import dayjs from 'dayjs'

const props = defineProps({ isPortfolio: { type: Boolean, default: false } })
const emit = defineEmits(['task-click'])
const store = useProjectStore()

// Japanese localization (Jordium has no built-in 'ja'). localeMessages must be
// keyed by locale name; we override the active 'en-US' locale with Japanese.
const jaMessages = {
  'en-US': {
  dateNotSet: '未設定',
  // TaskList header
  taskName: 'タスク名', resourceName: 'リソース名', predecessor: '先行タスク', assignee: '担当者',
  startDate: '開始日', endDate: '終了日',
  plannedStartDate: '計画開始日', plannedEndDate: '計画終了日',
  actualStartDate: '実績開始日', actualEndDate: '実績終了日',
  childrenEarliestStart: '子の最早開始', childrenLatestEnd: '子の最遅終了',
  childrenOverflow: '子が親の範囲を超えています',
  estimatedHours: '見積(h)', actualHours: '実績(h)', progress: '進捗', type: '種別',
  // dates
  yearMonthFormat: (y, m) => `${y}年${m}月`,
  monthFormat: (m) => `${m}月`,
  monthNames: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
  weekDays: ['日', '月', '火', '水', '木', '金', '土'],
  // misc / badges
  milestone: 'マイルストーン', today: '本日', targetDate: '目標日',
  overtime: '超過', overdue: '遅延', days: '日',
  // status
  statusPending: '未開始', statusOngoing: '対応中', statusDelayed: '遅延', statusCompleted: '完了',
  // toolbar
  addTask: 'タスク追加', addMilestone: 'マイルストーン追加',
  todayLocate: '本日', todayLocateTooltip: '本日へ移動',
  exportCsv: 'CSV出力', exportPdf: 'PDF出力',
  expandAll: '展開', collapseAll: '折りたたみ',
  taskView: 'タスク', language: '日本語', languageTooltip: '言語を選択',
  resourceView: { desc: 'リソース', capacity: '利用率', overloaded: '過負荷', duration: '期間', overloadWarning: 'リソース過負荷警告', conflictDuration: '競合期間', conflictWith: 'と', conflictSuffix: '競合' },
  lightMode: 'ライトモード', darkMode: 'ダークモード',
  fullscreen: '全画面', exitFullscreen: '全画面解除',
  collapseTaskList: 'タスク一覧を閉じる', expandTaskList: 'タスク一覧を開く',
  // time scale
  timeScaleHour: '時', timeScaleDay: '日', timeScaleWeek: '週', timeScaleMonth: '月',
  timeScaleQuarter: '四半期', timeScaleYear: '年', timeScaleTooltip: '時間スケール切替',
  halfYearFirst: '上半期', halfYearSecond: '下半期',
  // dialogs / buttons
  save: '保存', close: '閉じる', confirm: 'OK', cancel: 'キャンセル', create: '作成', update: '更新',
  delete: '削除', edit: '編集', confirmDelete: 'このマイルストーンを削除しますか？',
  description: '説明', hours: '工数',
  // task drawer
  editTask: 'タスク編集', newTask: 'タスク新規作成', parentTask: '親タスク', noParentTask: '親タスクなし',
  taskType: 'タスク種別', taskTypeRequired: 'タスク種別を選択してください',
  taskTypeMap: { task: 'タスク', milestone: 'マイルストーン', story: 'ストーリー', epic: 'エピック', bug: 'バグ' },
  taskNamePlaceholder: 'タスク名を入力', assigneePlaceholder: '担当者を入力',
  progressPlaceholder: '0-100', hoursPlaceholder: '工数', descriptionPlaceholder: 'タスクの説明を入力...',
  taskNameRequired: 'タスク名は必須です', startDateRequired: '開始日は必須です',
  endDateRequired: '終了日は必須です', endDateInvalid: '終了日は開始日より前にできません',
  taskNameTooLong: 'タスク名は50文字以内にしてください',
  // predecessor / links
  predecessorPlaceholder: '先行タスクを選択', selectPredecessor: '先行タスクを選択',
  removePredecessor: '先行タスクを解除', addPredecessor: '先行タスクを追加', addSuccessor: '後続タスクを追加',
  deleteLinks: '依存関係を削除', noLinks: '依存関係なし',
  // milestone dialog
  milestoneDetails: 'マイルストーン詳細', milestoneName: 'マイルストーン名', milestoneDate: 'マイルストーン日付',
  milestoneIcon: 'アイコン', diamond: 'ダイヤ', rocket: 'ロケット',
  newMilestone: 'マイルストーン新規作成', editMilestone: 'マイルストーン編集',
  enterMilestoneName: 'マイルストーン名を入力', enterAssignee: '担当者を入力', enterDescription: '説明を入力',
  milestoneNameRequired: 'マイルストーン名は必須です', milestoneDateRequired: 'マイルストーン日付は必須です',
  // date/time picker
  selectDate: '日付を選択', to: '〜', time: '時刻', selectTime: '時刻を選択', hour: '時', minute: '分',
  // pdf
  pdfExportLoading: 'PDFを生成中です...', pdfExportTitle: 'ガントチャート出力', pdfExportDate: '出力日'
  }
}

const fmt = (d) => (d ? dayjs(d).format('YYYY-MM-DD') : dayjs().format('YYYY-MM-DD'))

const depsOf = (n) => (n.dependencies || []).map((d) => String(typeof d === 'string' ? d : d.id))

// Map a backend WBS node (with nested .children) to a Jordium task (recursive).
const mapNode = (n) => {
  const task = {
    id: String(n.id),
    name: n.title,
    startDate: fmt(n.planned_start),
    endDate: fmt(n.planned_end),
    progress: n.progress || 0,
    assignee: n.assignee_name || '',
    predecessor: depsOf(n)
  }
  if (n.children && n.children.length > 0) {
    task.children = n.children.map(mapNode)
    task.collapsed = false
  }
  return task
}

const ganttTasks = computed(() => {
  if (props.isPortfolio) {
    return (store.portfolioProjects || []).map((p) => {
      const ts = p.tasks || []
      const starts = ts.map((t) => new Date(t.planned_start).getTime()).filter((x) => !isNaN(x))
      const ends = ts.map((t) => new Date(t.planned_end).getTime()).filter((x) => !isNaN(x))
      return {
        id: String(p.id),
        name: p.name,
        startDate: fmt(starts.length ? new Date(Math.min(...starts)) : new Date()),
        endDate: fmt(ends.length ? new Date(Math.max(...ends)) : new Date()),
        progress: 0,
        collapsed: false,
        children: ts.map((t) => ({
          id: String(t.id),
          name: t.title,
          startDate: fmt(t.planned_start),
          endDate: fmt(t.planned_end),
          progress: t.progress || 0,
          assignee: t.assignee_name || '',
          predecessor: depsOf(t)
        }))
      }
    })
  }
  return (store.projectWbsTree || []).map(mapNode)
})

const onTaskClick = (task) => {
  if (task && task.id) emit('task-click', String(task.id))
}

const onBarChange = (task) => {
  if (!task || !task.id) return
  try {
    store.updateTaskDates(String(task.id), new Date(task.startDate), new Date(task.endDate), false)
  } catch (e) { /* ignore */ }
}
</script>

<style>
.gantt-wrapper {
  height: calc(100vh - 230px);
  min-height: 460px;
  background: rgba(255, 255, 255, 0.01);
  border-radius: 8px;
  overflow: hidden;
}
.gap-2 { gap: 8px; } .gap-3 { gap: 12px; } .gap-4 { gap: 16px; }

/* Jordium toolbar: let button groups size to their (Japanese) content so labels
   are not clipped by the default fixed-width / overflow:hidden groups. */
.wbs-gantt-panel .gantt-toolbar .gantt-btn-group {
  overflow: visible !important;
  width: auto !important;
  max-width: none !important;
  flex: 0 0 auto !important;
}
.wbs-gantt-panel .gantt-toolbar .gantt-btn-group-item {
  white-space: nowrap !important;
}
</style>
