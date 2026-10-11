import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from './views/Dashboard.vue'
import EmailDetail from './views/EmailDetail.vue'
import Login from './views/Login.vue'
import MailboxDetail from './views/MailboxDetail.vue'
import Mailboxes from './views/Mailboxes.vue'
import Tags from './views/Tags.vue'
import Settings from './views/Settings.vue'
import { hasAccessToken } from './utils/email'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: '管理员登录', component: Login },
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: '运行概览', component: Dashboard, meta: { requiresAuth: true } },
    { path: '/mailboxes', name: '邮箱管理', component: Mailboxes, meta: { requiresAuth: true } },
    { path: '/mailboxes/:id', name: '邮箱详情', component: MailboxDetail, meta: { requiresAuth: true } },
    { path: '/emails/:id', name: '邮件详情', component: EmailDetail, meta: { requiresAuth: true } },
    { path: '/tags', name: '标签管理', component: Tags, meta: { requiresAuth: true } },
    { path: '/settings', name: '系统设置', component: Settings, meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  const authenticated = hasAccessToken()
  if (to.meta.requiresAuth && !authenticated) return '/login'
  if (to.path === '/login' && authenticated) return '/dashboard'
})

export default router
