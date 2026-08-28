<script setup>
import DesktopWidget from './components/DesktopWidget.vue'
</script>

<template>
  <DesktopWidget />
</template>

<style>
/* 桌面小组件窗口：透明背景，圆角悬浮条 */
html,
body {
  margin: 0;
  padding: 0;
  background: transparent;
  overflow: hidden;
}
</style>
