<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  PointElement, LineElement, Title, Tooltip, Legend
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

// 同樣接收來自父元件的 userName
const props = defineProps({
  userName: String
})

const isFetchingHistory = ref(false)
const historyMessage = ref('')
const chartData = ref(null)

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'top' }, title: { display: true, text: '測量趨勢' } }
}

const fetchHistory = async () => {
  if (!props.userName) {
    historyMessage.value = "請先輸入要查詢的測量者名稱！"
    return
  }
  
  isFetchingHistory.value = true
  historyMessage.value = ''
  chartData.value = null

  try {
    const response = await axios.get(`http://localhost:8000/api/records/${props.userName}`)
    const history = response.data.history
    
    if (history.length === 0) {
      historyMessage.value = `找不到「${props.userName}」的歷史紀錄。`
      return
    }

    const labels = history.map(row => row.record_time.split(' ')[0])
    const weightData = history.map(row => row.weight)
    const bodyFatData = history.map(row => row.body_fat)

    chartData.value = {
      labels: labels,
      datasets: [
        { label: '體重 (kg)', backgroundColor: '#3498db', borderColor: '#3498db', data: weightData, tension: 0.3 },
        { label: '體脂率 (%)', backgroundColor: '#e74c3c', borderColor: '#e74c3c', data: bodyFatData, tension: 0.3 }
      ]
    }
  } catch (error) {
    historyMessage.value = "無法取得歷史紀錄。"
  } finally {
    isFetchingHistory.value = false
  }
}
</script>

<template>
  <div class="history-chart">
    <button class="action-btn query-btn" @click="fetchHistory" :disabled="isFetchingHistory">
      {{ isFetchingHistory ? '查詢中...' : '載入歷史圖表' }}
    </button>
    <p v-if="historyMessage" class="error-msg">{{ historyMessage }}</p>

    <div v-if="chartData" class="chart-container">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<style scoped>
.history-chart { margin-top: 1rem; }
.action-btn { width: 100%; padding: 1rem; color: white; border: none; border-radius: 8px; font-size: 1.1rem; font-weight: bold; cursor: pointer; transition: 0.2s; }
.query-btn { background-color: #3498db; }
.query-btn:hover:not(:disabled) { background-color: #2980b9; }
.action-btn:disabled { background-color: #bdc3c7; cursor: not-allowed; }
.error-msg { color: #e74c3c; margin-top: 1rem; font-weight: bold; text-align: center; }
.chart-container { position: relative; height: 400px; width: 100%; margin-top: 1.5rem; }
</style>