import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import GanttView from '../views/GanttView.vue'
import KnowledgeView from '../views/KnowledgeView.vue'
import ArtifactsView from '../views/ArtifactsView.vue'
import AdminView from '../views/AdminView.vue'
import Login from '../views/Login.vue'
import { useProjectStore } from '../store/project'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard
  },
  {
    path: '/gantt',
    name: 'GanttView',
    component: GanttView
  },
  {
    path: '/knowledge',
    name: 'KnowledgeView',
    component: KnowledgeView
  },
  {
    path: '/artifacts',
    name: 'ArtifactsView',
    component: ArtifactsView
  },
  {
    path: '/admin',
    name: 'AdminView',
    component: AdminView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const store = useProjectStore()
  
  // 1. If token exists but currentUser is not loaded, fetch it
  if (store.token && !store.currentUser) {
    try {
      await store.fetchMe()
    } catch (err) {
      console.error('Failed to restore user from token:', err)
      store.logout()
    }
  }
  
  const isAuthenticated = !!store.token
  
  if (to.path !== '/login' && !isAuthenticated) {
    // Redirect to login if not authenticated
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if (to.path === '/login' && isAuthenticated) {
    // Redirect to home if already logged in
    next('/')
  } else if (to.path === '/admin' && store.currentRole === 'メンバー') {
    // Prevent members from visiting System Management panel
    next('/')
  } else if (to.path === '/gantt') {
    // Preload WBS data BEFORE rendering the gantt view, so the SVAR Gantt mounts
    // exactly once with data already present (it crashes on any later re-mount).
    try {
      if (!store.portfolioProjects || store.portfolioProjects.length === 0) {
        await store.fetchPortfolio()
      }
      await store.fetchTasks()
      const pid = to.query.project || (store.portfolioProjects[0] && store.portfolioProjects[0].id)
      if (pid) await store.fetchProjectTree(pid)
    } catch (e) {
      // Non-fatal: the view will show an empty state.
    }
    next()
  } else {
    next()
  }
})

export default router
