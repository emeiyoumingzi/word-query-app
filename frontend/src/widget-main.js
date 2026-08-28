// 桌面小组件专用入口（Electron 壳或浏览器直接打开 widget.html）
import { createApp } from 'vue'
import AppWidget from './AppWidget.vue'
import './styles/main.css'
import './styles/widget.css'

createApp(AppWidget).mount('#widget-app')
