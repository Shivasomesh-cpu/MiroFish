<template>
  <div 
    class="history-database"
    :class="{ 'no-projects': projects.length === 0 && !loading }"
    ref="historyContainer"
  >
    <div v-if="projects.length > 0 || loading" class="tech-grid-bg">
      <div class="grid-pattern"></div>
      <div class="gradient-overlay"></div>
    </div>

    <div class="section-header">
      <div class="section-line"></div>
      <span class="section-title">{{ $t('history.title') }}</span>
      <div class="section-line"></div>
    </div>

    <div v-if="projects.length > 0" class="cards-container" :class="{ expanded: isExpanded }" :style="containerStyle">
      <div 
        v-for="(project, index) in projects" 
        :key="project.simulation_id"
        class="project-card"
        :class="{ expanded: isExpanded, hovering: hoveringCard === index }"
        :style="getCardStyle(index)"
        @mouseenter="hoveringCard = index"
        @mouseleave="hoveringCard = null"
        @click="navigateToProject(project)"
      >
        <div class="card-header">
          <span class="card-id">{{ formatSimulationId(project.simulation_id) }}</span>
          <div class="card-status-icons">
            <span 
              class="status-icon" 
              :class="{ available: project.project_id, unavailable: !project.project_id }"
              :title="$t('history.graphBuild')"
            >◇</span>
            <span 
              class="status-icon available" 
              :title="$t('history.envSetup')"
            >◈</span>
            <span 
              class="status-icon" 
              :class="{ available: project.report_id, unavailable: !project.report_id }"
              :title="$t('history.analysisReport')"
            >◆</span>
          </div>
        </div>

        <div class="card-files-wrapper">
          <div class="corner-mark top-left-only"></div>
          
          <div class="files-list" v-if="project.files && project.files.length > 0">
            <div 
              v-for="(file, fileIndex) in project.files.slice(0, 3)" 
              :key="fileIndex"
              class="file-item"
            >
              <span class="file-tag" :class="getFileType(file.filename)">{{ getFileTypeLabel(file.filename) }}</span>
              <span class="file-name">{{ truncateFilename(file.filename, 20) }}</span>
            </div>
            <div v-if="project.files.length > 3" class="files-more">
              {{ $t('history.moreFiles', { count: project.files.length - 3 }) }}
            </div>
          </div>
          <div class="files-empty" v-else>
            <span class="empty-file-icon">◇</span>
            <span class="empty-file-text">{{ $t('history.noFiles') }}</span>
          </div>
        </div>

        <h3 class="card-title">{{ getSimulationTitle(project.simulation_requirement) }}</h3>

        <p class="card-desc">{{ truncateText(project.simulation_requirement, 55) }}</p>

        <div class="card-footer">
          <div class="card-datetime">
            <span class="card-date">{{ formatDate(project.created_at) }}</span>
            <span class="card-time">{{ formatTime(project.created_at) }}</span>
          </div>
          <span class="card-progress" :class="getProgressClass(project)">
            <span class="status-dot">●</span> {{ formatRounds(project) }}
          </span>
        </div>
        
        <div class="card-bottom-line"></div>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <span class="loading-spinner"></span>
      <span class="loading-text">{{ $t('history.loadingText') }}</span>
    </div>

    <Teleport to="body">
      <Transition name="modal">
        <div v-if="selectedProject" class="modal-overlay" @click.self="closeModal">
          <div class="modal-content">
            <div class="modal-header">
              <div class="modal-title-section">
                <span class="modal-id">{{ formatSimulationId(selectedProject.simulation_id) }}</span>
                <span class="modal-progress" :class="getProgressClass(selectedProject)">
                  <span class="status-dot">●</span> {{ formatRounds(selectedProject) }}
                </span>
                <span class="modal-create-time">{{ formatDate(selectedProject.created_at) }} {{ formatTime(selectedProject.created_at) }}</span>
              </div>
              <button class="modal-close" @click="closeModal">×</button>
            </div>

            <div class="modal-body">
              <div class="modal-section">
                <div class="modal-label">{{ $t('history.simRequirement') }}</div>
                <div class="modal-requirement">{{ selectedProject.simulation_requirement || $t('common.none') }}</div>
              </div>

              <div class="modal-section">
                <div class="modal-label">{{ $t('history.relatedFiles') }}</div>
                <div class="modal-files" v-if="selectedProject.files && selectedProject.files.length > 0">
                  <div v-for="(file, index) in selectedProject.files" :key="index" class="modal-file-item">
                    <span class="file-tag" :class="getFileType(file.filename)">{{ getFileTypeLabel(file.filename) }}</span>
                    <span class="modal-file-name">{{ file.filename }}</span>
                  </div>
                </div>
                <div class="modal-empty" v-else>{{ $t('history.noRelatedFiles') }}</div>
              </div>
            </div>

            <div class="modal-divider">
              <span class="divider-line"></span>
              <span class="divider-text">{{ $t('history.replayTitle') }}</span>
              <span class="divider-line"></span>
            </div>

            <div class="modal-actions">
              <button 
                class="modal-btn btn-project" 
                @click="goToProject"
                :disabled="!selectedProject.project_id"
              >
                <span class="btn-step">Step1</span>
                <span class="btn-icon">◇</span>
                <span class="btn-text">{{ $t('history.step1Button') }}</span>
              </button>
              <button 
                class="modal-btn btn-simulation" 
                @click="goToSimulation"
              >
                <span class="btn-step">Step2</span>
                <span class="btn-icon">◈</span>
                <span class="btn-text">{{ $t('history.step2Button') }}</span>
              </button>
              <button 
                class="modal-btn btn-report" 
                @click="goToReport"
                :disabled="!selectedProject.report_id"
              >
                <span class="btn-step">Step4</span>
                <span class="btn-icon">◆</span>
                <span class="btn-text">{{ $t('history.step4Button') }}</span>
              </button>
            </div>
            <div class="modal-playback-hint">
              <span class="hint-text">{{ $t('history.replayHint') }}</span>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, onActivated, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSimulationHistory } from '../api/simulation'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const projects = ref([])
const loading = ref(true)
const isExpanded = ref(false)
const hoveringCard = ref(null)
const historyContainer = ref(null)
const selectedProject = ref(null)  // 当前选中的项目（用于弹窗）
let observer = null
let isAnimating = false  // 动画锁，防止闪烁
let expandDebounceTimer = null  // 防抖定时器
let pendingState = null  // 记录待执行的目标状态

const CARDS_PER_ROW = 4
const CARD_WIDTH = 280  
const CARD_HEIGHT = 280 
const CARD_GAP = 24

const containerStyle = computed(() => {
  if (!isExpanded.value) {
    return { minHeight: '420px' }
  }
  
  const total = projects.value.length
  if (total === 0) {
    return { minHeight: '280px' }
  }
  
  const rows = Math.ceil(total / CARDS_PER_ROW)
  const expandedHeight = rows * CARD_HEIGHT + (rows - 1) * CARD_GAP + 10
  
  return { minHeight: `${expandedHeight}px` }
})

const getCardStyle = (index) => {
  const total = projects.value.length
  
  if (isExpanded.value) {
    const transition = 'transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1), box-shadow 0.3s ease, border-color 0.3s ease'

    const col = index % CARDS_PER_ROW
    const row = Math.floor(index / CARDS_PER_ROW)
    
    const currentRowStart = row * CARDS_PER_ROW
    const currentRowCards = Math.min(CARDS_PER_ROW, total - currentRowStart)
    
    const rowWidth = currentRowCards * CARD_WIDTH + (currentRowCards - 1) * CARD_GAP
    
    const startX = -(rowWidth / 2) + (CARD_WIDTH / 2)
    const colInRow = index % CARDS_PER_ROW
    const x = startX + colInRow * (CARD_WIDTH + CARD_GAP)
    
    const y = 20 + row * (CARD_HEIGHT + CARD_GAP)

    return {
      transform: `translate(${x}px, ${y}px) rotate(0deg) scale(1)`,
      zIndex: 100 + index,
      opacity: 1,
      transition: transition
    }
  } else {
    const transition = 'transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1), box-shadow 0.3s ease, border-color 0.3s ease'

    const centerIndex = (total - 1) / 2
    const offset = index - centerIndex
    
    const x = offset * 35
    const y = 25 + Math.abs(offset) * 8
    const r = offset * 3
    const s = 0.95 - Math.abs(offset) * 0.05
    
    return {
      transform: `translate(${x}px, ${y}px) rotate(${r}deg) scale(${s})`,
      zIndex: 10 + index,
      opacity: 1,
      transition: transition
    }
  }
}

const getProgressClass = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  
  if (total === 0 || current === 0) {
    return 'not-started'
  } else if (current >= total) {
    return 'completed'
  } else {
    return 'in-progress'
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toISOString().slice(0, 10)
  } catch {
    return dateStr?.slice(0, 10) || ''
  }
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  } catch {
    return ''
  }
}

const truncateText = (text, maxLength) => {
  if (!text) return ''
  return text.length > maxLength ? text.slice(0, maxLength) + '...' : text
}

const getSimulationTitle = (requirement) => {
  if (!requirement) return t('history.untitledSimulation')
  const title = requirement.slice(0, 20)
  return requirement.length > 20 ? title + '...' : title
}

const formatSimulationId = (simulationId) => {
  if (!simulationId) return 'SIM_UNKNOWN'
  const prefix = simulationId.replace('sim_', '').slice(0, 6)
  return `SIM_${prefix.toUpperCase()}`
}

const formatRounds = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  if (total === 0) return t('history.notStarted')
  return t('history.roundsProgress', { current, total })
}

const getFileType = (filename) => {
  if (!filename) return 'other'
  const ext = filename.split('.').pop()?.toLowerCase()
  const typeMap = {
    'pdf': 'pdf',
    'doc': 'doc', 'docx': 'doc',
    'xls': 'xls', 'xlsx': 'xls', 'csv': 'xls',
    'ppt': 'ppt', 'pptx': 'ppt',
    'txt': 'txt', 'md': 'txt', 'json': 'code',
    'jpg': 'img', 'jpeg': 'img', 'png': 'img', 'gif': 'img',
    'zip': 'zip', 'rar': 'zip', '7z': 'zip'
  }
  return typeMap[ext] || 'other'
}

const getFileTypeLabel = (filename) => {
  if (!filename) return 'FILE'
  const ext = filename.split('.').pop()?.toUpperCase()
  return ext || 'FILE'
}

const truncateFilename = (filename, maxLength) => {
  if (!filename) return t('history.unknownFile')
  if (filename.length <= maxLength) return filename
  
  const ext = filename.includes('.') ? '.' + filename.split('.').pop() : ''
  const nameWithoutExt = filename.slice(0, filename.length - ext.length)
  const truncatedName = nameWithoutExt.slice(0, maxLength - ext.length - 3) + '...'
  return truncatedName + ext
}

const navigateToProject = (simulation) => {
  selectedProject.value = simulation
}

const closeModal = () => {
  selectedProject.value = null
}

const goToProject = () => {
  if (selectedProject.value?.project_id) {
    router.push({
      name: 'Process',
      params: { projectId: selectedProject.value.project_id }
    })
    closeModal()
  }
}

const goToSimulation = () => {
  if (selectedProject.value?.simulation_id) {
    router.push({
      name: 'Simulation',
      params: { simulationId: selectedProject.value.simulation_id }
    })
    closeModal()
  }
}

const goToReport = () => {
  if (selectedProject.value?.report_id) {
    router.push({
      name: 'Report',
      params: { reportId: selectedProject.value.report_id }
    })
    closeModal()
  }
}

const loadHistory = async () => {
  try {
    loading.value = true
    const response = await getSimulationHistory(20)
    if (response.success) {
      projects.value = response.data || []
    }
  } catch (error) {
    console.error('加载历史项目失败:', error)
    projects.value = []
  } finally {
    loading.value = false
  }
}

const initObserver = () => {
  if (observer) {
    observer.disconnect()
  }
  
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const shouldExpand = entry.isIntersecting
        
        pendingState = shouldExpand
        
        if (expandDebounceTimer) {
          clearTimeout(expandDebounceTimer)
          expandDebounceTimer = null
        }
        
        if (isAnimating) return
        
        if (shouldExpand === isExpanded.value) {
          pendingState = null
          return
        }
        
        const delay = shouldExpand ? 50 : 200
        
        expandDebounceTimer = setTimeout(() => {
          if (isAnimating) return
          
          if (pendingState === null || pendingState === isExpanded.value) return
          
          isAnimating = true
          isExpanded.value = pendingState
          pendingState = null
          
          setTimeout(() => {
            isAnimating = false
            
            if (pendingState !== null && pendingState !== isExpanded.value) {
              expandDebounceTimer = setTimeout(() => {
                if (pendingState !== null && pendingState !== isExpanded.value) {
                  isAnimating = true
                  isExpanded.value = pendingState
                  pendingState = null
                  setTimeout(() => {
                    isAnimating = false
                  }, 750)
                }
              }, 100)
            }
          }, 750)
        }, delay)
      })
    },
    {
      threshold: [0.4, 0.6, 0.8],
      rootMargin: '0px 0px -150px 0px'
    }
  )
  
  if (historyContainer.value) {
    observer.observe(historyContainer.value)
  }
}

watch(() => route.path, (newPath) => {
  if (newPath === '/') {
    loadHistory()
  }
})

onMounted(async () => {
  await nextTick()
  await loadHistory()
  
  setTimeout(() => {
    initObserver()
  }, 100)
})

onActivated(() => {
  loadHistory()
})

onUnmounted(() => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
  if (expandDebounceTimer) {
    clearTimeout(expandDebounceTimer)
    expandDebounceTimer = null
  }
})
</script>

<style scoped>
/* Container */
.history-database {
  position: relative;
  width: 100%;
  min-height: 280px;
  margin-top: var(--mf-space-10);
  padding: var(--mf-space-10) 0 var(--mf-space-12);
  overflow: visible;
}

/* No projects state */
.history-database.no-projects {
  min-height: auto;
  padding: var(--mf-space-10) 0 var(--mf-space-6);
}

/* Tech grid background */
.tech-grid-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  pointer-events: none;
}

.grid-pattern {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(to right, var(--mf-border-subtle) 1px, transparent 1px),
    linear-gradient(to bottom, var(--mf-border-subtle) 1px, transparent 1px);
  background-size: 50px 50px;
  background-position: top left;
}

.gradient-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    linear-gradient(to right, var(--mf-bg-primary) 0%, transparent 15%, transparent 85%, var(--mf-bg-primary) 100%),
    linear-gradient(to bottom, var(--mf-bg-primary) 0%, transparent 20%, transparent 80%, var(--mf-bg-primary) 100%);
  pointer-events: none;
}

/* Section header */
.section-header {
  position: relative;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--mf-space-6);
  margin-bottom: var(--mf-space-6);
  font-family: var(--mf-font-mono);
  padding: 0 var(--mf-space-10);
}

.section-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--mf-border-default), transparent);
  max-width: 300px;
}

.section-title {
  font-size: var(--mf-text-sm);
  font-weight: var(--mf-font-medium);
  color: var(--mf-text-tertiary);
  letter-spacing: 3px;
  text-transform: uppercase;
}

/* Cards container */
.cards-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 0 var(--mf-space-10);
  transition: min-height 700ms cubic-bezier(0.23, 1, 0.32, 1);
}

/* Project card */
.project-card {
  position: absolute;
  width: 280px;
  background: var(--mf-bg-secondary);
  border: 1px solid var(--mf-border-subtle);
  border-radius: var(--mf-radius-lg);
  padding: var(--mf-space-4);
  cursor: pointer;
  box-shadow: var(--mf-shadow-sm);
  transition: box-shadow 0.3s ease, border-color 0.3s ease, transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1);
}

.project-card:hover {
  box-shadow: var(--mf-shadow-lg), var(--mf-glow-accent-subtle);
  border-color: var(--mf-accent-primary);
  z-index: 1000 !important;
}

.project-card.hovering {
  z-index: 1000 !important;
}

/* Card header */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--mf-space-3);
  padding-bottom: var(--mf-space-3);
  border-bottom: 1px solid var(--mf-border-subtle);
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-xs);
}

.card-id {
  color: var(--mf-text-tertiary);
  letter-spacing: 0.5px;
  font-weight: var(--mf-font-medium);
}

/* Status icons */
.card-status-icons {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
}

.status-icon {
  font-size: 0.75rem;
  transition: all 0.2s ease;
  cursor: default;
}

.status-icon.available {
  opacity: 1;
}

.status-icon:nth-child(1).available { color: var(--mf-cyan); }
.status-icon:nth-child(2).available { color: var(--mf-orange); }
.status-icon:nth-child(3).available { color: var(--mf-green); }

.status-icon.unavailable {
  color: var(--mf-text-tertiary);
  opacity: 0.3;
}

/* Progress */
.card-progress {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  letter-spacing: 0.5px;
  font-weight: var(--mf-font-semibold);
  font-size: var(--mf-text-xs);
}

.status-dot {
  font-size: 0.5rem;
}

.card-progress.completed { color: var(--mf-green); }
.card-progress.in-progress { color: var(--mf-orange); }
.card-progress.not-started { color: var(--mf-text-tertiary); }
.card-status.pending { color: var(--mf-text-tertiary); }

/* Files wrapper */
.card-files-wrapper {
  position: relative;
  width: 100%;
  min-height: 48px;
  max-height: 110px;
  margin-bottom: var(--mf-space-3);
  padding: var(--mf-space-2) var(--mf-space-3);
  background: var(--mf-bg-tertiary);
  border-radius: var(--mf-radius-md);
  border: 1px solid var(--mf-border-subtle);
  overflow: hidden;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-1);
}

.files-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--mf-space-1) var(--mf-space-2);
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
  background: var(--mf-surface-glass);
  border-radius: var(--mf-radius-sm);
  letter-spacing: 0.3px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  padding: var(--mf-space-1) var(--mf-space-2);
  background: var(--mf-bg-elevated);
  border-radius: var(--mf-radius-sm);
  transition: all 0.2s ease;
}

.file-item:hover {
  background: var(--mf-bg-hover);
  transform: translateX(2px);
  border-color: #e5e7eb;
}

/* 简约文件标签样式 */
.file-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 16px;
  padding: 0 4px;
  border-radius: 2px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  font-weight: 600;
  line-height: 1;
  text-transform: uppercase;
  letter-spacing: 0.2px;
  flex-shrink: 0;
  min-width: 28px;
}

/* Low saturation color scheme - Dark theme adjusted */
.file-tag.pdf { background: rgba(166, 90, 90, 0.15); color: #e88a8a; }
.file-tag.doc { background: rgba(90, 126, 166, 0.15); color: #8ab4e6; }
.file-tag.xls { background: rgba(90, 166, 104, 0.15); color: #8ae69e; }
.file-tag.ppt { background: rgba(166, 129, 90, 0.15); color: #e6b18a; }
.file-tag.txt { background: rgba(117, 117, 117, 0.15); color: #a3a3a3; }
.file-tag.code { background: rgba(129, 90, 166, 0.15); color: #b38ae6; }
.file-tag.img { background: rgba(90, 166, 166, 0.15); color: #8ae6e6; }
.file-tag.zip { background: rgba(166, 155, 90, 0.15); color: #e6d58a; }
.file-tag.other { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }

.file-name {
  font-family: 'Inter', sans-serif;
  font-size: 0.7rem;
  color: var(--mf-text-secondary, #94a3b8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: 0.1px;
}

/* No files placeholder */
.files-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 48px;
  color: var(--mf-text-muted, #6b7280);
}

.empty-file-icon {
  font-size: 1rem;
  opacity: 0.5;
}

.empty-file-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  letter-spacing: 0.5px;
}

/* Hover effect for file area */
.project-card:hover .card-files-wrapper {
  border-color: var(--mf-accent, #8b5cf6);
  background: linear-gradient(135deg, var(--mf-bg-tertiary, #1a1a2e) 0%, rgba(139, 92, 246, 0.05) 100%);
}

/* Corner decoration */
.corner-mark.top-left-only {
  position: absolute;
  top: 6px;
  left: 6px;
  width: 8px;
  height: 8px;
  border-top: 1.5px solid var(--mf-accent, #8b5cf6);
  border-left: 1.5px solid var(--mf-accent, #8b5cf6);
  pointer-events: none;
  z-index: 10;
}

/* Card title */
.card-title {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--mf-text-primary, #f1f5f9);
  margin: 0 0 6px 0;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.3s ease;
}

.project-card:hover .card-title {
  color: var(--mf-accent, #8b5cf6);
}

/* Card description */
.card-desc {
  font-family: 'Inter', sans-serif;
  font-size: 0.75rem;
  color: var(--mf-text-secondary, #94a3b8);
  margin: 0 0 16px 0;
  line-height: 1.5;
  height: 34px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* Card footer */
.card-footer {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: var(--mf-text-muted, #6b7280);
  font-weight: 500;
}

/* 日期时间组合 */
.card-datetime {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 底部轮数进度显示 */
.card-footer .card-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 0.5px;
  font-weight: 600;
  font-size: 0.65rem;
}

.card-footer .status-dot {
  font-size: 0.5rem;
}

/* Footer progress colors */
.card-footer .card-progress.completed { color: var(--mf-success, #10b981); }
.card-footer .card-progress.in-progress { color: #F59E0B; }
.card-footer .card-progress.not-started { color: var(--mf-text-muted, #6b7280); }

/* Bottom decoration line */
.card-bottom-line {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 2px;
  width: 0;
  background: linear-gradient(135deg, var(--mf-accent, #8b5cf6), var(--mf-accent-secondary, #ec4899));
  transition: width 0.5s cubic-bezier(0.23, 1, 0.32, 1);
  z-index: 20;
}

.project-card:hover .card-bottom-line {
  width: 100%;
}

/* Empty state */
.empty-state, .loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 48px;
  color: var(--mf-text-muted, #6b7280);
}

.empty-icon {
  font-size: 2rem;
  opacity: 0.5;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  border-top-color: var(--mf-accent, #8b5cf6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 响应式 */
@media (max-width: 1200px) {
  .project-card {
    width: 240px;
  }
}

@media (max-width: 768px) {
  .cards-container {
    padding: 0 20px;
  }
  .project-card {
    width: 200px;
  }
}

/* ===== History Playback Detail Modal Styles ===== */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(8px);
}

.modal-content {
  background: var(--mf-bg-secondary, #12121a);
  width: 560px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 30px rgba(139, 92, 246, 0.1);
}

/* 动画过渡 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-content {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.modal-leave-active .modal-content {
  transition: all 0.2s ease-in;
}

.modal-enter-from .modal-content {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}

.modal-leave-to .modal-content {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}

/* Modal header */
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 32px;
  border-bottom: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  background: var(--mf-bg-secondary, #12121a);
}

.modal-title-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.modal-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  font-weight: 600;
  color: var(--mf-text-primary, #f1f5f9);
  letter-spacing: 0.5px;
}

.modal-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  background: var(--mf-bg-tertiary, #1a1a2e);
}

.modal-progress.completed { color: var(--mf-success, #10b981); background: rgba(16, 185, 129, 0.15); }
.modal-progress.in-progress { color: #F59E0B; background: rgba(245, 158, 11, 0.15); }
.modal-progress.not-started { color: var(--mf-text-muted, #6b7280); background: var(--mf-bg-tertiary, #1a1a2e); }

.modal-create-time {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--mf-text-muted, #6b7280);
  letter-spacing: 0.3px;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 1.5rem;
  color: var(--mf-text-muted, #6b7280);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  border-radius: 6px;
}

.modal-close:hover {
  background: rgba(139, 92, 246, 0.1);
  color: var(--mf-text-primary, #f1f5f9);
}

/* Modal content */
.modal-body {
  padding: 24px 32px;
}

.modal-section {
  margin-bottom: 24px;
}

.modal-section:last-child {
  margin-bottom: 0;
}

.modal-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--mf-text-muted, #6b7280);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 10px;
  font-weight: 500;
}

.modal-requirement {
  font-size: 0.95rem;
  color: var(--mf-text-secondary, #94a3b8);
  line-height: 1.6;
  padding: 16px;
  background: var(--mf-bg-tertiary, #1a1a2e);
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  border-radius: 8px;
}

.modal-files {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 200px;
  overflow-y: auto;
  padding-right: 4px;
}

/* Custom scrollbar styles */
.modal-files::-webkit-scrollbar {
  width: 4px;
}

.modal-files::-webkit-scrollbar-track {
  background: var(--mf-bg-tertiary, #1a1a2e);
  border-radius: 2px;
}

.modal-files::-webkit-scrollbar-thumb {
  background: var(--mf-accent, #8b5cf6);
  border-radius: 2px;
}

.modal-files::-webkit-scrollbar-thumb:hover {
  background: var(--mf-accent-secondary, #ec4899);
}

.modal-file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--mf-bg-secondary, #12121a);
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  border-radius: 6px;
  transition: all 0.2s ease;
}

.modal-file-item:hover {
  border-color: var(--mf-accent, #8b5cf6);
  box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);
}

.modal-file-name {
  font-size: 0.85rem;
  color: var(--mf-text-secondary, #94a3b8);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.modal-empty {
  font-size: 0.85rem;
  color: var(--mf-text-muted, #6b7280);
  padding: 16px;
  background: var(--mf-bg-tertiary, #1a1a2e);
  border: 1px dashed var(--mf-border, rgba(139, 92, 246, 0.2));
  border-radius: 6px;
  text-align: center;
}

/* Playback divider line */
.modal-divider {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 32px 0;
  background: var(--mf-bg-secondary, #12121a);
}

.divider-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--mf-border, rgba(139, 92, 246, 0.2)), transparent);
}

.divider-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--mf-text-muted, #6b7280);
  letter-spacing: 2px;
  text-transform: uppercase;
  white-space: nowrap;
}

/* Navigation buttons */
.modal-actions {
  display: flex;
  gap: 16px;
  padding: 20px 32px;
  background: var(--mf-bg-secondary, #12121a);
}

.modal-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  border-radius: 8px;
  background: var(--mf-bg-tertiary, #1a1a2e);
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.modal-btn:hover:not(:disabled) {
  border-color: var(--mf-accent, #8b5cf6);
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(139, 92, 246, 0.2);
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--mf-bg-tertiary, #1a1a2e);
}

.btn-step {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  font-weight: 500;
  color: var(--mf-text-muted, #6b7280);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.btn-icon {
  font-size: 1.4rem;
  line-height: 1;
  transition: color 0.2s ease;
}

.btn-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: var(--mf-text-secondary, #94a3b8);
}

.modal-btn.btn-project .btn-icon { color: #3B82F6; }
.modal-btn.btn-simulation .btn-icon { color: #F59E0B; }
.modal-btn.btn-report .btn-icon { color: var(--mf-success, #10b981); }

.modal-btn:hover:not(:disabled) .btn-text {
  color: var(--mf-text-primary, #f1f5f9);
}

/* Cannot playback hint */
.modal-playback-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 32px 20px;
  background: var(--mf-bg-secondary, #12121a);
}

.hint-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--mf-text-muted, #6b7280);
  letter-spacing: 0.3px;
  text-align: center;
  line-height: 1.5;
}
</style>
