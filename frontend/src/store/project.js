import { defineStore } from 'pinia'
import axios from 'axios'

const API_BASE = 'http://localhost:8008/api/v1'

// Request interceptor to add Authorization header dynamically
axios.interceptors.request.use((config) => {
  try {
    const store = useProjectStore()
    if (store.token) {
      config.headers['Authorization'] = `Bearer ${store.token}`
    }
  } catch (e) {
    // Pinia might not be initialized yet
  }
  return config
}, (error) => {
  return Promise.reject(error)
})

// Response interceptor to handle 401 unauthorized errors
axios.interceptors.response.use((response) => {
  return response
}, (error) => {
  if (error.response && error.response.status === 401) {
    try {
      const store = useProjectStore()
      store.logout()
    } catch (e) {
      // ignore
    }
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  }
  return Promise.reject(error)
})

export const useProjectStore = defineStore('project', {
  state: () => ({
    tasks: [],
    messages: {}, // key by taskId, and 'general'
    knowledges: [],
    standupSummary: {
      ai_completed_summary: [],
      top_actions: []
    },
    comments: [],
    planBGhostActive: false,
    portfolioProjects: [],
    portfolioConflicts: [],
    executiveSummary: null,
    lessonsLearnedProposals: [],
    loading: false,
    error: null,
    token: localStorage.getItem('token') || '',
    currentUser: null,
    currentRole: null,
    resourcesList: [],
    calendarHolidays: [],
    projectWbsTree: [],
    currentProjectId: null,
    wbsTreeRevision: 0
  }),
  
  getters: {
    getMessagesByTask: (state) => (taskId) => {
      const key = taskId || 'general'
      return state.messages[key] || []
    }
  },
  
  actions: {
    async fetchTasks() {
      this.loading = true
      try {
        const response = await axios.get(`${API_BASE}/tasks/`)
        this.tasks = response.data
        // Check if there are any tasks with active plan_b different from planned
        const hasPlanB = this.tasks.some(
          t => t.plan_b_start && t.plan_b_end && 
               (t.plan_b_start !== t.planned_start || t.plan_b_end !== t.planned_end)
        )
        this.planBGhostActive = hasPlanB
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async createTask(taskData) {
      try {
        const response = await axios.post(`${API_BASE}/tasks/`, taskData)
        await this.fetchTasks()
        await this.fetchStandupSummary()
        await this.fetchPortfolio()
        if (this.currentProjectId) {
          await this.fetchProjectTree(this.currentProjectId)
        }
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    
    async updateTask(taskId, taskData) {
      this.loading = true
      try {
        const response = await axios.put(`${API_BASE}/tasks/${taskId}`, taskData)
        await this.fetchTasks()
        await this.fetchStandupSummary()
        await this.fetchPortfolio()
        if (this.currentProjectId) {
          await this.fetchProjectTree(this.currentProjectId)
        }
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async deleteTask(taskId) {
      this.loading = true
      try {
        const response = await axios.delete(`${API_BASE}/tasks/${taskId}`)
        await this.fetchTasks()
        await this.fetchStandupSummary()
        await this.fetchPortfolio()
        if (this.currentProjectId) {
          await this.fetchProjectTree(this.currentProjectId)
        }
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async approvePlan(taskId) {
      try {
        await axios.post(`${API_BASE}/tasks/${taskId}/approve-plan`)
        await this.fetchTasks()
        await this.fetchStandupSummary()
      } catch (err) {
        this.error = err.message
      }
    },
    
    async rejectPlan(taskId) {
      try {
        await axios.post(`${API_BASE}/tasks/${taskId}/reject-plan`)
        await this.fetchTasks()
        await this.fetchStandupSummary()
      } catch (err) {
        this.error = err.message
      }
    },
    
    async fetchStandupSummary() {
      try {
        const response = await axios.get(`${API_BASE}/standup/summary`)
        this.standupSummary = response.data
      } catch (err) {
        this.error = err.message
      }
    },
    
    async submitHearing(taskId, text) {
      try {
        const response = await axios.post(`${API_BASE}/plan-b/hearing/${taskId}`, {
          remaining_text: text
        })
        await this.fetchTasks()
        await this.fetchMessages(taskId)
        this.planBGhostActive = true
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    
    async applyPlanB() {
      try {
        await axios.post(`${API_BASE}/plan-b/apply-plan-b`)
        await this.fetchTasks()
        this.planBGhostActive = false
      } catch (err) {
        this.error = err.message
      }
    },
    
    async fetchMessages(taskId = null) {
      const key = taskId || 'general'
      try {
        const params = taskId ? { task_id: taskId } : {}
        const response = await axios.get(`${API_BASE}/messages/`, { params })
        this.messages[key] = response.data
      } catch (err) {
        this.error = err.message
      }
    },
    
    async sendMessage(senderType, senderName, content, taskId = null) {
      const key = taskId || 'general'
      try {
        const payload = {
          sender_type: senderType,
          sender_name: senderName,
          content: content,
          task_id: taskId
        }
        const response = await axios.post(`${API_BASE}/messages/`, payload)
        if (!this.messages[key]) {
          this.messages[key] = []
        }
        this.messages[key].push(response.data)
        return response.data
      } catch (err) {
        this.error = err.message
      }
    },
    
    async fetchKnowledge() {
      try {
        const response = await axios.get(`${API_BASE}/knowledge/`)
        this.knowledges = response.data
      } catch (err) {
        this.error = err.message
      }
    },
    
    async updateKnowledgeStatus(id, status) {
      try {
        await axios.put(`${API_BASE}/knowledge/${id}`, { status })
        await this.fetchKnowledge()
      } catch (err) {
        this.error = err.message
      }
    },
    
    async deleteKnowledge(id) {
      try {
        await axios.delete(`${API_BASE}/knowledge/${id}`)
        await this.fetchKnowledge()
      } catch (err) {
        this.error = err.message
      }
    },
    
    async triggerNightlyCrawl() {
      this.loading = true
      try {
        await axios.post(`${API_BASE}/knowledge/nightly-crawl`)
        await this.fetchKnowledge()
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async fetchComments(taskId = null) {
      try {
        const params = taskId ? { task_id: taskId } : {}
        const response = await axios.get(`${API_BASE}/comments/`, { params })
        this.comments = response.data
      } catch (err) {
        this.error = err.message
      }
    },
    
    async postComment(taskId, content, author, lineNumber = null) {
      try {
        const response = await axios.post(`${API_BASE}/comments/`, {
          task_id: taskId,
          content,
          author,
          line_number: lineNumber
        })
        this.comments.push(response.data)
        return response.data
      } catch (err) {
        this.error = err.message
      }
    },
    
    async executeCommand(commandText) {
      try {
        const response = await axios.post(`${API_BASE}/command/execute`, {
          command: commandText
        })
        await this.fetchTasks()
        await this.fetchStandupSummary()
        return response.data
      } catch (err) {
        this.error = err.message
        return { success: false, message: `コマンド実行エラー: ${err.message}` }
      }
    },
    
    async updateTaskDates(taskId, start, end, isPlanB = false) {
      try {
        const payload = isPlanB ? {
          plan_b_start: new Date(start).toISOString(),
          plan_b_end: new Date(end).toISOString()
        } : {
          planned_start: new Date(start).toISOString(),
          planned_end: new Date(end).toISOString()
        }
        const response = await axios.put(`${API_BASE}/tasks/${taskId}`, payload)
        await this.fetchTasks()
        if (this.currentProjectId) {
          await this.fetchProjectTree(this.currentProjectId)
        }
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    
    async fetchTaskArtifact(taskId) {
      this.loading = true
      try {
        const response = await axios.get(`${API_BASE}/tasks/${taskId}/artifacts`)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async applyArtifactFix(taskId, lineNumber) {
      this.loading = true
      try {
        const response = await axios.post(`${API_BASE}/tasks/${taskId}/artifacts/apply-fix`, {
          line_number: lineNumber
        })
        await this.fetchComments(taskId)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async fetchPortfolio() {
      this.loading = true
      try {
        const response = await axios.get(`${API_BASE}/pmo/portfolio`)
        this.portfolioProjects = response.data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async auditPortfolioConflicts() {
      this.loading = true
      try {
        const response = await axios.post(`${API_BASE}/pmo/portfolio/audit-conflict`)
        this.portfolioConflicts = response.data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async applyAllocationShift(delayedProjectId, donorProjectId, resourceName, shiftPercent) {
      this.loading = true
      try {
        await axios.post(`${API_BASE}/pmo/portfolio/apply-allocation-shift`, {
          delayed_project_id: delayedProjectId,
          donor_project_id: donorProjectId,
          resource_name: resourceName,
          shift_percent: shiftPercent
        })
        await this.fetchPortfolio()
        await this.auditPortfolioConflicts()
      } catch (err) {
        this.error = err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async runGovernanceAudit(taskId, content) {
      this.loading = true
      try {
        const response = await axios.post(`${API_BASE}/pmo/governance/audit-document`, {
          task_id: taskId,
          content
        })
        await this.fetchComments(taskId)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async fetchExecutiveSummary() {
      this.loading = true
      try {
        const response = await axios.get(`${API_BASE}/pmo/executive-report/summary`)
        this.executiveSummary = response.data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async searchLessons(title, description) {
      this.loading = true
      try {
        const response = await axios.post(`${API_BASE}/pmo/lessons/search-lesson`, {
          title,
          description
        })
        this.lessonsLearnedProposals = response.data
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      } finally {
        this.loading = false
      }
    },

    async login(email, password) {
      this.loading = true
      this.error = null
      try {
        const response = await axios.post(`${API_BASE}/auth/login`, { email, password })
        this.token = response.data.access_token
        localStorage.setItem('token', this.token)
        this.currentUser = {
          id: response.data.user.id,
          name: response.data.user.name,
          email: response.data.user.email,
          role: response.data.user.role
        }
        this.currentRole = response.data.user.system_role
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    logout() {
      this.token = ''
      this.currentUser = null
      this.currentRole = null
      localStorage.removeItem('token')
    },
    
    async fetchMe() {
      if (!this.token) return
      this.loading = true
      try {
        const response = await axios.get(`${API_BASE}/auth/me`)
        this.currentUser = {
          id: response.data.id,
          name: response.data.name,
          email: response.data.email,
          role: response.data.role
        }
        this.currentRole = response.data.system_role
      } catch (err) {
        this.logout()
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async fetchResources() {
      this.loading = true
      try {
        const response = await axios.get(`${API_BASE}/resources/`)
        this.resourcesList = response.data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async fetchResourcesNLP(query) {
      this.loading = true
      try {
        const response = await axios.get(`${API_BASE}/resources/search`, { params: { query } })
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async createResource(resourceData) {
      this.loading = true
      try {
        await axios.post(`${API_BASE}/resources/`, resourceData)
        await this.fetchResources()
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async updateResource(resourceId, resourceData) {
      this.loading = true
      try {
        await axios.put(`${API_BASE}/resources/${resourceId}`, resourceData)
        await this.fetchResources()
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async deleteResource(resourceId) {
      this.loading = true
      try {
        await axios.delete(`${API_BASE}/resources/${resourceId}`)
        await this.fetchResources()
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async fetchHolidays(year = null) {
      this.loading = true
      try {
        const params = year ? { year } : {}
        const response = await axios.get(`${API_BASE}/calendar/holidays`, { params })
        this.calendarHolidays = response.data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async createHoliday(holidayData) {
      this.loading = true
      try {
        await axios.post(`${API_BASE}/calendar/holidays`, holidayData)
        await this.fetchHolidays(holidayData.year)
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async updateHoliday(holidayId, holidayData) {
      this.loading = true
      try {
        await axios.put(`${API_BASE}/calendar/holidays/${holidayId}`, holidayData)
        await this.fetchHolidays(holidayData.year)
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async deleteHoliday(holidayId, year = null) {
      this.loading = true
      try {
        await axios.delete(`${API_BASE}/calendar/holidays/${holidayId}`)
        await this.fetchHolidays(year)
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async syncPublicHolidays(year) {
      this.loading = true
      try {
        await axios.post(`${API_BASE}/calendar/sync-public-holidays`, { year })
        await this.fetchHolidays(year)
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async fetchProjectTree(projectId) {
      if (!projectId) return
      this.loading = true
      try {
        const response = await axios.get(`${API_BASE}/projects/${projectId}/tree`)
        this.projectWbsTree = response.data
        this.currentProjectId = projectId
        this.wbsTreeRevision++
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },
    
    async createProject(projectData) {
      this.loading = true
      try {
        const response = await axios.post(`${API_BASE}/projects/`, projectData)
        await this.fetchPortfolio()
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },

    async analyzePlanning(payload) {
      this.loading = true
      try {
        const response = await axios.post(`${API_BASE}/planning/analyze`, payload)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },

    async applyPlanning(payload) {
      this.loading = true
      try {
        const response = await axios.post(`${API_BASE}/planning/apply`, payload)
        const projId = response.data.project_id || payload.project_id
        if (projId) {
          await this.fetchProjectTree(projId)
        }
        await this.fetchTasks()
        await this.fetchPortfolio()
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchGiteaRepos() {
      const res = await axios.get(`${API_BASE}/gitea/repos`)
      return res.data  // { repos: [...], configured: bool }
    },

    async linkTaskGitea(taskId, { gitea_repo, gitea_issue_number }) {
      const res = await axios.patch(`${API_BASE}/gitea/${taskId}/gitea-link`, { gitea_repo, gitea_issue_number })
      return res.data
    }
  }
})

