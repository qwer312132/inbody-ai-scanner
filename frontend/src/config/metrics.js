/**
 * Single source of truth for metric ordering, labels, and API field mappings.
 * `key` is used by history records; `analysisKey` is returned by the AI API.
 */
export const METRICS = [
  { key: 'weight', analysisKey: 'Weight', label: '體重', unit: 'kg' },
  { key: 'body_fat', analysisKey: 'Body Fat', label: '體脂肪率', unit: '%' },
  { key: 'visceral_fat', analysisKey: 'Visceral Fat', label: '內臟脂肪', unit: '' },
  { key: 'bmr', analysisKey: 'BMR', label: '基礎代謝率', unit: 'kcal' },
  { key: 'bmi', analysisKey: 'BMI', label: 'BMI', unit: '' },
  { key: 'body_age', analysisKey: 'Body Age', label: '身體年齡', unit: '歲' },
  { key: 'subfat_whole', analysisKey: 'Subcutaneous Fat (Whole Body)', label: '皮下脂肪（全身）', unit: '' },
  { key: 'subfat_trunk', analysisKey: 'Subcutaneous Fat (Trunk)', label: '皮下脂肪（軀幹）', unit: '' },
  { key: 'subfat_arms', analysisKey: 'Subcutaneous Fat (Arms)', label: '皮下脂肪（手臂）', unit: '' },
  { key: 'subfat_legs', analysisKey: 'Subcutaneous Fat (Legs)', label: '皮下脂肪（腿部）', unit: '' },
  { key: 'muscle_whole', analysisKey: 'Skeletal Muscle (Whole Body)', label: '骨骼肌（全身）', unit: '' },
  { key: 'muscle_trunk', analysisKey: 'Skeletal Muscle (Trunk)', label: '骨骼肌（軀幹）', unit: '' },
  { key: 'muscle_arms', analysisKey: 'Skeletal Muscle (Arms)', label: '骨骼肌（手臂）', unit: '' },
  { key: 'muscle_legs', analysisKey: 'Skeletal Muscle (Legs)', label: '骨骼肌（腿部）', unit: '' },
]
