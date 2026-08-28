<script setup>
import { useRouter } from 'vue-router'
import SearchBar from '../components/SearchBar.vue'

const router = useRouter()
const HOT_WORDS = ['abandon', 'adapt', 'affect', 'begin', 'fast', 'quiet', 'round', 'swift']

function jump(word) {
  router.push({ name: 'word', params: { word } })
}
</script>

<template>
  <div class="home">
    <h1 class="home-title">单词速查</h1>
    <p class="home-sub">考研英语大纲词汇 · 搜索即服务，详情即网络</p>

    <SearchBar large />

    <div class="home-tags">
      <button v-for="w in HOT_WORDS" :key="w" class="home-tag" @click="jump(w)">
        {{ w }}
      </button>
    </div>
  </div>
</template>
