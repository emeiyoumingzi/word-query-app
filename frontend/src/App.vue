<script setup>
import { onMounted } from 'vue'
import { applyFontScale, settings } from './settings'
import WordWidget from './components/WordWidget.vue'
import NotesPanel from './components/NotesPanel.vue'
import FavoritesPanel from './components/FavoritesPanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'

applyFontScale()
onMounted(applyFontScale)
</script>

<template>
  <router-view v-slot="{ Component }">
    <Transition name="page" mode="out-in">
      <component :is="Component" />
    </Transition>
  </router-view>
  <WordWidget v-if="settings.widgetEnabled" />
  <NotesPanel />
  <FavoritesPanel />
  <SettingsPanel />
</template>
