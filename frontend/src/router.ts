import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from './views/Dashboard.vue'
import EmailDetail from './views/EmailDetail.vue'
import Login from './views/Login.vue'
import MailboxDetail from './views/MailboxDetail.vue'
import Mailboxes from './views/Mailboxes.vue'
import Tags from './views/Tags.vue'
import { hasAccessToken } from './utils/email'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: Dashboard, meta: { requiresAuth: true } },
    { path: '/mailboxes', component: Mailboxes, meta: { requiresAuth: true } },
    { path: '/mailboxes/:id', component: MailboxDetail, meta: { requiresAuth: true } },
    { path: '/emails/:id', component: EmailDetail, meta: { requiresAuth: true } },
    { path: '/tags', component: Tags, meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  const authenticated = hasAccessToken()
  if (to.meta.requiresAuth && !authenticated) return '/login'
  if (to.path === '/login' && authenticated) return '/dashboard'
})

export default router
