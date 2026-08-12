<script setup>
import { computed, ref } from 'vue'
import axios from 'axios'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  PointElement, LineElement, Title, Tooltip, Legend
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const props = defineProps({
  userName: String
})

const METRICS = [
  { key: 'weight', label: '體重', unit: 'kg' },
  { key: 'bmi', label: 'BMI', unit: '' },
  { key: 'body_fat', label: '體脂肪率', unit: '%' },
  { key: 'visceral_fat', label: '內臟脂肪', unit: '' },
  { key: 'bmr', label: '基礎代謝率', unit: 'kcal' },
  { key: 'body_age', label: '身體年齡', unit: '歲' },
  { key: 'subfat_whole', label: '皮下脂肪（全身）', unit: '' },
  { key: 'subfat_trunk', label: '皮下脂肪（軀幹）', unit: '' },
  { key: 'subfat_arms', label: '皮下脂肪（手臂）', unit: '' },
  { key: 'subfat_legs', label: '皮下脂肪（腿部）', unit: '' },
  { key: 'muscle_whole', label: '骨骼肌（全身）', unit: '' },
  { key: 'muscle_trunk', label: '骨骼肌（軀幹）', unit: '' },
  { key: 'muscle_arms', label: '骨骼肌（手臂）', unit: '' },
  { key: 'muscle_legs', label: '骨骼肌（腿部）', unit: '' }
]

const isFetchingHistory = ref(false)
const historyMessage = ref('')
const history = ref([])
const selectedMetric = ref('weight')

const selectedMetricInfo = computed(() =>
  METRICS.find(metric => metric.key === selectedMetric.value) ?? METRICS[0]
)

const chartData = computed(() => {
  if (history.value.length === 0) return null

  let previousValue = 0
  const filledValues = []
  const values = history.value.map(row => {
    const rawValue = row[selectedMetric.value]
    const value = Number(rawValue)
    const isMissing = rawValue === null || rawValue === undefined || rawValue === '' ||
      !Number.isFinite(value) || value === -1

    if (isMissing) {
      filledValues.push(true)
      return previousValue
    }

    filledValues.push(false)
    previousValue = value
    return value
  })

  const metric = selectedMetricInfo.value
  const label = metric.unit ? `${metric.label} (${metric.unit})` : metric.label

  return {
    labels: history.value.map(row => row.record_time.split(' ')[0]),
    datasets: [{
      label,
      data: values,
      borderColor: '#3498db',
      backgroundColor: '#3498db',
      pointBackgroundColor: filledValues.map(isFilled => isFilled ? '#f39c12' : '#3498db'),
      pointBorderColor: filledValues.map(isFilled => isFilled ? '#d35400' : '#3498db'),
      pointRadius: filledValues.map(isFilled => isFilled ? 6 : 4),
      tension: 0.3
    }]
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'top' },
    title: { display: true, text: `${selectedMetricInfo.value.label}歷史紀錄` },
    tooltip: {
      callbacks: {
        afterLabel: context => context.dataset.pointBackgroundColor[context.dataIndex] === '#f39c12'
          ? '未辨識到：已以前一次數值補上'
          : ''
      }
    }
  }
}))

const fetchHistory = async () => {
  if (!props.userName) {
    historyMessage.value = '請先輸入姓名，再查詢歷史紀錄。'
    return
  }

  isFetchingHistory.value = true
  historyMessage.value = ''
  history.value = []

  try {
    const response = await axios.get(`/api/records/${encodeURIComponent(props.userName)}`)
    history.value = response.data.history

    if (history.value.length === 0) {
      historyMessage.value = `${props.userName} 尚無歷史紀錄。`
    }
  } catch (error) {
    historyMessage.value = '無法取得歷史紀錄，請確認後端服務是否啟動。'
  } finally {
    isFetchingHistory.value = false
  }
}
</script>

<template>
  <div class="history-chart">
    <button class="action-btn query-btn" @click="fetchHistory" :disabled="isFetchingHistory">
      {{ isFetchingHistory ? '查詢中...' : '查詢歷史紀錄' }}
    </button>
    <p v-if="historyMessage" class="error-msg">{{ historyMessage }}</p>

    <template v-if="chartData">
      <label class="metric-selector">
        顯示項目
        <select v-model="selectedMetric">
          <option v-for="metric in METRICS" :key="metric.key" :value="metric.key">
            {{ metric.label }}{{ metric.unit ? ` (${metric.unit})` : '' }}
          </option>
        </select>
      </label>
      <p class="chart-note">橘色點代表該次未辨識到數值，已用前一次數值補上；第一筆則以 0 補上。</p>
      <div class="chart-container">
        <Line :data="chartData" :options="chartOptions" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.history-chart { margin-top: 1rem; }
.action-btn { width: 100%; padding: 1rem; color: white; border: none; border-radius: 8px; font-size: 1.1rem; font-weight: bold; cursor: pointer; transition: 0.2s; }
.query-btn { background-color: #3498db; }
.query-btn:hover:not(:disabled) { background-color: #2980b9; }
.action-btn:disabled { background-color: #bdc3c7; cursor: not-allowed; }
.error-msg { color: #e74c3c; margin-top: 1rem; font-weight: bold; text-align: center; }
.metric-selector { display: flex; align-items: center; gap: 0.75rem; margin-top: 1.5rem; font-weight: bold; }
.metric-selector select { flex: 1; padding: 0.6rem; border: 1px solid #bdc3c7; border-radius: 6px; font-size: 1rem; }
.chart-note { color: #7f8c8d; font-size: 0.9rem; margin: 0.75rem 0 0; }
.chart-container { position: relative; height: 400px; width: 100%; margin-top: 0.75rem; }
</style>
