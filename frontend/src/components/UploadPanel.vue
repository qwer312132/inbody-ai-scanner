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
const uploadProgress = ref(0)
const uploadPhase = ref('')

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
  uploadProgress.value = 0
  uploadPhase.value = 'uploading'

  try {
    const response = await axios.post('/api/analyze', formData, {
      onUploadProgress: (event) => {
        if (!event.total) return

        uploadProgress.value = Math.round((event.loaded * 100) / event.total)
        if (uploadProgress.value >= 100) {
          uploadPhase.value = 'analyzing'
        }
      }
    })
    resultData.value = response.data.data
  } catch (error) {
    errorMessage.value = error.response?.data?.message || "分析失敗，請檢查後端。"
  } finally {
    isLoading.value = false
    uploadPhase.value = ''
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
    <div v-if="isLoading" class="progress-section" aria-live="polite">
      <div class="progress-label">
        <span v-if="uploadPhase === 'uploading'">影片上傳中</span>
        <span v-else>影片已送出，AI 分析中</span>
        <span v-if="uploadPhase === 'uploading'">{{ uploadProgress }}%</span>
      </div>
      <div class="progress-track" role="progressbar" :aria-valuenow="uploadPhase === 'uploading' ? uploadProgress : undefined" aria-valuemin="0" aria-valuemax="100">
        <div
          class="progress-bar"
          :class="{ analyzing: uploadPhase === 'analyzing' }"
          :style="uploadPhase === 'uploading' ? { width: `${uploadProgress}%` } : undefined"
        ></div>
      </div>
    </div>
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
.progress-section { margin-top: 1rem; }
.progress-label { display: flex; justify-content: space-between; margin-bottom: 0.4rem; color: #52616b; font-size: 0.9rem; }
.progress-track { height: 0.7rem; overflow: hidden; border-radius: 999px; background: #e9eef0; }
.progress-bar { height: 100%; border-radius: inherit; background: #42b883; transition: width 0.2s ease; }
.progress-bar.analyzing { width: 45%; animation: analyzing-progress 1.25s ease-in-out infinite; }
@keyframes analyzing-progress { 0% { transform: translateX(-100%); } 100% { transform: translateX(325%); } }
.error-msg { color: #e74c3c; margin-top: 1rem; font-weight: bold; text-align: center; }
.data-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; margin-top: 1.5rem; }
.data-item { background: #f8f9fa; padding: 1rem; border-radius: 8px; display: flex; flex-direction: column; align-items: center; border-left: 4px solid #42b883; }
.data-key { font-size: 0.85rem; color: #666; margin-bottom: 0.5rem; }
.data-value { font-size: 1.4rem; font-weight: bold; color: #2c3e50; }
</style>
