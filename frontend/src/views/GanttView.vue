<template>
  <v-container fluid class="pa-6">
    <!-- View Header -->
    <div class="d-flex align-center justify-between mb-4 flex-wrap gap-3">
      <div>
        <h1 class="text-h4 font-weight-bold text-neon-blue">WBS / ガントチャート</h1>
        <p class="text-caption text-grey">タスク間の依存関係およびスケジュールの可視化</p>
      </div>
      <v-spacer></v-spacer>
      
      <!-- Apply Plan B controls -->
      <div v-if="store.planBGhostActive && (activeTab === 'wbs' || activeTab === 'tasklist')" class="d-flex align-center gap-2 mr-4 bg-glass border-neon-glow pa-2 rounded-lg">
        <span class="text-caption text-warning font-weight-bold">⚠️ プランB（スケジュール再編案）提示中</span>
        <v-btn size="small" variant="flat" class="bg-neon-gradient text-white" @click="handleApplyPlanB">
          再構築案を適用する
        </v-btn>
      </div>

      <v-btn
        v-if="activeTab === 'wbs' || activeTab === 'tasklist'"
        variant="outlined"
        color="primary"
        prepend-icon="mdi-plus"
        @click="openCreateDialog"
      >
        タスク追加
      </v-btn>
    </div>

    <!-- Navigation Tabs -->
    <v-tabs v-model="activeTab" class="mb-6 border-bottom" color="primary">
      <v-tab value="wbs">プロジェクト WBS</v-tab>
      <v-tab value="tasklist">タスク一覧</v-tab>
      <v-tab value="portfolio">ポートフォリオ・オーケストレーター</v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <!-- Tab 1: WBS -->
      <v-window-item value="wbs">
        <!-- Project Selector and Creation Row -->
        <v-row class="mb-4 align-center">
          <v-col cols="12" sm="6" md="4">
            <v-select
              v-model="selectedProjectId"
              label="表示するプロジェクト"
              :items="projectOptions"
              item-title="name"
              item-value="id"
              density="comfortable"
              variant="solo-filled"
              bg-color="rgba(255,255,255,0.03)"
              class="glass-input"
              hide-details
            ></v-select>
          </v-col>
          <v-col cols="12" sm="6" md="8" class="d-flex gap-2">
            <v-btn
              variant="outlined"
              color="secondary"
              prepend-icon="mdi-folder-plus-outline"
              @click="openProjectCreateDialog"
            >
              新規プロジェクト作成
            </v-btn>
            <v-btn
              color="primary"
              variant="elevated"
              prepend-icon="mdi-brain"
              class="bg-gradient-neon"
              @click="openAIPlanningDialog"
            >
              AIで計画を作成
            </v-btn>
          </v-col>
        </v-row>

        <v-row>
          <!-- Gantt chart container -->
          <v-col cols="12" :md="selectedTaskId ? 8 : 12" class="transition-width">
            <GanttChart @task-click="handleTaskSelect" />
          </v-col>

          <!-- Sidebar for Hearing chat -->
          <v-col cols="12" md="4" v-if="selectedTaskId">
            <HearingChat :task-id="selectedTaskId" />
          </v-col>
        </v-row>
      </v-window-item>

      <!-- Tab 2: Task List -->
      <v-window-item value="tasklist">
        <v-card class="glass-panel border-neon-glow pa-6">
          <v-card-title class="text-subtitle-1 font-weight-bold text-white d-flex align-center pb-4">
            <v-icon start color="primary">mdi-format-list-bulleted</v-icon>
            WBS タスク一覧・詳細フィルタ
          </v-card-title>

          <!-- Filters Row -->
          <v-row class="mb-4">
            <v-col cols="12" sm="4" md="3">
              <v-text-field
                v-model="searchFilter"
                label="キーワード検索"
                prepend-inner-icon="mdi-magnify"
                clearable
                density="comfortable"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
                class="glass-input"
                hide-details
              ></v-text-field>
            </v-col>
            <v-col cols="12" sm="4" md="2.4">
              <v-select
                v-model="projectFilter"
                label="プロジェクト"
                :items="[{id: 'ALL', name: 'すべてのプロジェクト'}, ...projectOptions]"
                item-title="name"
                item-value="id"
                density="comfortable"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
                class="glass-input"
                hide-details
              ></v-select>
            </v-col>
            <v-col cols="12" sm="4" md="2.2">
              <v-select
                v-model="statusFilter"
                label="ステータス"
                :items="[
                  {value: 'ALL', title: 'すべてのステータス'},
                  {value: 'TODO', title: '未開始 (TODO)'},
                  {value: 'IN_PROGRESS', title: '対応中 (IN_PROGRESS)'},
                  {value: 'REVIEW', title: 'レビュー (REVIEW)'},
                  {value: 'DONE', title: '完了 (DONE)'}
                ]"
                item-title="title"
                item-value="value"
                density="comfortable"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
                class="glass-input"
                hide-details
              ></v-select>
            </v-col>
            <v-col cols="12" sm="6" md="2.2">
              <v-select
                v-model="priorityFilter"
                label="優先度"
                :items="[
                  {value: 'ALL', title: 'すべての優先度'},
                  {value: 'HIGH', title: '高 (HIGH)'},
                  {value: 'MEDIUM', title: '中 (MEDIUM)'},
                  {value: 'LOW', title: '低 (LOW)'}
                ]"
                item-title="title"
                item-value="value"
                density="comfortable"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
                class="glass-input"
                hide-details
              ></v-select>
            </v-col>
            <v-col cols="12" sm="6" md="2.2">
              <v-select
                v-model="assigneeTypeFilter"
                label="担当者タイプ"
                :items="[
                  {value: 'ALL', title: 'すべての担当者'},
                  {value: 'HUMAN', title: '人間 (HUMAN)'},
                  {value: 'AI', title: 'AIワーカー (AI)'}
                ]"
                item-title="title"
                item-value="value"
                density="comfortable"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
                class="glass-input"
                hide-details
              ></v-select>
            </v-col>
          </v-row>

          <!-- Data Table -->
          <v-data-table
            :headers="headers"
            :items="tableTasks"
            :loading="store.loading"
            loading-text="タスク一覧をロード中..."
            no-data-text="該当するタスクが見つかりません"
            hover
            density="comfortable"
            class="glass-table text-white bg-transparent"
          >
            <!-- Title Column (With Indentation & Node Type Icon) -->
            <template v-slot:item.title="{ item }">
              <span :style="{ marginLeft: `${(item.depth || 0) * 16}px` }" class="d-inline-flex align-center">
                <v-icon v-if="item.depth > 0" start size="14" class="text-grey mr-1">mdi-chevron-right</v-icon>
                <v-icon start size="16" class="mr-1" :color="getNodeTypeColor(item.node_type)">
                  {{ getNodeTypeIcon(item.node_type) }}
                </v-icon>
                <span :class="{ 'font-weight-bold text-white': item.is_summary || (item.depth === 0), 'text-grey-lighten-2': !item.is_summary && item.depth > 0 }">
                  {{ item.title }}
                </span>
                <v-icon v-if="item.gitea_repo" size="14" color="grey" title="Gitea連携済み" class="ml-2">mdi-git</v-icon>
                <v-chip size="x-small" variant="outlined" class="ml-2 px-1" :color="getNodeTypeColor(item.node_type)" style="font-size: 9px; height: 16px;">
                  {{ item.node_type }}
                </v-chip>
              </span>
            </template>

            <!-- Project Column -->
            <template v-slot:item.projectName="{ item }">
              <span class="text-caption text-grey">{{ item.projectName }}</span>
            </template>

            <!-- Assignee Column -->
            <template v-slot:item.assignee_name="{ item }">
              <v-chip
                size="small"
                :color="item.assignee_type === 'AI' ? 'primary' : 'grey'"
                variant="outlined"
              >
                <v-icon v-if="item.assignee_type === 'AI'" start size="12">mdi-robot</v-icon>
                {{ item.assignee_name || '未アサイン' }}
              </v-chip>
            </template>

            <!-- Status Column -->
            <template v-slot:item.status="{ item }">
              <v-chip size="small" :color="getStatusColor(item.status)" variant="flat" class="text-white">
                {{ getStatusLabel(item.status) }}
              </v-chip>
            </template>

            <!-- Priority Column -->
            <template v-slot:item.priority="{ item }">
              <v-chip size="small" :color="getPriorityColor(item.priority)" variant="tonal" class="font-weight-bold">
                {{ item.priority }}
              </v-chip>
            </template>

            <!-- Dates Column -->
            <template v-slot:item.planned_start="{ item }">
              <span class="text-caption text-grey">{{ formatDate(item.planned_start) }}</span>
            </template>
            <template v-slot:item.planned_end="{ item }">
              <span class="text-caption text-grey">{{ formatDate(item.planned_end) }}</span>
            </template>

            <!-- Progress Column -->
            <template v-slot:item.progress="{ item }">
              <div class="d-flex align-center gap-2" style="min-width: 100px;">
                <v-progress-linear
                  :model-value="item.progress"
                  color="primary"
                  height="6"
                  rounded
                  class="flex-grow-1"
                ></v-progress-linear>
                <span class="text-caption font-weight-bold">{{ item.progress }}%</span>
              </div>
            </template>

            <!-- Delay Column -->
            <template v-slot:item.delay_days="{ item }">
              <v-chip v-if="item.delay_days > 0" size="x-small" color="error" class="font-weight-bold">
                {{ item.delay_days }}日遅延
              </v-chip>
              <span v-else class="text-grey text-caption">-</span>
            </template>

            <!-- Actions Column -->
            <template v-slot:item.actions="{ item }">
              <div class="d-flex align-center gap-1">
                <v-btn
                  icon="mdi-chat-processing-outline"
                  size="x-small"
                  variant="text"
                  color="secondary"
                  title="ヒアリングチャットを開く"
                  @click="openHearingChat(item)"
                ></v-btn>
                <v-btn
                  icon="mdi-pencil-outline"
                  size="x-small"
                  variant="text"
                  color="primary"
                  title="編集"
                  @click="openEditDialog(item)"
                ></v-btn>
                <v-btn
                  icon="mdi-delete-outline"
                  size="x-small"
                  variant="text"
                  color="error"
                  title="削除"
                  @click="handleDeleteTask(item)"
                ></v-btn>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-window-item>

      <!-- Tab 3: Portfolio -->
      <v-window-item value="portfolio">
        <v-row>
          <!-- Left: Portfolio Gantt & Allocations -->
          <v-col cols="12" md="8">
            <div class="d-flex flex-column gap-6">
              <!-- Portfolio Gantt Chart -->
              <v-card class="glass-panel border-neon-glow pa-4">
                <v-card-title class="text-subtitle-1 font-weight-bold text-white d-flex align-center pb-2">
                  <v-icon start color="primary">mdi-chart-gantt</v-icon>
                  全プロジェクト横断ガントチャート
                </v-card-title>
                
                <div v-if="store.planBGhostActive" class="d-flex align-center gap-2 mb-4 bg-glass border-neon-glow pa-2 rounded-lg justify-space-between">
                  <span class="text-caption text-warning font-weight-bold">⚠️ リソースシフト適用に伴うスケジュール再計算シミュレーション（Ghost表示中）</span>
                  <v-btn size="x-small" variant="flat" color="error" @click="store.planBGhostActive = false">
                    Ghost表示を閉じる
                  </v-btn>
                </div>
                
                <GanttChart :is-portfolio="true" />
              </v-card>

              <!-- Projects & Resource Allocations -->
              <v-card class="glass-panel border-neon-glow pa-4">
                <v-card-title class="text-subtitle-1 font-weight-bold text-white d-flex align-center pb-4">
                  <v-icon start color="primary">mdi-account-group-outline</v-icon>
                  プロジェクト別リソース稼働状況
                </v-card-title>
                
                <v-row>
                  <v-col
                    cols="12"
                    sm="6"
                    v-for="proj in store.portfolioProjects"
                    :key="proj.id"
                  >
                    <v-card class="glass-card pa-4 h-100 border-subtle">
                       <div class="text-subtitle-2 font-weight-bold text-neon-blue mb-3">
                        {{ proj.name }}
                      </div>
                      
                      <v-list class="bg-transparent pa-0">
                        <v-list-item
                          v-for="alloc in proj.allocations"
                          :key="alloc.id"
                          class="px-0 py-2 border-bottom-dashed"
                        >
                          <div class="d-flex align-center justify-between w-100 flex-wrap gap-2">
                            <div class="d-flex align-center gap-2">
                              <v-icon size="16" :color="alloc.is_ai ? 'secondary' : 'grey'">
                                {{ alloc.is_ai ? 'mdi-robot' : 'mdi-account' }}
                              </v-icon>
                              <span class="text-body-2 font-weight-medium text-white">
                                {{ alloc.resource_name }}
                              </span>
                              <v-chip
                                v-for="tag in alloc.skill_tags"
                                :key="tag"
                                size="x-small"
                                color="grey"
                                variant="outlined"
                                class="ml-1"
                              >
                                {{ tag }}
                              </v-chip>
                            </div>
                            <div class="d-flex align-center gap-2">
                              <v-progress-linear
                                :model-value="alloc.allocation_percent"
                                color="primary"
                                height="6"
                                width="60"
                                rounded
                                class="mr-2"
                                style="width: 60px;"
                              ></v-progress-linear>
                              <span class="text-caption font-weight-bold text-white">
                                {{ alloc.allocation_percent }}%
                              </span>
                            </div>
                          </div>
                        </v-list-item>
                      </v-list>
                    </v-card>
                  </v-col>
                </v-row>
              </v-card>
            </div>
          </v-col>

          <!-- Right: Conflict Alerts Panel -->
          <v-col cols="12" md="4">
            <v-card class="glass-panel border-neon-glow pa-4 h-100">
              <v-card-title class="text-subtitle-1 font-weight-bold text-neon-purple d-flex align-center pb-4">
                <v-icon start color="secondary">mdi-alert-decagram-outline</v-icon>
                リソース競合・調停アラート
              </v-card-title>
              
              <div v-if="store.loading" class="d-flex justify-center align-center py-12">
                <v-progress-circular indeterminate color="secondary"></v-progress-circular>
              </div>
              
              <div v-else>
                <div v-if="!store.portfolioConflicts.length" class="text-center py-8 text-grey text-caption">
                  <v-icon size="36" color="success" class="mb-2">mdi-check-decagram-outline</v-icon>
                  <div>現在、プロジェクト間のリソース競合やボトルネックは検知されていません。</div>
                </div>
                
                <div v-else class="d-flex flex-column gap-4">
                  <v-card
                    v-for="conflict in store.portfolioConflicts"
                    :key="conflict.id"
                    class="glass-card pa-4 border-warning border-subtle"
                    style="border: 1px solid rgba(255, 179, 0, 0.3) !important;"
                  >
                    <div class="d-flex align-center gap-2 mb-2">
                      <v-icon color="warning">mdi-alert-outline</v-icon>
                      <span class="text-subtitle-2 font-weight-bold text-warning">稼働シフト調停案</span>
                    </div>
                    
                    <div class="text-caption text-grey mb-3">
                      {{ conflict.description }}
                    </div>
                    
                    <div class="bg-glass pa-3 rounded-lg border-subtle text-caption mb-4">
                      <div><strong>対象リソース:</strong> {{ conflict.resource_name }} ({{ conflict.skill }})</div>
                      <div><strong>移行元:</strong> {{ conflict.donor_project_name }}</div>
                      <div><strong>移行先:</strong> {{ conflict.delayed_project_name }} (-{{ conflict.shift_percent }}%)</div>
                      <div><strong>穴埋めAI:</strong> {{ conflict.substitute_ai_name }} (+{{ conflict.shift_percent }}%)</div>
                    </div>
                    
                    <v-btn
                      block
                      variant="flat"
                      class="bg-neon-gradient text-white font-weight-bold"
                      size="small"
                      @click="handleApplyShift(conflict)"
                    >
                      調停案を承認（一括シフト）
                    </v-btn>
                  </v-card>
                </div>
              </div>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>
    </v-window>

    <!-- Project Creation Dialog -->
    <v-dialog v-model="projectCreateDialog" max-width="500px" content-class="glass-panel border-neon-glow">
      <v-card class="bg-transparent text-white border-0 pa-4" style="backdrop-filter: blur(20px);">
        <v-card-title class="text-h6 font-weight-bold text-neon-blue pb-3 border-bottom">
          新規プロジェクト作成
        </v-card-title>
        
        <v-card-text class="pt-4">
          <v-form ref="projectForm">
            <v-text-field
              v-model="newProject.name"
              label="プロジェクト名"
              required
              class="glass-input mb-4"
              variant="solo-filled"
              bg-color="rgba(255,255,255,0.03)"
            ></v-text-field>

            <v-select
              v-model="newProject.template_type"
              label="WBS初期テンプレート"
              :items="[
                { value: 'FLAT', title: 'テンプレートなし (空のWBS)' },
                { value: 'PHASE_BASED', title: 'フェーズベース (要件定義/設計/開発/テスト/リリース)' },
                { value: 'FEATURE_BASED', title: '主要機能ベース (機能開発フェーズ構成)' }
              ]"
              item-title="title"
              item-value="value"
              class="glass-input mb-4"
              variant="solo-filled"
              bg-color="rgba(255,255,255,0.03)"
              required
            ></v-select>
          </v-form>
        </v-card-text>

        <v-card-actions class="d-flex justify-end pt-2">
          <v-btn variant="text" color="grey" @click="projectCreateDialog = false">キャンセル</v-btn>
          <v-btn
            variant="flat"
            class="bg-neon-gradient text-white"
            @click="handleSaveProject"
          >
            作成する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- AI WBS Planning Dialog -->
    <v-dialog v-model="planningDialog" max-width="1100px" content-class="glass-panel border-neon-glow" persistent>
      <v-card class="bg-transparent text-white border-0 pa-4" style="backdrop-filter: blur(20px);">
        <v-card-title class="text-h6 font-weight-bold text-neon-blue pb-3 border-bottom d-flex align-center justify-between">
          <span>AIプランニング（WBS下案の自動作成）</span>
          <v-btn icon="mdi-close" variant="text" color="grey" @click="planningDialog = false" class="ml-auto"></v-btn>
        </v-card-title>
        
        <v-card-text class="pt-4">
          <!-- Error Alert Banner -->
          <v-alert
            v-if="planningErrorMessage"
            type="error"
            variant="tonal"
            closable
            class="mb-4"
            @click:close="planningErrorMessage = ''"
          >
            {{ planningErrorMessage }}
          </v-alert>

          <v-row>
            <!-- Left Input Pane (4 cols) -->
            <v-col cols="12" md="4" class="border-right pe-4">
              <h3 class="text-subtitle-1 font-weight-bold mb-3 text-neon-blue">1. 解析条件とテキストの入力</h3>
              
              <v-radio-group v-model="planningProjectMode" class="mb-4" density="compact" inline>
                <v-radio label="既存プロジェクトに追加" value="existing" class="text-caption"></v-radio>
                <v-radio label="新規プロジェクトを作成" value="new" class="text-caption"></v-radio>
              </v-radio-group>

              <!-- Existing project selector -->
              <v-select
                v-if="planningProjectMode === 'existing'"
                v-model="planningProjectId"
                label="対象プロジェクト"
                :items="projectOptions"
                item-title="name"
                item-value="id"
                class="glass-input mb-4"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
                hide-details
              ></v-select>

              <!-- New project options -->
              <div v-else>
                <v-text-field
                  v-model="planningNewProject.name"
                  label="新しいプロジェクト名"
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                  hide-details
                ></v-text-field>

                <v-select
                  v-model="planningNewProject.template_type"
                  label="WBSテンプレート"
                  :items="[
                    { value: 'FLAT', title: 'テンプレートなし (空のWBS)' },
                    { value: 'PHASE_BASED', title: 'フェーズベース' },
                    { value: 'FEATURE_BASED', title: '主要機能ベース' }
                  ]"
                  item-title="title"
                  item-value="value"
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                  hide-details
                ></v-select>
              </div>

              <!-- Textarea for minutes/transcript -->
              <v-textarea
                v-model="planningText"
                label="議事録 / 要件テキストを貼り付け"
                placeholder="例：次のプロジェクトでは、要件定義を行った後、Vue3を使ったフロントエンド開発と決済APIの連携開発を行います。佐藤さんはフロント、鈴木さんは決済連携を担当します。"
                rows="10"
                class="glass-input mb-4"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
                no-resize
                hide-details
              ></v-textarea>

              <v-btn
                block
                color="primary"
                class="bg-gradient-neon font-weight-bold"
                :loading="isAnalyzing"
                :disabled="!planningText || (planningProjectMode === 'new' && !planningNewProject.name) || (planningProjectMode === 'existing' && !planningProjectId)"
                @click="handleAnalyzePlanning"
              >
                AI解析を実行する
              </v-btn>
            </v-col>

            <!-- Right Staging Pane (8 cols) -->
            <v-col cols="12" md="8" class="ps-4">
              <!-- Loading State -->
              <div v-if="isAnalyzing" class="d-flex flex-column align-center justify-center py-12">
                <v-progress-circular indeterminate color="primary" size="64" class="mb-4"></v-progress-circular>
                <div class="text-body-1 font-weight-medium text-grey">AIがテキストを解析してWBSの下案を作成中...</div>
              </div>

              <!-- Empty State (Before analysis) -->
              <div v-else-if="!analyzeResult" class="d-flex flex-column align-center justify-center py-12 text-grey-darken-1">
                <v-icon size="64" class="mb-4">mdi-brain</v-icon>
                <div class="text-body-1">左側で条件を入力し、「AI解析を実行する」をクリックしてください。</div>
              </div>

              <!-- Staging review pane -->
              <div v-else class="d-flex flex-column fill-height" style="max-height: 60vh; overflow-y: auto;">
                <div class="mb-4">
                  <h3 class="text-subtitle-1 font-weight-bold text-neon-blue mb-1">2. WBS下案のレビューと編集</h3>
                  <p class="text-caption text-grey">{{ analyzeResult.summary }}</p>
                </div>

                <!-- Warnings & Recommendations -->
                <div v-if="analyzeResult.staffing_recommendations.length > 0" class="mb-4">
                  <v-alert
                    v-for="(rec, idx) in analyzeResult.staffing_recommendations"
                    :key="idx"
                    type="warning"
                    variant="tonal"
                    density="comfortable"
                    class="mb-2 text-caption"
                  >
                    <template v-slot:prepend>
                      <v-icon size="20">mdi-account-alert-outline</v-icon>
                    </template>
                    <strong>【リソース要員警告 - {{ rec.skill }}】</strong> {{ rec.detail }}
                  </v-alert>
                </div>

                <!-- Clarifying Questions -->
                <v-card v-if="analyzeResult.clarifying_questions.length > 0" class="glass-panel mb-4 pa-3 border-subtle bg-glass">
                  <div class="text-caption font-weight-bold text-neon-blue mb-2 d-flex align-center gap-1">
                    <v-icon color="primary" size="16">mdi-help-circle-outline</v-icon>
                    AIからの逆質問（残課題）:
                  </div>
                  <ul class="ps-4 text-caption text-grey">
                    <li v-for="(q, idx) in analyzeResult.clarifying_questions" :key="idx" class="mb-1">{{ q }}</li>
                  </ul>
                </v-card>

                <!-- Preventive Tasks Proposals -->
                <v-card v-if="analyzeResult.preventive_tasks.length > 0" class="glass-panel mb-4 pa-3 border-subtle bg-glass">
                  <div class="text-caption font-weight-bold text-secondary mb-2 d-flex align-center gap-1">
                    <v-icon color="secondary" size="16">mdi-shield-alert-outline</v-icon>
                    教訓（Lessons-Learned）に基づく予防タスク提案:
                  </div>
                  <v-row dense>
                    <v-col cols="12" v-for="(pt, idx) in analyzeResult.preventive_tasks" :key="idx" class="mb-2">
                      <div class="d-flex align-center justify-between gap-3 bg-glass border-subtle pa-2 rounded-lg">
                        <div class="flex-grow-1">
                          <div class="text-caption font-weight-bold text-white">{{ pt.title }}</div>
                          <div class="text-caption text-grey">{{ pt.reason }}</div>
                        </div>
                        <v-btn
                          size="x-small"
                          color="secondary"
                          variant="outlined"
                          prepend-icon="mdi-plus"
                          @click="addPreventiveTaskToTree(pt)"
                        >
                          WBSへ追加
                        </v-btn>
                      </div>
                    </v-col>
                  </v-row>
                </v-card>

                <!-- WBS Tree Nodes List -->
                <div class="bg-glass border-subtle rounded-lg pa-3 mb-4">
                  <div class="text-caption font-weight-bold text-white mb-3">WBS 階層ツリー下案:</div>
                  
                  <div v-for="node in orderedStagingNodes" :key="node.temp_id" :style="{ marginLeft: (node.depth * 20) + 'px' }" class="d-flex align-center gap-2 py-2 border-bottom-dashed">
                    <!-- Status Checkbox (採用/却下) -->
                    <v-checkbox-btn
                      v-model="node.adopted"
                      density="compact"
                      hide-details
                      color="primary"
                    ></v-checkbox-btn>

                    <!-- Indent indicator line or symbol -->
                    <span v-if="node.depth > 0" class="text-grey-darken-2">└─</span>

                    <!-- Node type badge -->
                    <v-chip
                      size="x-small"
                      :color="getNodeTypeColor(node.node_type)"
                      class="text-caption font-weight-bold"
                      variant="flat"
                    >
                      {{ node.node_type }}
                    </v-chip>

                    <!-- Title Input (Directly Editable) -->
                    <input
                      v-model="node.title"
                      class="glass-inline-input text-caption font-weight-bold text-white flex-grow-1"
                      placeholder="タイトル"
                      :disabled="!node.adopted"
                    />

                    <!-- Estimated hours (TASK only) -->
                    <div v-if="node.node_type === 'TASK'" class="d-flex align-center gap-1" style="width: 80px;">
                      <input
                        v-model.number="node.estimated_hours"
                        type="number"
                        min="0"
                        class="glass-inline-input text-caption text-center text-white"
                        style="width: 50px;"
                        :disabled="!node.adopted"
                      />
                      <span class="text-caption text-grey">h</span>
                    </div>

                    <!-- Assignee Select (TASK only) -->
                    <div v-if="node.node_type === 'TASK'" style="width: 140px;">
                      <v-select
                        v-model="node.assignee_name"
                        :items="['', ...assignableResources.map(r => r.name)]"
                        placeholder="未割り当て"
                        density="compact"
                        variant="plain"
                        hide-details
                        class="text-caption pa-0 ma-0 custom-select"
                        :disabled="!node.adopted"
                      ></v-select>
                    </div>

                    <!-- Confidence Badge -->
                    <v-chip
                      v-if="node.confidence !== undefined"
                      size="x-small"
                      :color="node.confidence >= 0.75 ? 'success' : 'error'"
                      variant="outlined"
                      class="text-caption"
                      :class="node.confidence < 0.75 ? 'border-neon-glow' : ''"
                    >
                      信頼度 {{ Math.round(node.confidence * 100) }}%
                    </v-chip>

                    <!-- Reject Button -->
                    <v-btn
                      icon="mdi-trash-can-outline"
                      size="x-small"
                      variant="text"
                      color="error"
                      @click="node.adopted = false"
                      :disabled="!node.adopted"
                    ></v-btn>
                  </div>
                </div>
              </div>
            </v-col>
          </v-row>
        </v-card-text>

        <v-card-actions class="d-flex justify-end pt-4 border-top">
          <v-btn variant="text" color="grey" @click="planningDialog = false" :disabled="isApplying">キャンセル</v-btn>
          <v-btn
            variant="flat"
            class="bg-neon-gradient text-white font-weight-bold"
            :loading="isApplying"
            :disabled="!analyzeResult || !hasAdoptedNodes"
            @click="handleApplyPlanning"
          >
            WBSへ登録する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Create/Edit Task Dialog -->
    <v-dialog v-model="createDialog" max-width="600px" content-class="glass-panel border-neon-glow">
      <v-card class="bg-transparent text-white border-0 pa-4" style="backdrop-filter: blur(20px);">
        <v-card-title class="text-h6 font-weight-bold text-neon-blue pb-3 border-bottom">
          {{ isEditMode ? 'WBS タスク編集' : '新規 WBS タスク追加' }}
        </v-card-title>
        
        <v-card-text class="pt-4">
          <!-- Error Alert Banner -->
          <v-alert
            v-if="errorMessage"
            type="error"
            variant="tonal"
            closable
            class="mb-4"
            @click:close="errorMessage = ''"
          >
            {{ errorMessage }}
          </v-alert>

          <!-- Lessons Learned Advisor Panel inside Task Creation -->
          <div v-if="lessonsAdvisorList.length > 0" class="mb-4 pa-3 bg-glass border-neon-purple rounded-lg border-subtle">
            <div class="d-flex align-center gap-2 mb-2">
              <v-icon color="secondary" size="18">mdi-lightbulb-on-outline</v-icon>
              <span class="text-caption font-weight-bold text-neon-purple">Lessons Learned アラート (過去のトラブル知見)</span>
            </div>
            <div v-for="(lesson, idx) in lessonsAdvisorList" :key="idx" class="text-caption mb-2 text-grey">
              <strong>{{ lesson.title }}:</strong> {{ lesson.content }}
              <div class="mt-2 d-flex justify-end">
                <v-btn size="x-small" color="secondary" variant="outlined" @click="addPreventiveSubtask(lesson)">
                  予防タスクをWBSへ追加
                </v-btn>
              </div>
            </div>
          </div>

          <v-form ref="form">
            <v-text-field
              v-model="newTask.title"
              label="タスクタイトル"
              required
              class="glass-input mb-4"
              variant="solo-filled"
              bg-color="rgba(255,255,255,0.03)"
              @blur="triggerLessonsAdvisor"
            ></v-text-field>

            <v-textarea
              v-model="newTask.description"
              label="詳細説明"
              rows="3"
              class="glass-input mb-4"
              variant="solo-filled"
              bg-color="rgba(255,255,255,0.03)"
              @blur="triggerLessonsAdvisor"
            ></v-textarea>

            <v-select
              v-model="newTask.project_id"
              label="所属プロジェクト"
              :items="projectOptions"
              item-title="name"
              item-value="id"
              class="glass-input mb-4"
              variant="solo-filled"
              bg-color="rgba(255,255,255,0.03)"
              required
            ></v-select>

            <!-- Hierarchy WBS Node Types -->
            <v-row>
              <v-col cols="6">
                <v-select
                  v-model="newTask.node_type"
                  label="ノードタイプ (Node Type)"
                  :items="['PHASE', 'FEATURE', 'SPRINT', 'STORY', 'TASK']"
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                  required
                ></v-select>
              </v-col>
              <v-col cols="6">
                <v-select
                  v-model="newTask.parent_id"
                  label="親サマリータスク"
                  :items="[{id: null, title: 'なし (ルートノード)'}, ...parentTaskCandidates]"
                  item-title="title"
                  item-value="id"
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                  clearable
                ></v-select>
              </v-col>
            </v-row>

            <!-- Effort Estimation fields -->
            <v-row>
              <v-col cols="6">
                <v-text-field
                  v-model.number="newTask.estimated_hours"
                  label="見積予定工数 (時間)"
                  type="number"
                  min="0"
                  step="0.5"
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                ></v-text-field>
              </v-col>
              <v-col cols="6">
                <v-text-field
                  v-model.number="newTask.actual_hours"
                  label="実績消費工数 (時間)"
                  type="number"
                  min="0"
                  step="0.5"
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                  :disabled="!isEditMode"
                ></v-text-field>
              </v-col>
            </v-row>

            <!-- Preventive Tasks Queue -->
            <div v-if="preventiveTasks.length > 0" class="mb-4">
              <span class="text-caption text-grey">追加される予防タスク:</span>
              <v-chip
                v-for="(pt, idx) in preventiveTasks"
                :key="idx"
                closable
                size="small"
                color="secondary"
                class="ma-1"
                @click:close="preventiveTasks.splice(idx, 1)"
              >
                {{ pt }}
              </v-chip>
            </div>

            <v-row>
              <v-col cols="6">
                <v-select
                  v-model="newTask.priority"
                  label="優先度"
                  :items="['HIGH', 'MEDIUM', 'LOW']"
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                ></v-select>
              </v-col>
              <v-col cols="6">
                <v-select
                  v-model="newTask.assignee_type"
                  label="担当タイプ"
                  :items="['HUMAN', 'AI']"
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                ></v-select>
              </v-col>
            </v-row>

            <!-- NOTE: 担当者は任意の文字列入力となっており、DBのResourceマスタとの外部キー(FK)連携・管理者アサイン除外バリデーションはスコープ外とします。 -->
            <v-text-field
              v-model="newTask.assignee_name"
              label="担当者名 (または AIエージェント名)"
              class="glass-input mb-4"
              variant="solo-filled"
              bg-color="rgba(255,255,255,0.03)"
            ></v-text-field>

            <v-row>
              <v-col cols="6">
                <v-text-field
                  v-model="newTask.planned_start"
                  label="開始日"
                  type="date"
                  required
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                ></v-text-field>
              </v-col>
              <v-col cols="6">
                <v-text-field
                  v-model="newTask.planned_end"
                  label="終了日"
                  type="date"
                  required
                  class="glass-input mb-4"
                  variant="solo-filled"
                  bg-color="rgba(255,255,255,0.03)"
                ></v-text-field>
              </v-col>
            </v-row>

            <v-select
              v-model="newTask.dependency_ids"
              label="先行依存タスク"
              :items="taskOptions"
              item-title="title"
              item-value="id"
              multiple
              class="glass-input mb-4"
              variant="solo-filled"
              bg-color="rgba(255,255,255,0.03)"
            ></v-select>

            <!-- Gitea 連携セクション（編集モード かつ Gitea 設定済みのみ表示） -->
            <div v-if="isEditMode && giteaConfigured" class="mt-4 mb-2">
              <div class="d-flex align-center gap-2 mb-3">
                <v-icon color="grey-lighten-1" size="18">mdi-git</v-icon>
                <span class="text-caption font-weight-bold text-grey-lighten-1">Gitea 連携</span>
              </div>
              <v-select
                v-model="giteaRepo"
                :items="giteaRepos"
                item-title="full_name"
                item-value="full_name"
                label="リポジトリ"
                clearable
                class="glass-input mb-3"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
                placeholder="owner/repo"
              ></v-select>
              <v-text-field
                v-model.number="giteaIssueNumber"
                label="Issue 番号 (任意)"
                type="number"
                min="1"
                clearable
                class="glass-input"
                variant="solo-filled"
                bg-color="rgba(255,255,255,0.03)"
              ></v-text-field>
            </div>
          </v-form>
        </v-card-text>

        <v-card-actions class="d-flex justify-end pt-2">
          <v-btn variant="text" color="grey" @click="createDialog = false">キャンセル</v-btn>
          <v-btn
            variant="flat"
            class="bg-neon-gradient text-white"
            @click="handleSaveTask"
          >
            保存する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useProjectStore } from '../store/project'
import GanttChart from '../components/GanttChart.vue'
import HearingChat from '../components/HearingChat.vue'

const store = useProjectStore()
const selectedTaskId = ref(null)
const createDialog = ref(false)
const projectCreateDialog = ref(false)
const activeTab = ref('wbs')
const errorMessage = ref('')

// Search & filter refs for Task List tab
const searchFilter = ref('')
const projectFilter = ref('ALL')
const statusFilter = ref('ALL')
const priorityFilter = ref('ALL')
const assigneeTypeFilter = ref('ALL')

// Edit mode refs
const isEditMode = ref(false)
const editingTaskId = ref(null)

const giteaConfigured = ref(false)
const giteaRepos = ref([])
const giteaRepo = ref(null)
const giteaIssueNumber = ref(null)

// Project Selector state
const selectedProjectId = ref(null)

const lessonsAdvisorList = ref([])
const preventiveTasks = ref([])

const newProject = ref({
  name: '',
  template_type: 'PHASE_BASED'
})

// AI Planning State Refs
const planningDialog = ref(false)
const planningText = ref('')
const planningProjectMode = ref('existing')
const planningProjectId = ref(null)
const planningNewProject = ref({
  name: '',
  template_type: 'PHASE_BASED'
})
const analyzeResult = ref(null)
const isAnalyzing = ref(false)
const isApplying = ref(false)
const planningErrorMessage = ref('')

const assignableResources = computed(() => {
  return store.resourcesList.filter(r => r.system_role !== '管理者' && r.is_active)
})

const orderedStagingNodes = computed(() => {
  if (!analyzeResult.value || !analyzeResult.value.nodes) return []
  
  const nodes = analyzeResult.value.nodes
  const nodesMap = {}
  nodes.forEach(n => {
    if (n.adopted === undefined) n.adopted = true
    nodesMap[n.temp_id] = { ...n, children: [] }
  })
  
  const roots = []
  Object.values(nodesMap).forEach(n => {
    if (n.parent_temp_id && nodesMap[n.parent_temp_id]) {
      nodesMap[n.parent_temp_id].children.push(n)
    } else {
      roots.push(n)
    }
  })
  
  const flatList = []
  const flatten = (node, depth = 0) => {
    node.depth = depth
    flatList.push(node)
    node.children.forEach(c => flatten(c, depth + 1))
  }
  
  roots.forEach(r => flatten(r, 0))
  return flatList
})

const hasAdoptedNodes = computed(() => {
  if (!analyzeResult.value || !analyzeResult.value.nodes) return false
  return analyzeResult.value.nodes.some(n => n.adopted)
})

const newTask = ref({
  title: '',
  description: '',
  priority: 'MEDIUM',
  assignee_type: 'HUMAN',
  assignee_name: '',
  planned_start: '',
  planned_end: '',
  dependency_ids: [],
  project_id: null,
  node_type: 'TASK',
  parent_id: null,
  estimated_hours: 0,
  actual_hours: 0
})

const taskOptions = computed(() => {
  return store.tasks.map(t => ({ id: t.id, title: t.title }))
})

const projectOptions = computed(() => {
  return store.portfolioProjects.map(p => ({ id: p.id, name: p.name }))
})

// Recursive tree flattener with indentation levels
const getHierarchicalTableTasks = (nodes, depth = 0) => {
  const list = []
  nodes.forEach(node => {
    list.push({
      ...node,
      depth,
      projectName: getProjectName(node.project_id)
    })
    if (node.children && node.children.length > 0) {
      list.push(...getHierarchicalTableTasks(node.children, depth + 1))
    }
  })
  return list
}

const getProjectName = (projectId) => {
  const proj = store.portfolioProjects.find(p => p.id === projectId)
  return proj ? proj.name : '未割当'
}

const filteredTasks = computed(() => {
  return store.tasks.filter(t => {
    // 1. Text Search
    if (searchFilter.value) {
      const query = searchFilter.value.toLowerCase()
      const titleMatch = t.title ? t.title.toLowerCase().includes(query) : false
      const descMatch = t.description ? t.description.toLowerCase().includes(query) : false
      if (!titleMatch && !descMatch) return false
    }
    
    // 2. Project Filter
    if (projectFilter.value && projectFilter.value !== 'ALL') {
      if (t.project_id !== projectFilter.value) return false
    }
    
    // 3. Status Filter
    if (statusFilter.value && statusFilter.value !== 'ALL') {
      if (t.status !== statusFilter.value) return false
    }
    
    // 4. Priority Filter
    if (priorityFilter.value && priorityFilter.value !== 'ALL') {
      if (t.priority !== priorityFilter.value) return false
    }
    
    // 5. Assignee Type Filter
    if (assigneeTypeFilter.value && assigneeTypeFilter.value !== 'ALL') {
      if (t.assignee_type !== assigneeTypeFilter.value) return false
    }
    
    return true
  })
})

const tableTasks = computed(() => {
  const isFiltering = searchFilter.value || 
                       projectFilter.value !== 'ALL' || 
                       statusFilter.value !== 'ALL' || 
                       priorityFilter.value !== 'ALL' || 
                       assigneeTypeFilter.value !== 'ALL'

  if (isFiltering) {
    return filteredTasks.value.map(t => ({
      ...t,
      depth: 0,
      projectName: getProjectName(t.project_id)
    }))
  } else {
    if (store.projectWbsTree && store.projectWbsTree.length > 0) {
      return getHierarchicalTableTasks(store.projectWbsTree)
    } else {
      return store.tasks.map(t => ({
        ...t,
        depth: 0,
        projectName: getProjectName(t.project_id)
      }))
    }
  }
})

// Parent candidate options for selected project tasks (filtered to avoid cycles)
const parentTaskCandidates = computed(() => {
  const projectId = newTask.value.project_id
  if (!projectId) return []

  let candidates = store.tasks.filter(t => t.project_id === projectId)

  if (isEditMode.value && editingTaskId.value) {
    // Filter out target task
    candidates = candidates.filter(t => t.id !== editingTaskId.value)

    // Filter out target task descendants to prevent circular cycles
    const descendants = new Set()
    const findDescendants = (parentId) => {
      const children = store.tasks.filter(t => t.parent_id === parentId)
      children.forEach(c => {
        descendants.add(c.id)
        findDescendants(c.id)
      })
    }
    findDescendants(editingTaskId.value)
    candidates = candidates.filter(t => !descendants.has(t.id))
  }

  return candidates.map(t => ({ id: t.id, title: t.title }))
})

const headers = [
  { title: 'タイトル', key: 'title', sortable: true },
  { title: 'プロジェクト名', key: 'projectName', sortable: true },
  { title: '担当者', key: 'assignee_name', sortable: true },
  { title: 'ステータス', key: 'status', sortable: true },
  { title: '優先度', key: 'priority', sortable: true },
  { title: '開始日', key: 'planned_start', sortable: true },
  { title: '終了日', key: 'planned_end', sortable: true },
  { title: '進捗', key: 'progress', sortable: true },
  { title: '遅延', key: 'delay_days', sortable: true },
  { title: '操作', key: 'actions', sortable: false }
]

const getStatusColor = (status) => {
  switch (status) {
    case 'DONE': return 'success'
    case 'IN_PROGRESS': return 'warning'
    case 'REVIEW': return 'secondary'
    case 'TODO': default: return 'primary'
  }
}

const getStatusLabel = (status) => {
  switch (status) {
    case 'DONE': return '完了'
    case 'IN_PROGRESS': return '対応中'
    case 'REVIEW': return 'レビュー'
    case 'TODO': default: return '未開始'
  }
}

const getPriorityColor = (priority) => {
  switch (priority) {
    case 'HIGH': return 'error'
    case 'MEDIUM': return 'warning'
    case 'LOW': default: return 'grey'
  }
}

const getNodeTypeIcon = (type) => {
  switch (type) {
    case 'PHASE': return 'mdi-layers-outline'
    case 'FEATURE': return 'mdi-star-outline'
    case 'SPRINT': return 'mdi-clock-fast'
    case 'STORY': return 'mdi-book-open-outline'
    case 'TASK': default: return 'mdi-checkbox-blank-circle-outline'
  }
}

const getNodeTypeColor = (type) => {
  switch (type) {
    case 'PHASE': return 'purple'
    case 'FEATURE': return 'amber'
    case 'SPRINT': return 'orange'
    case 'STORY': return 'teal'
    case 'TASK': default: return 'grey'
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return dateStr.split('T')[0]
}

const handleTaskSelect = (taskId) => {
  if (selectedTaskId.value === taskId) {
    selectedTaskId.value = null // toggle close
  } else {
    selectedTaskId.value = taskId
  }
}

const openProjectCreateDialog = () => {
  newProject.value = {
    name: '',
    template_type: 'PHASE_BASED'
  }
  projectCreateDialog.value = true
}

const handleSaveProject = async () => {
  if (!newProject.value.name) return
  try {
    const created = await store.createProject(newProject.value)
    projectCreateDialog.value = false
    if (created && created.id) {
      selectedProjectId.value = created.id
      await store.fetchProjectTree(created.id)
    }
  } catch (err) {
    console.error('Failed to create project:', err)
  }
}

const openAIPlanningDialog = async () => {
  planningDialog.value = true
  planningText.value = ''
  planningProjectMode.value = 'existing'
  planningProjectId.value = selectedProjectId.value || (projectOptions.value.length > 0 ? projectOptions.value[0].id : null)
  planningNewProject.value = {
    name: '',
    template_type: 'PHASE_BASED'
  }
  analyzeResult.value = null
  planningErrorMessage.value = ''
  
  try {
    await store.fetchResources()
  } catch (e) {
    console.error('Failed to fetch resources:', e)
  }
}

const handleAnalyzePlanning = async () => {
  isAnalyzing.value = true
  planningErrorMessage.value = ''
  analyzeResult.value = null
  try {
    const payload = {
      source_text: planningText.value
    }
    if (planningProjectMode.value === 'existing') {
      payload.project_id = planningProjectId.value
    } else {
      payload.new_project = {
        name: planningNewProject.value.name,
        template_type: planningNewProject.value.template_type
      }
    }
    
    const result = await store.analyzePlanning(payload)
    if (result && result.nodes) {
      result.nodes.forEach(n => {
        n.adopted = true
        if (n.suggested_assignee) {
          n.assignee_name = n.suggested_assignee.name
        } else {
          n.assignee_name = ''
        }
      })
    }
    analyzeResult.value = result
  } catch (err) {
    planningErrorMessage.value = err.response?.data?.detail || err.message || 'AI解析に失敗しました。'
  } finally {
    isAnalyzing.value = false
  }
}

const handleApplyPlanning = async () => {
  if (!analyzeResult.value || !analyzeResult.value.nodes) return
  isApplying.value = true
  planningErrorMessage.value = ''
  try {
    const adoptedNodes = analyzeResult.value.nodes.filter(n => n.adopted)
    const payload = {
      nodes: adoptedNodes.map(n => ({
        temp_id: n.temp_id,
        title: n.title,
        description: n.description || '',
        node_type: n.node_type,
        parent_temp_id: n.parent_temp_id,
        estimated_hours: n.estimated_hours || 0,
        assignee_name: n.assignee_name || '',
        assignee_type: 'HUMAN',
        dependencies: n.dependencies || [],
        planned_start: null,
        planned_end: null
      }))
    }
    
    if (planningProjectMode.value === 'existing') {
      payload.project_id = planningProjectId.value
    } else {
      payload.new_project = {
        name: planningNewProject.value.name,
        template_type: planningNewProject.value.template_type
      }
    }
    
    const res = await store.applyPlanning(payload)
    planningDialog.value = false
    
    if (res.project_id) {
      selectedProjectId.value = res.project_id
      await store.fetchProjectTree(res.project_id)
    }
  } catch (err) {
    planningErrorMessage.value = err.response?.data?.detail || err.message || 'WBSの登録に失敗しました。'
  } finally {
    isApplying.value = false
  }
}

const addPreventiveTaskToTree = (pt) => {
  if (!analyzeResult.value || !analyzeResult.value.nodes) return
  
  const firstPhase = analyzeResult.value.nodes.find(n => n.node_type === 'PHASE')
  const parent_temp_id = firstPhase ? firstPhase.temp_id : null
  
  const newTempId = 'preventive_' + Date.now()
  const newNode = {
    temp_id: newTempId,
    title: pt.title,
    description: pt.reason,
    node_type: 'TASK',
    parent_temp_id: parent_temp_id,
    deliverable: '',
    estimated_hours: 8,
    suggested_assignee: null,
    dependencies: [],
    confidence: 1.0,
    adopted: true,
    required_skill: 'General',
    assignee_name: ''
  }
  
  analyzeResult.value.nodes.push(newNode)
}


const openCreateDialog = () => {
  isEditMode.value = false
  editingTaskId.value = null
  lessonsAdvisorList.value = []
  preventiveTasks.value = []
  errorMessage.value = ''
  giteaRepo.value = null
  giteaIssueNumber.value = null
  giteaConfigured.value = false
  newTask.value = {
    title: '',
    description: '',
    priority: 'MEDIUM',
    assignee_type: 'HUMAN',
    assignee_name: '',
    planned_start: new Date().toISOString().split('T')[0],
    planned_end: new Date(Date.now() + 5*24*3600*1000).toISOString().split('T')[0],
    dependency_ids: [],
    project_id: selectedProjectId.value || store.portfolioProjects[0]?.id || null,
    node_type: 'TASK',
    parent_id: null,
    estimated_hours: 0,
    actual_hours: 0
  }
  createDialog.value = true
}

const openEditDialog = (task) => {
  isEditMode.value = true
  editingTaskId.value = task.id
  lessonsAdvisorList.value = []
  preventiveTasks.value = []
  errorMessage.value = ''
  
  newTask.value = {
    title: task.title,
    description: task.description || '',
    priority: task.priority || 'MEDIUM',
    assignee_type: task.assignee_type || 'HUMAN',
    assignee_name: task.assignee_name || '',
    planned_start: formatDate(task.planned_start),
    planned_end: formatDate(task.planned_end),
    dependency_ids: task.dependencies ? task.dependencies.map(d => d.id) : [],
    project_id: task.project_id || null,
    node_type: task.node_type || 'TASK',
    parent_id: task.parent_id || null,
    estimated_hours: task.estimated_hours || 0,
    actual_hours: task.actual_hours || 0
  }
  // Gitea 既存値をセット
  giteaRepo.value = task.gitea_repo || null
  giteaIssueNumber.value = task.gitea_issue_number || null
  // Gitea リポジトリ一覧を取得
  store.fetchGiteaRepos().then(data => {
    giteaConfigured.value = data.configured
    giteaRepos.value = data.repos
  })
  createDialog.value = true
}

const handleDeleteTask = async (task) => {
  if (confirm(`タスク「${task.title}」を削除します。よろしいですか？`)) {
    try {
      await store.deleteTask(task.id)
      if (selectedTaskId.value === task.id) {
        selectedTaskId.value = null
      }
    } catch (err) {
      console.error('Failed to delete task:', err)
    }
  }
}

const openHearingChat = (task) => {
  activeTab.value = 'wbs'
  selectedTaskId.value = task.id
}

const triggerLessonsAdvisor = async () => {
  if (!newTask.value.title) return
  try {
    const lessons = await store.searchLessons(newTask.value.title, newTask.value.description)
    lessonsAdvisorList.value = lessons
  } catch (e) {
    console.error('Failed to run lessons learned search:', e)
  }
}

const addPreventiveSubtask = (lesson) => {
  if (lesson.mitigation_task && !preventiveTasks.value.includes(lesson.mitigation_task)) {
    preventiveTasks.value.push(lesson.mitigation_task)
  }
}

const handleSaveTask = async () => {
  if (!newTask.value.title) return
  errorMessage.value = ''
  
  // Custom description appending the preventive tasks if any
  let finalDescription = newTask.value.description
  if (preventiveTasks.value.length > 0) {
    finalDescription += '\n\n【予防タスク】\n' + preventiveTasks.value.map(pt => `- ${pt}`).join('\n')
  }

  // Parse inputs
  const payload = {
    ...newTask.value,
    description: finalDescription,
    planned_start: new Date(newTask.value.planned_start).toISOString(),
    planned_end: new Date(newTask.value.planned_end).toISOString(),
    assignee_name: newTask.value.assignee_type === 'AI' ? 'AI_WORKER' : newTask.value.assignee_name,
    estimated_hours: parseFloat(newTask.value.estimated_hours) || 0,
    actual_hours: parseFloat(newTask.value.actual_hours) || 0,
    parent_id: newTask.value.parent_id || null
  }
  
  try {
    if (isEditMode.value) {
      await store.updateTask(editingTaskId.value, payload)
      // Gitea 紐付けを保存（編集モードのみ）
      await store.linkTaskGitea(editingTaskId.value, {
        gitea_repo: giteaRepo.value || null,
        gitea_issue_number: giteaIssueNumber.value || null
      })
    } else {
      const created = await store.createTask(payload)
      // If there were preventive tasks, post them as inline subtasks/actions
      if (preventiveTasks.value.length > 0 && created && created.id) {
        for (const pt of preventiveTasks.value) {
          await store.postComment(created.id, `予防タスク追加アラート: WBSの子タスクに「${pt}」を自動追加することを推奨します。`, 'AI_PMO')
        }
      }
    }
    createDialog.value = false
  } catch (err) {
    console.error('Failed to save task:', err)
    errorMessage.value = err.response?.data?.detail || err.message || 'タスクの保存に失敗しました。'
  }
}

const handleApplyPlanB = async () => {
  await store.applyPlanB()
  selectedTaskId.value = null
}

const handleApplyShift = async (conflict) => {
  try {
    await store.applyAllocationShift(
      conflict.delayed_project_id,
      conflict.donor_project_id,
      conflict.resource_name,
      conflict.shift_percent
    )
    store.planBGhostActive = true
  } catch (err) {
    console.error('Failed to apply resource shift:', err)
  }
}

// Watchers for selected project dropdown
watch(selectedProjectId, async (newId) => {
  if (newId) {
    await store.fetchProjectTree(newId)
  }
})

watch(() => store.portfolioProjects, (val) => {
  if (val && val.length > 0 && !selectedProjectId.value) {
    selectedProjectId.value = val[0].id
  }
}, { immediate: true })

watch(activeTab, async (newVal) => {
  if (newVal === 'portfolio') {
    store.fetchPortfolio()
    store.auditPortfolioConflicts()
  } else if (newVal === 'tasklist') {
    store.fetchTasks()
    store.fetchPortfolio()
    if (selectedProjectId.value) {
      await store.fetchProjectTree(selectedProjectId.value)
    }
  } else if (newVal === 'wbs') {
    if (selectedProjectId.value) {
      await store.fetchProjectTree(selectedProjectId.value)
    }
  }
})

onMounted(async () => {
  await store.fetchTasks()
  await store.fetchPortfolio()
  store.auditPortfolioConflicts()
  
  if (selectedProjectId.value) {
    await store.fetchProjectTree(selectedProjectId.value)
  } else if (store.portfolioProjects.length > 0) {
    selectedProjectId.value = store.portfolioProjects[0].id
    await store.fetchProjectTree(selectedProjectId.value)
  }
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
.gap-6 {
  gap: 24px;
}
.transition-width {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.bg-glass {
  background: rgba(255, 255, 255, 0.02);
}
.border-subtle {
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.border-bottom-dashed {
  border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
}
.border-neon-purple {
  border: 1px solid rgba(155, 81, 224, 0.3) !important;
}

/* Glass table custom styling */
:deep(.glass-table) {
  background: transparent !important;
  color: #ffffff !important;
}
:deep(.v-data-table-header) {
  background: rgba(13, 17, 23, 0.6) !important;
}
:deep(.v-data-table-header__content) {
  font-weight: bold !important;
  color: #8f9cae !important;
}
:deep(.v-data-table__tr:hover) {
  background: rgba(255, 255, 255, 0.03) !important;
}
:deep(.v-data-table__tr) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
}
:deep(.v-pagination__item) {
  color: #ffffff !important;
}
:deep(.v-pagination__item--is-active) {
  background: var(--v-primary-base, #00f2fe) !important;
  color: #000000 !important;
}

.glass-inline-input {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 4px 8px;
  outline: none;
  transition: all 0.2s ease;
}
.glass-inline-input:focus {
  background: rgba(255, 255, 255, 0.1);
  border-color: #00f2fe;
  box-shadow: 0 0 5px rgba(0, 242, 254, 0.5);
}
.glass-inline-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.custom-select :deep(.v-field__input) {
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  min-height: 28px !important;
  font-size: 0.75rem !important;
}
</style>
