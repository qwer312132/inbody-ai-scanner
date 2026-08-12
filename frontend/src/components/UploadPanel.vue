<script setup>
import { ref } from 'vue'
import axios from 'axios'

// 接收來自父元件 (App.vue) 的 userName
const props = defineProps({
  userName: String
})

const selectedFile = ref(null)
const isLoading = ref(false)
const resultData = ref(null)
const errorMessage = ref('')

const handleFileChange = (event) => {
  selectedFile.value = event.target.files[0]
}

const uploadVideo = async () => {
  if (!props.userName || !selectedFile.value) {
    errorMessage.value = "請確認已輸入名稱並選擇影片！"
    return
  }
  
  const formData = new FormData()
  formData.append('user_name', props.userName) // 使用 props.userName
  formData.append('file', selectedFile.value)

  isLoading.value = true
  errorMessage.value = ''
  resultData.value = null

  try {
    const response = await axios.post('/api/analyze', formData)
    resultData.value = response.data.data
  } catch (error) {
    errorMessage.value = error.response?.data?.message || "分析失敗，請檢查後端。"
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="upload-panel">
    <div class="input-group">
      <label>上傳影片：</label>
      <input type="file" accept="video/mp4,video/avi,video/mov" @change="handleFileChange" />
    </div>
    
    <button class="action-btn upload-btn" @click="uploadVideo" :disabled="isLoading">
      {{ isLoading ? 'AI 視覺分析中...' : '開始分析' }}
    </button>
    <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>

    <div v-if="resultData" class="data-grid">
      <div v-for="(value, key) in resultData" :key="key" class="data-item">
        <span class="data-key">{{ key }}</span>
        <span class="data-value">{{ value }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 這裡只放上傳面板專屬的 CSS */
.upload-panel { margin-top: 1rem; }
.input-group { margin-bottom: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.action-btn { width: 100%; padding: 1rem; color: white; border: none; border-radius: 8px; font-size: 1.1rem; font-weight: bold; cursor: pointer; transition: 0.2s; }
.upload-btn { background-color: #42b883; }
.upload-btn:hover:not(:disabled) { background-color: #33a06f; }
.action-btn:disabled { background-color: #bdc3c7; cursor: not-allowed; }
.error-msg { color: #e74c3c; margin-top: 1rem; font-weight: bold; text-align: center; }
.data-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; margin-top: 1.5rem; }
.data-item { background: #f8f9fa; padding: 1rem; border-radius: 8px; display: flex; flex-direction: column; align-items: center; border-left: 4px solid #42b883; }
.data-key { font-size: 0.85rem; color: #666; margin-bottom: 0.5rem; }
.data-value { font-size: 1.4rem; font-weight: bold; color: #2c3e50; }
</style>