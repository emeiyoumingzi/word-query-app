import { createRouter, createWebHistory } from 'vue-router'
import SearchHome from '../views/SearchHome.vue'
import WordDetail from '../views/WordDetail.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: SearchHome },
    { path: '/word/:word', name: 'word', component: WordDetail, props: true },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

export default router
