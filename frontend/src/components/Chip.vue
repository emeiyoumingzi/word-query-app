<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  item: { type: Object, required: true }, // { word, pos, meaning }
})

const router = useRouter()

function go() {
  if (!props.item?.word) return
  router.push({ name: 'word', params: { word: props.item.word } })
}
</script>

<template>
  <button class="chip" :title="item.word" @click="go">
    <span class="chip-word">{{ item.word }}</span>
    <span v-if="item.pos" class="pos">{{ item.pos }}</span>
    <span v-if="item.meaning" class="chip-tip">{{ item.meaning }}</span>
  </button>
</template>

<style scoped>
.chip-word {
  color: inherit;
}
</style>
