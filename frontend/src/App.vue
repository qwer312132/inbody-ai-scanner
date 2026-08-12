<script setup>
import { ref } from 'vue'
// 引入我們寫好的兩個子元件
import UploadPanel from './components/UploadPanel.vue'
import HistoryChart from './components/HistoryChart.vue'

const activeTab = ref('upload')
const userName = ref('')
</script>

<template>
  <div class="container">
    <h1 class="title">🏃‍♂️ InBody AI 掃描器</h1>
    
    <div class="card global-input">
      <label>請輸入測量者名稱：</label>
      <input v-model="userName" type="text" placeholder="例如：爸爸" />
    </div>
    
    <div class="tabs">
      <button :class="{ active: activeTab === 'upload' }" @click="activeTab = 'upload'">📤 新增測量 (上傳)</button>
      <button :class="{ active: activeTab === 'history' }" @click="activeTab = 'history'">📈 歷史追蹤 (圖表)</button>
    </div>

    <!-- 
      使用子元件，並透過 :userName="userName" 
      把父元件的使用者名稱即時傳遞給子元件！
    -->
    <div class="card">
      <UploadPanel v-show="activeTab === 'upload'" :userName="userName" />
      <HistoryChart v-show="activeTab === 'history'" :userName="userName" />
    </div>
  </div>
</template>

<style scoped>
/* 這裡只留大框架的 CSS */
.container { max-width: 800px; margin: 0 auto; padding: 2rem; font-family: 'Segoe UI', sans-serif; color: #333; }
.title { text-align: center; color: #2c3e50; margin-bottom: 1.5rem; }
.card { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 1rem; }
.global-input { display: flex; flex-direction: column; gap: 0.5rem; }
.global-input input { padding: 0.75rem; border: 1px solid #ccc; border-radius: 6px; font-size: 1.1rem; }
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.tabs button { flex: 1; padding: 0.75rem; border: none; background: #e0e0e0; border-radius: 8px; font-size: 1rem; cursor: pointer; transition: 0.3s; }
.tabs button.active { background: #34495e; color: white; font-weight: bold; }
</style>