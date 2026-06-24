<template>
  <v-container fluid class="pa-6 text-white">
    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-6">
      <div>
        <h1 class="text-h4 font-weight-bold text-neon-blue d-flex align-center">
          <v-icon class="mr-2" color="primary">mdi-cog-outline</v-icon>
          システム管理 (Master Admin)
        </h1>
        <p class="text-subtitle-2 text-grey">
          リソース情報（ユーザー）、スキルセット、および稼働カレンダー・休日の管理を行います。
        </p>
      </div>
      <!-- Active User Badge -->
      <v-chip color="primary" class="border-neon-glow px-4" variant="outlined">
        <v-icon start size="16">mdi-account-circle-outline</v-icon>
        現在の操作ロール: <strong>{{ store.currentRole }}</strong>
      </v-chip>
    </div>

    <!-- Tabs -->
    <v-tabs v-model="activeTab" bg-color="rgba(255, 255, 255, 0.02)" class="rounded-lg mb-6" theme="dark" slider-color="primary">
      <v-tab value="resources" class="font-weight-bold">
        <v-icon start>mdi-account-group-outline</v-icon>
        リソース・ユーザー管理
      </v-tab>
      <v-tab value="calendar" class="font-weight-bold">
        <v-icon start>mdi-calendar-month-outline</v-icon>
        カレンダー・祝日管理
      </v-tab>
    </v-tabs>

    <!-- Tab Contents -->
    <v-window v-model="activeTab">
      <!-- 1. Resource Master Tab -->
      <v-window-item value="resources">
        <v-row>
          <!-- NLP AI Search panel (Left side) -->
          <v-col cols="12" lg="4">
            <v-card class="glass-panel border-neon-glow pa-4 mb-6" style="background: rgba(13,17,23,0.6) !important;">
              <h3 class="text-subtitle-1 font-weight-bold text-neon-purple mb-2 d-flex align-center">
                <v-icon start color="secondary">mdi-magnify-expand</v-icon>
                AIリソース推薦 (NLP検索)
              </h3>
              <p class="text-caption text-grey mb-4">
                「JavaScriptの開発ができる人」や「アプリ設計の経験者」など、自然言語で最適な人員を検索・推薦します。
              </p>
              
              <v-text-field
                v-model="nlpQuery"
                label="検索クエリを入力..."
                variant="outlined"
                density="comfortable"
                hide-details
                append-inner-icon="mdi-arrow-right-bold-circle"
                @click:append-inner="runNlpSearch"
                @keyup.enter="runNlpSearch"
                class="mb-3 rounded-lg"
              ></v-text-field>

              <v-btn
                block
                color="secondary"
                variant="outlined"
                class="rounded-lg mb-4"
                :loading="nlpSearching"
                @click="runNlpSearch"
              >
                AIリソース選定を実行
              </v-btn>

              <!-- NLP Results -->
              <div v-if="nlpResults.length > 0" class="nlp-results-container">
                <div class="text-caption font-weight-bold text-neon-blue mb-2">AIによる推薦結果 ({{ nlpResults.length }}名)</div>
                <div
                  v-for="res in nlpResults"
                  :key="res.id"
                  class="glass-card mb-3 pa-3 rounded-lg border-neon-glow"
                  style="background: rgba(155, 81, 224, 0.05) !important;"
                >
                  <div class="d-flex justify-space-between align-center mb-1">
                    <span class="font-weight-bold text-white">{{ res.name }}</span>
                    <v-chip size="x-small" color="secondary">{{ res.role }}</v-chip>
                  </div>
                  <div class="text-caption text-grey mb-2">{{ res.department || '所属なし' }}</div>
                  <div class="text-caption bg-rgba-white-05 pa-2 rounded text-grey-lighten-2 border-left-purple">
                    <v-icon size="12" color="secondary" class="mr-1">mdi-robot-outline</v-icon>
                    <strong>選定理由:</strong> {{ res.matching_reason }}
                  </div>
                </div>
              </div>
              <div v-else-if="nlpSearched && nlpResults.length === 0" class="text-center text-caption text-grey py-6">
                該当するリソースは見つかりませんでした。
              </div>
            </v-card>
          </v-col>

          <!-- Resource List (Right side) -->
          <v-col cols="12" lg="8">
            <v-card class="glass-panel border-neon-glow pa-4" style="background: rgba(13,17,23,0.6) !important;">
              <div class="d-flex justify-space-between align-center mb-4">
                <div class="text-subtitle-1 font-weight-bold text-neon-blue d-flex align-center">
                  <v-icon start>mdi-format-list-bulleted</v-icon>
                  リソース一覧
                </div>
                <v-btn
                  color="primary"
                  prepend-icon="mdi-plus"
                  class="rounded-lg bg-neon-gradient text-white"
                  :disabled="!canCreateResource"
                  @click="openResourceDialog()"
                >
                  新規リソース追加
                </v-btn>
              </div>

              <!-- Main Resources Table -->
              <v-table class="bg-transparent text-white custom-admin-table" theme="dark">
                <thead>
                  <tr>
                    <th>氏名 / 部署</th>
                    <th>役割</th>
                    <th>システム権限</th>
                    <th>基本稼働時間</th>
                    <th>時間単価 (JPY)</th>
                    <th>有効</th>
                    <th class="text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="res in store.resourcesList" :key="res.id" :class="{ 'admin-non-assignable': res.system_role === '管理者' }">
                    <td>
                      <div class="font-weight-bold text-white d-flex align-center">
                        {{ res.name }}
                        <v-chip v-if="res.system_role === '管理者'" size="x-small" color="error" variant="flat" class="ml-2">アサイン対象外</v-chip>
                      </div>
                      <div class="text-caption text-grey">{{ res.department }}</div>
                    </td>
                    <td>
                      <v-chip size="small" variant="flat" color="rgba(255, 255, 255, 0.1)">{{ res.role }}</v-chip>
                    </td>
                    <td>
                      <v-chip
                        size="small"
                        :color="getSystemRoleColor(res.system_role)"
                        variant="tonal"
                      >
                        {{ res.system_role }}
                      </v-chip>
                    </td>
                    <td>
                      <div class="text-body-2">{{ res.daily_working_hours }}h</div>
                      <div class="text-caption text-grey">{{ res.start_time }}-{{ res.end_time }} (休{{ res.break_hours }}h)</div>
                    </td>
                    <td>
                      <span v-if="store.currentRole === 'メンバー'" class="text-grey text-caption">*** JPY (非表示)</span>
                      <span v-else class="font-weight-bold text-neon-blue">
                        ¥{{ res.hourly_cost_jpy?.toLocaleString() }} / h
                      </span>
                    </td>
                    <td>
                      <!-- Login status switcher (restricted to Admin) -->
                      <v-switch
                        :model-value="res.is_active"
                        density="compact"
                        color="success"
                        hide-details
                        :disabled="!canToggleStatus"
                        @update:model-value="toggleResourceActive(res)"
                      ></v-switch>
                    </td>
                    <td class="text-right">
                      <div class="d-flex justify-end gap-2">
                        <!-- Edit Button -->
                        <v-btn
                          icon="mdi-pencil-outline"
                          size="x-small"
                          color="info"
                          variant="text"
                          :disabled="!canEditResource"
                          @click="openResourceDialog(res)"
                        ></v-btn>
                        <!-- Delete Button -->
                        <v-btn
                          icon="mdi-trash-can-outline"
                          size="x-small"
                          color="error"
                          variant="text"
                          :disabled="!canDeleteResource"
                          @click="confirmDeleteResource(res)"
                        ></v-btn>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="store.resourcesList.length === 0">
                    <td colspan="7" class="text-center text-grey py-8">
                      リソースが登録されていません。
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <!-- 2. Calendar Master Tab -->
      <v-window-item value="calendar">
        <v-row>
          <!-- Left side: AI public holidays auto setting -->
          <v-col cols="12" lg="4">
            <v-card class="glass-panel border-neon-glow pa-4 mb-6" style="background: rgba(13,17,23,0.6) !important;">
              <h3 class="text-subtitle-1 font-weight-bold text-neon-purple mb-2 d-flex align-center">
                <v-icon start color="secondary">mdi-robot-outline</v-icon>
                AI祝祭日自動同期
              </h3>
              <p class="text-caption text-grey mb-4">
                指定年の日本の国民の祝日を、AIを用いて自動生成し一括インポートします。
              </p>

              <v-text-field
                v-model.number="syncYear"
                label="対象年 (西暦)"
                type="number"
                variant="outlined"
                density="comfortable"
                class="mb-3"
              ></v-text-field>

              <v-btn
                block
                color="secondary"
                class="rounded-lg bg-neon-gradient text-white"
                :loading="syncLoading"
                :disabled="!canManageCalendar"
                @click="runCalendarSync"
              >
                AIで祝祭日を自動設定
              </v-btn>
              
              <div v-if="!canManageCalendar" class="text-caption text-error mt-2 text-center">
                ※祝日の同期・変更には管理者またはマネージャ権限が必要です。
              </div>
            </v-card>
          </v-col>

          <!-- Right side: Holidays table -->
          <v-col cols="12" lg="8">
            <v-card class="glass-panel border-neon-glow pa-4" style="background: rgba(13,17,23,0.6) !important;">
              <div class="d-flex justify-space-between align-center mb-4">
                <div class="text-subtitle-1 font-weight-bold text-neon-blue d-flex align-center">
                  <v-icon start>mdi-calendar-heart</v-icon>
                  祝祭日・休日一覧
                </div>
                <div class="d-flex gap-3 align-center">
                  <v-select
                    v-model="filterYear"
                    :items="[2025, 2026, 2027]"
                    label="表示年度"
                    density="compact"
                    variant="outlined"
                    hide-details
                    style="width: 120px;"
                    @update:model-value="onFilterYearChange"
                  ></v-select>
                  
                  <v-btn
                    color="primary"
                    prepend-icon="mdi-plus"
                    class="rounded-lg"
                    variant="outlined"
                    :disabled="!canManageCalendar"
                    @click="openHolidayDialog()"
                  >
                    休日を手動追加
                  </v-btn>
                </div>
              </div>

              <!-- Holidays Table -->
              <v-table class="bg-transparent text-white custom-admin-table" theme="dark">
                <thead>
                  <tr>
                    <th>日付</th>
                    <th>休日名</th>
                    <th>種類</th>
                    <th class="text-right" v-if="canManageCalendar">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="holiday in store.calendarHolidays" :key="holiday.id">
                    <td class="font-weight-bold text-white">{{ holiday.date }}</td>
                    <td>{{ holiday.name }}</td>
                    <td>
                      <v-chip
                        size="small"
                        :color="holiday.is_company_holiday ? 'warning' : 'primary'"
                        variant="tonal"
                      >
                        {{ holiday.is_company_holiday ? '企業休日' : '国民の祝日' }}
                      </v-chip>
                    </td>
                    <td class="text-right" v-if="canManageCalendar">
                      <div class="d-flex justify-end gap-2">
                        <v-btn
                          icon="mdi-pencil-outline"
                          size="x-small"
                          color="info"
                          variant="text"
                          @click="openHolidayDialog(holiday)"
                        ></v-btn>
                        <v-btn
                          icon="mdi-trash-can-outline"
                          size="x-small"
                          color="error"
                          variant="text"
                          @click="confirmDeleteHoliday(holiday)"
                        ></v-btn>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="store.calendarHolidays.length === 0">
                    <td colspan="4" class="text-center text-grey py-8">
                      選択された年度の休日が登録されていません。
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>
    </v-window>

    <!-- Resource Edit/Add Dialog -->
    <v-dialog v-model="resourceDialog" max-width="700px" content-class="glass-panel border-neon-glow" persistent>
      <v-card class="bg-transparent text-white border-0 pa-6" style="backdrop-filter: blur(20px);">
        <v-card-title class="border-bottom pb-3 pl-0">
          <span class="text-h6 font-weight-bold text-neon-blue">
            {{ isEditingResource ? 'リソース情報の編集' : '新規リソースの登録' }}
          </span>
        </v-card-title>

        <v-card-text class="pt-6 px-0 overflow-y-auto" style="max-height: 65vh;">
          <v-form ref="resourceForm">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editedResource.name"
                  label="氏名 *"
                  required
                  variant="outlined"
                  density="comfortable"
                  :disabled="isEditingResource"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editedResource.email"
                  label="メールアドレス *"
                  required
                  variant="outlined"
                  density="comfortable"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editedResource.password"
                  label="パスワード"
                  placeholder="新規設定または変更時のみ入力"
                  type="password"
                  variant="outlined"
                  density="comfortable"
                  :disabled="!canEditPassword"
                  :required="!isEditingResource"
                ></v-text-field>
              </v-col>
              
              <v-col cols="12" md="6">
                <v-select
                  v-model="editedResource.role"
                  :items="['PG', 'SE', 'PM', 'SV', 'AI Agent']"
                  label="役割 (PMO内・開発職種) *"
                  required
                  variant="outlined"
                  density="comfortable"
                ></v-select>
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="editedResource.system_role"
                  :items="['管理者', 'マネージャ', 'メンバー']"
                  label="システム権限 *"
                  required
                  variant="outlined"
                  density="comfortable"
                  :disabled="store.currentRole !== '管理者'"
                ></v-select>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editedResource.department"
                  label="所属部署・チーム"
                  variant="outlined"
                  density="comfortable"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="editedResource.hourly_cost_jpy"
                  label="時間単価 (時給、円単位) *"
                  type="number"
                  required
                  variant="outlined"
                  density="comfortable"
                  :disabled="store.currentRole === 'メンバー'"
                ></v-text-field>
              </v-col>

              <!-- Shift working hours and auto calculation -->
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="editedResource.start_time"
                  label="基本始業時間 (HH:MM)"
                  placeholder="09:00"
                  variant="outlined"
                  density="comfortable"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="editedResource.end_time"
                  label="基本終業時間 (HH:MM)"
                  placeholder="17:45"
                  variant="outlined"
                  density="comfortable"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="editedResource.break_hours"
                  label="休憩時間数 (h)"
                  type="number"
                  step="0.25"
                  variant="outlined"
                  density="comfortable"
                ></v-text-field>
              </v-col>

              <!-- Calculated Working Hours Alert Box -->
              <v-col cols="12">
                <div class="d-flex align-center justify-space-between bg-rgba-white-05 pa-3 rounded-lg border-neon-blue">
                  <div class="text-caption text-grey d-flex align-center">
                    <v-icon start size="16" color="primary">mdi-clock-outline</v-icon>
                    基本入力から自動算出された1日あたりの稼働時間
                  </div>
                  <div class="text-h6 font-weight-bold text-neon-blue">
                    {{ calculatedDailyHours }} 時間
                  </div>
                </div>
              </v-col>

              <!-- Allocation limits & dates -->
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="editedResource.allocation_limit"
                  label="アサイン上限 (%)"
                  type="number"
                  variant="outlined"
                  density="comfortable"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="editedResource.available_from"
                  label="稼働可能開始日 (YYYY-MM-DD)"
                  placeholder="2026-01-01"
                  variant="outlined"
                  density="comfortable"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="editedResource.available_to"
                  label="稼働可能終了日 (YYYY-MM-DD)"
                  placeholder="2026-12-31"
                  variant="outlined"
                  density="comfortable"
                ></v-text-field>
              </v-col>

              <!-- Working Days of the Week checkboxes -->
              <v-col cols="12">
                <div class="text-body-2 mb-2 font-weight-bold">稼働可能曜日</div>
                <div class="d-flex flex-wrap gap-2">
                  <v-checkbox
                    v-for="day in ['月', '火', '水', '木', '金', '土', '日']"
                    :key="day"
                    v-model="editedResource.working_days"
                    :label="day"
                    :value="day"
                    hide-details
                    density="compact"
                    inline
                  ></v-checkbox>
                </div>
              </v-col>

              <!-- Checkbox lists for Phase/Domain skills -->
              <v-col cols="12" md="6">
                <div class="text-body-2 mb-2 font-weight-bold">対応可能フェーズ</div>
                <v-row no-gutters>
                  <v-col cols="6" v-for="phase in ['企画', '要件定義', '設計', '実装', 'テスト', '運用']" :key="phase">
                    <v-checkbox
                      v-model="editedResource.skills_phase"
                      :label="phase"
                      :value="phase"
                      hide-details
                      density="compact"
                    ></v-checkbox>
                  </v-col>
                </v-row>
              </v-col>
              
              <v-col cols="12" md="6">
                <div class="text-body-2 mb-2 font-weight-bold">対応可能領域</div>
                <v-row no-gutters>
                  <v-col cols="12" v-for="domain in ['アプリ領域', 'インフラ領域', 'ユーザサポート領域']" :key="domain">
                    <v-checkbox
                      v-model="editedResource.skills_domain"
                      :label="domain"
                      :value="domain"
                      hide-details
                      density="compact"
                    ></v-checkbox>
                  </v-col>
                </v-row>
              </v-col>

              <!-- Free text skills -->
              <v-col cols="12">
                <v-textarea
                  v-model="editedResource.skills_free"
                  label="保有スキル・技術スタック（自由記述）"
                  variant="outlined"
                  density="comfortable"
                  rows="3"
                  hide-details
                ></v-textarea>
              </v-col>

              <v-col cols="12">
                <v-switch
                  v-model="editedResource.is_active"
                  label="ログイン有効状態 (無効にするとリソース枠のみとなりログイン不可)"
                  color="success"
                  hide-details
                  :disabled="store.currentRole !== '管理者'"
                ></v-switch>
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>

        <v-card-actions class="d-flex justify-end pt-4 border-top">
          <v-btn variant="text" color="grey" @click="closeResourceDialog">キャンセル</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            class="bg-neon-gradient text-white rounded-lg px-4"
            :loading="resourceSaving"
            @click="saveResource"
          >
            保存する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Holiday Edit/Add Dialog -->
    <v-dialog v-model="holidayDialog" max-width="500px" content-class="glass-panel border-neon-glow" persistent>
      <v-card class="bg-transparent text-white border-0 pa-6" style="backdrop-filter: blur(20px);">
        <v-card-title class="border-bottom pb-3 pl-0">
          <span class="text-h6 font-weight-bold text-neon-blue">
            {{ isEditingHoliday ? '休日情報の編集' : '新規休日の手動登録' }}
          </span>
        </v-card-title>

        <v-card-text class="pt-6 px-0">
          <v-form ref="holidayForm">
            <v-text-field
              v-model="editedHoliday.date"
              label="日付 (YYYY-MM-DD) *"
              required
              placeholder="2026-10-10"
              variant="outlined"
              density="comfortable"
              :disabled="isEditingHoliday"
            ></v-text-field>

            <v-text-field
              v-model="editedHoliday.name"
              label="休日名 / 祝日名 *"
              required
              placeholder="創立記念日"
              variant="outlined"
              density="comfortable"
            ></v-text-field>

            <v-checkbox
              v-model="editedHoliday.is_company_holiday"
              label="企業独自の休日 (会社休日)"
              color="warning"
              hide-details
            ></v-checkbox>
          </v-form>
        </v-card-text>

        <v-card-actions class="d-flex justify-end pt-4 border-top">
          <v-btn variant="text" color="grey" @click="closeHolidayDialog">キャンセル</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            class="bg-neon-gradient text-white rounded-lg px-4"
            :loading="holidaySaving"
            @click="saveHoliday"
          >
            保存する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteConfirmDialog" max-width="400px" content-class="glass-panel border-neon-glow">
      <v-card class="bg-transparent text-white border-0 pa-6" style="backdrop-filter: blur(20px);">
        <v-card-title class="pl-0 pb-2 text-h6 font-weight-bold text-error">
          本当に削除しますか？
        </v-card-title>
        <v-card-text class="px-0 py-3 text-body-2 text-grey-lighten-2">
          この操作は取り消せません。対象のデータ (<strong>{{ itemToDeleteName }}</strong>) をデータベースから完全に削除します。
        </v-card-text>
        <v-card-actions class="d-flex justify-end gap-2 pt-3 pl-0 pr-0">
          <v-btn variant="text" color="grey" @click="deleteConfirmDialog = false">キャンセル</v-btn>
          <v-btn color="error" variant="flat" class="rounded-lg" @click="executeDelete">削除する</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Error/Success Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor" timeout="4000">
      {{ snackbarText }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar = false">閉じる</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useProjectStore } from '../store/project'

const store = useProjectStore()

// State variables
const activeTab = ref('resources')
const nlpQuery = ref('')
const nlpSearching = ref(false)
const nlpSearched = ref(false)
const nlpResults = ref([])

const filterYear = ref(2026)
const syncYear = ref(2026)
const syncLoading = ref(false)

// Dialogs & edit states
const resourceDialog = ref(false)
const isEditingResource = ref(false)
const resourceSaving = ref(false)
const defaultResource = {
  name: '',
  email: '',
  password: '',
  role: 'SE',
  system_role: 'メンバー',
  hourly_cost_jpy: 5000,
  start_time: '09:00',
  end_time: '18:00',
  break_hours: 1.0,
  daily_working_hours: 8.0,
  allocation_limit: 100,
  available_from: '',
  available_to: '',
  working_days: ['月', '火', '水', '木', '金'],
  skills_phase: ['設計', '実装'],
  skills_domain: ['アプリ領域'],
  skills_free: '',
  is_active: true
}
const editedResource = ref({ ...defaultResource })

const holidayDialog = ref(false)
const isEditingHoliday = ref(false)
const holidaySaving = ref(false)
const defaultHoliday = {
  date: '',
  name: '',
  is_company_holiday: false,
  year: 2026
}
const editedHoliday = ref({ ...defaultHoliday })

// Delete state
const deleteConfirmDialog = ref(false)
const deleteType = ref('') // 'resource' or 'holiday'
const itemToDeleteId = ref('')
const itemToDeleteName = ref('')

// Snackbar notification state
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

// Helper function to show notifications
const notify = (text, color = 'success') => {
  snackbarText.value = text
  snackbarColor.value = color
  snackbar.value = true
}

// System Role color helper
const getSystemRoleColor = (role) => {
  if (role === '管理者') return 'error'
  if (role === 'マネージャ') return 'warning'
  return 'primary'
}

// Compute dynamic working hours based on start/end/break
const calculatedDailyHours = computed(() => {
  const start = editedResource.value.start_time
  const end = editedResource.value.end_time
  const breakHrs = editedResource.value.break_hours
  
  if (!start || !end) return 0
  
  try {
    const [sh, sm] = start.split(':').map(Number)
    const [eh, em] = end.split(':').map(Number)
    if (isNaN(sh) || isNaN(sm) || isNaN(eh) || isNaN(em)) return 0
    
    const diff = (eh + em / 60) - (sh + sm / 60)
    const total = diff - (Number(breakHrs) || 0)
    return Math.max(0, parseFloat(total.toFixed(2)))
  } catch (e) {
    return 0
  }
})

// Permissions based on user roles
const canCreateResource = computed(() => store.currentRole === '管理者')
const canEditResource = computed(() => store.currentRole === '管理者' || store.currentRole === 'マネージャ')
const canDeleteResource = computed(() => store.currentRole === '管理者')
const canToggleStatus = computed(() => store.currentRole === '管理者')
const canManageCalendar = computed(() => store.currentRole === '管理者' || store.currentRole === 'マネージャ')
const canEditPassword = computed(() => {
  if (!isEditingResource.value) return store.currentRole === '管理者'
  return store.currentRole === '管理者' || (store.currentUser && store.currentUser.id === editedResource.value.id)
})

// Lifecycle hook
onMounted(async () => {
  await store.fetchResources()
  await store.fetchHolidays(filterYear.value)
})

// NLP Search
const runNlpSearch = async () => {
  if (!nlpQuery.value.trim()) {
    notify('検索キーワードを入力してください。', 'warning')
    return
  }
  nlpSearching.value = true
  nlpSearched.value = false
  try {
    const results = await store.fetchResourcesNLP(nlpQuery.value)
    nlpResults.value = results
    nlpSearched.value = true
  } catch (e) {
    notify(`AI検索エラー: ${e.message}`, 'error')
  } finally {
    nlpSearching.value = false
  }
}

// Toggle Resource Login State directly
const toggleResourceActive = async (resource) => {
  if (store.currentRole !== '管理者') {
    notify('ログイン状態の変更権限がありません。(管理者のみ)', 'error')
    return
  }
  try {
    const payload = {
      is_active: !resource.is_active
    }
    await store.updateResource(resource.id, payload)
    notify(`「${resource.name}」のステータスを更新しました。`)
  } catch (e) {
    notify(`更新エラー: ${e.message}`, 'error')
  }
}

// Resource Dialog Open/Close
const openResourceDialog = (resource = null) => {
  if (resource) {
    isEditingResource.value = true
    editedResource.value = { 
      ...resource,
      password: '',
      available_from: resource.available_from || '',
      available_to: resource.available_to || '',
      skills_phase: resource.skills_phase || [],
      skills_domain: resource.skills_domain || [],
      working_days: resource.working_days || ['月', '火', '水', '木', '金']
    }
  } else {
    isEditingResource.value = false
    editedResource.value = { ...defaultResource, password: '' }
  }
  resourceDialog.value = true
}

const closeResourceDialog = () => {
  resourceDialog.value = false
}

// Save Resource (Create or Update)
const saveResource = async () => {
  if (!editedResource.value.name || !editedResource.value.email) {
    notify('必須項目を入力してください。', 'warning')
    return
  }
  
  // Set calculated daily hours
  editedResource.value.daily_working_hours = calculatedDailyHours.value
  
  resourceSaving.value = true
  try {
    if (isEditingResource.value) {
      await store.updateResource(editedResource.value.id, editedResource.value)
      notify(`リソース「${editedResource.value.name}」の情報を更新しました。`)
    } else {
      await store.createResource(editedResource.value)
      notify(`新しいリソース「${editedResource.value.name}」を登録しました。`)
    }
    closeResourceDialog()
  } catch (e) {
    notify(`保存エラー: ${e.message || e}`, 'error')
  } finally {
    resourceSaving.value = false
  }
}

// Delete Resource Confirm Dialog
const confirmDeleteResource = (resource) => {
  deleteType.value = 'resource'
  itemToDeleteId.value = resource.id
  itemToDeleteName.value = resource.name
  deleteConfirmDialog.value = true
}

// Calendar Filter change
const onFilterYearChange = async () => {
  await store.fetchHolidays(filterYear.value)
}

// Run Public Holiday Sync with LLM
const runCalendarSync = async () => {
  if (!syncYear.value) {
    notify('同期対象の年を入力してください。', 'warning')
    return
  }
  syncLoading.value = true
  try {
    await store.syncPublicHolidays(syncYear.value)
    filterYear.value = syncYear.value
    notify(`${syncYear.value}年の祝祭日データをAI同期しました。`)
  } catch (e) {
    notify(`祝日同期エラー: ${e.message || e}`, 'error')
  } finally {
    syncLoading.value = false
  }
}

// Holiday Dialog Open/Close
const openHolidayDialog = (holiday = null) => {
  if (holiday) {
    isEditingHoliday.value = true
    editedHoliday.value = { ...holiday }
  } else {
    isEditingHoliday.value = false
    editedHoliday.value = { 
      ...defaultHoliday,
      year: filterYear.value,
      date: `${filterYear.value}-01-01`
    }
  }
  holidayDialog.value = true
}

const closeHolidayDialog = () => {
  holidayDialog.value = false
}

// Save Holiday (Create or Update)
const saveHoliday = async () => {
  if (!editedHoliday.value.date || !editedHoliday.value.name) {
    notify('日付と休日名を入力してください。', 'warning')
    return
  }
  
  // Extract year from date string
  try {
    const year = parseInt(editedHoliday.value.date.split('-')[0])
    if (!isNaN(year)) {
      editedHoliday.value.year = year
    }
  } catch (e) {}

  holidaySaving.value = true
  try {
    if (isEditingHoliday.value) {
      await store.updateHoliday(editedHoliday.value.id, editedHoliday.value)
      notify(`休日「${editedHoliday.value.name}」を更新しました。`)
    } else {
      await store.createHoliday(editedHoliday.value)
      notify(`新規休日「${editedHoliday.value.name}」を登録しました。`)
    }
    closeHolidayDialog()
  } catch (e) {
    notify(`保存エラー: ${e.message || e}`, 'error')
  } finally {
    holidaySaving.value = false
  }
}

// Confirm Delete Holiday
const confirmDeleteHoliday = (holiday) => {
  deleteType.value = 'holiday'
  itemToDeleteId.value = holiday.id
  itemToDeleteName.value = `${holiday.date} - ${holiday.name}`
  deleteConfirmDialog.value = true
}

// Execute Delete (both Resources and Holidays)
const executeDelete = async () => {
  deleteConfirmDialog.value = false
  try {
    if (deleteType.value === 'resource') {
      await store.deleteResource(itemToDeleteId.value)
      notify('リソースを削除しました。')
    } else if (deleteType.value === 'holiday') {
      await store.deleteHoliday(itemToDeleteId.value, filterYear.value)
      notify('休日を削除しました。')
    }
  } catch (e) {
    notify(`削除に失敗しました: ${e.message || e}`, 'error')
  }
}
</script>

<style scoped>
.admin-non-assignable td {
  opacity: 0.65;
}
.custom-admin-table th {
  border-bottom: 2px solid rgba(255, 255, 255, 0.1) !important;
  color: var(--color-neon-blue) !important;
  font-weight: bold !important;
  text-transform: uppercase;
  font-size: 13px;
  letter-spacing: 0.5px;
}
.custom-admin-table td {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
  padding: 12px 16px !important;
  font-size: 14px;
}
.custom-admin-table tr:hover {
  background: rgba(255, 255, 255, 0.02);
}
.bg-rgba-white-05 {
  background: rgba(255, 255, 255, 0.03);
  border: 1px dashed rgba(0, 242, 254, 0.2);
}
.border-left-purple {
  border-left: 3px solid var(--color-neon-purple);
}
.nlp-results-container {
  max-height: 450px;
  overflow-y: auto;
}
.gap-2 {
  gap: 8px;
}
.gap-3 {
  gap: 12px;
}
.border-top {
  border-top: 1px solid rgba(255, 255, 255, 0.08) !important;
}
</style>
