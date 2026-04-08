<template>
  <div class="home-container">
    <!-- Navigation Bar -->
    <nav class="navbar glass">
      <div class="nav-content">
        <div class="nav-brand">
          <span class="brand-icon">Ã¢â€”â€ </span>
          <span class="brand-text">POSIEDON</span>
        </div>
        
        <div class="nav-center">
          <div class="nav-status">
            <span class="status-dot pulse"></span>
            <span class="status-text">{{ $t('nav.systemOnline') || 'System Online' }}</span>
          </div>
        </div>
        
        <div class="nav-links">
          <button class="nav-btn theme-toggle" @click="toggleTheme" :title="theme === 'dark' ? 'Light Mode' : 'Dark Mode'">
            <span v-if="theme === 'dark'">Ã¢Ëœâ‚¬Ã¯Â¸Â</span>
            <span v-else>Ã°Å¸Å’â„¢</span>
          </button>
          <LanguageSwitcher />
          <a href="https://github.com/Shivasomesh-cpu/posiedon" target="_blank" class="nav-btn github-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            <span>GitHub</span>
          </a>
        </div>
      </div>
    </nav>

    <!-- Hero Section -->
    <section class="hero-section">
      <div class="hero-content">
        <div class="hero-left">
          <div class="badge-row">
            <span class="badge badge-primary glow-pulse">{{ $t('home.tagline') || 'SWARM INTELLIGENCE' }}</span>
            <span class="version-badge">v0.1.0</span>
          </div>
          
          <h1 class="hero-title">
            <span class="title-line">{{ $t('home.heroTitle1') || 'Predict the' }}</span>
            <span class="title-line gradient-line">
              <span class="text-gradient">{{ $t('home.heroTitle2') || 'Unpredictable' }}</span>
            </span>
          </h1>
          
          <p class="hero-description">
            {{ $t('home.heroDescFull') || 'Posiedon is a next-generation AI prediction engine powered by multi-agent technology. Upload seed materials, describe your prediction requirements, and watch thousands of intelligent agents simulate future outcomes.' }}
          </p>
          
          <div class="hero-stats">
            <div class="stat-item">
              <span class="stat-value">1000+</span>
              <span class="stat-label">{{ $t('home.statAgents') || 'AI Agents' }}</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value">Ã¢Ë†Å¾</span>
              <span class="stat-label">{{ $t('home.statScenarios') || 'Scenarios' }}</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value">99%</span>
              <span class="stat-label">{{ $t('home.statAccuracy') || 'Accuracy' }}</span>
            </div>
          </div>
        </div>
        
        <div class="hero-right">
          <div class="logo-glow-container">
            <div class="logo-glow"></div>
            <img src="../assets/logo/Posiedon_logo_left.jpeg" alt="Posiedon Logo" class="hero-logo" />
          </div>
        </div>
      </div>
      
      <div class="scroll-indicator" @click="scrollToConsole">
        <span class="scroll-text">{{ $t('home.scrollToStart') || 'Scroll to Start' }}</span>
        <div class="scroll-arrow">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12l7 7 7-7"/>
          </svg>
        </div>
      </div>
    </section>

    <!-- Main Dashboard -->
    <section class="dashboard-section" ref="consoleSection">
      <div class="dashboard-content">
        <!-- Left Panel: Status & Workflow -->
        <div class="panel left-panel">
          <div class="panel-header">
            <span class="panel-icon">Ã¢â€”â€¡</span>
            <span class="panel-title">{{ $t('home.systemStatus') || 'System Status' }}</span>
          </div>
          
          <div class="status-card glass">
            <div class="status-indicator active">
              <span class="indicator-dot"></span>
              <span class="indicator-text">{{ $t('home.engineReady') || 'Prediction Engine Ready' }}</span>
            </div>
            
            <div class="metrics-grid">
              <div class="metric-card">
                <div class="metric-icon">Ã¢Å¡Â¡</div>
                <div class="metric-info">
                  <span class="metric-value">{{ $t('home.metricLowCost') || 'Low Cost' }}</span>
                  <span class="metric-label">{{ $t('home.metricLowCostDesc') || 'API Efficient' }}</span>
                </div>
              </div>
              <div class="metric-card">
                <div class="metric-icon">Ã°Å¸â€â€ž</div>
                <div class="metric-info">
                  <span class="metric-value">{{ $t('home.metricHighAvail') || '99.9%' }}</span>
                  <span class="metric-label">{{ $t('home.metricHighAvailDesc') || 'Uptime' }}</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Workflow Steps -->
          <div class="workflow-card glass">
            <div class="workflow-header">
              <span class="workflow-icon">Ã¢â€“Â£</span>
              <span class="workflow-title">{{ $t('home.workflowSequence') || 'Workflow Sequence' }}</span>
            </div>
            
            <div class="workflow-steps">
              <div v-for="(step, index) in workflowSteps" :key="index" class="workflow-step">
                <div class="step-number">{{ String(index + 1).padStart(2, '0') }}</div>
                <div class="step-content">
                  <span class="step-title">{{ step.title }}</span>
                  <span class="step-desc">{{ step.desc }}</span>
                </div>
                <div class="step-indicator"></div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Right Panel: Upload Console -->
        <div class="panel right-panel">
          <div class="console-card glass-strong">
            <div class="console-header">
              <div class="console-title">
                <span class="console-icon">Ã¢Â¬Â¡</span>
                <span>{{ $t('home.predictionConsole') || 'Prediction Console' }}</span>
              </div>
              <div class="console-badge">
                <span class="badge badge-success">{{ $t('home.ready') || 'READY' }}</span>
              </div>
            </div>
            
            <!-- File Upload Area -->
            <div class="upload-section">
              <div class="section-label">
                <span class="label-icon">Ã°Å¸â€œâ€ž</span>
                <span>{{ $t('home.realitySeed') || 'Reality Seed' }}</span>
                <span class="label-hint">{{ $t('home.supportedFormats') || 'PDF, MD, TXT' }}</span>
              </div>
              
              <div 
                class="upload-dropzone"
                :class="{ 
                  'drag-over': isDragOver, 
                  'has-files': files.length > 0 
                }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon-container">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                    </svg>
                  </div>
                  <div class="upload-text">
                    <span class="upload-title">{{ $t('home.dragToUpload') || 'Drag & Drop Files' }}</span>
                    <span class="upload-hint">{{ $t('home.orBrowse') || 'or click to browse' }}</span>
                  </div>
                </div>
                
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm4 18H6V4h7v5h5v11z"/>
                      </svg>
                    </span>
                    <span class="file-name">{{ file.name }}</span>
                    <span class="file-size">{{ formatFileSize(file.size) }}</span>
                    <button @click.stop="removeFile(index)" class="file-remove" aria-label="Remove file">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Divider -->
            <div class="console-divider">
              <span class="divider-line"></span>
              <span class="divider-text">{{ $t('home.inputParams') || 'PARAMETERS' }}</span>
              <span class="divider-line"></span>
            </div>
            
            <!-- Prediction Prompt -->
            <div class="prompt-section">
              <div class="section-label">
                <span class="label-icon">Ã°Å¸â€™Â­</span>
                <span>{{ $t('home.simulationPrompt') || 'Prediction Prompt' }}</span>
              </div>
              
              <div class="prompt-input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="prompt-input"
                  :placeholder="$t('home.promptPlaceholder') || 'Describe what you want to predict...'"
                  rows="5"
                  :disabled="loading"
                ></textarea>
                <div class="input-footer">
                  <span class="char-count">{{ formData.simulationRequirement.length }} / 2000</span>
                  <span class="engine-badge">
                    <span class="badge-dot"></span>
                    {{ $t('home.engineBadge') || 'OASIS Engine' }}
                  </span>
                </div>
              </div>
            </div>
            
            <!-- Launch Button -->
            <button 
              class="launch-btn"
              :class="{ 'ready': canSubmit, 'loading': loading }"
              @click="startSimulation"
              :disabled="!canSubmit || loading"
            >
              <span v-if="!loading" class="btn-content">
                <span class="btn-text">{{ $t('home.startEngine') || 'Launch Prediction Engine' }}</span>
                <span class="btn-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </span>
              </span>
              <span v-else class="btn-content loading">
                <span class="spinner"></span>
                <span class="btn-text">{{ $t('home.initializing') || 'Initializing...' }}</span>
              </span>
            </button>
          </div>
        </div>
      </div>
    </section>
    
    <!-- History Section -->
    <HistoryDatabase />
    
    <!-- Footer -->
    <footer class="footer glass">
      <div class="footer-content">
        <div class="footer-brand">
          <span class="brand-icon">Ã¢â€”â€ </span>
          <span>Posiedon</span>
        </div>
        <div class="footer-links">
          <a href="https://github.com/Shivasomesh-cpu/posiedon" target="_blank">GitHub</a>
          <a href="https://discord.gg/ePf5aPaHnA" target="_blank">Discord</a>
          <a href="https://x.com/mirofish_ai" target="_blank">Twitter</a>
        </div>
        <div class="footer-copy">
          <span>Ã‚Â© 2024 Posiedon. Powered by OASIS.</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'

const router = useRouter()
const { t } = useI18n()

// Theme
const { theme, toggleTheme } = inject('theme', { 
  theme: ref('dark'), 
  toggleTheme: () => {} 
})

// Toast
const showToast = inject('toast', () => {})

// Form Data
const formData = ref({
  simulationRequirement: ''
})

// File Management
const files = ref([])
const fileInput = ref(null)
const isDragOver = ref(false)
const loading = ref(false)
const consoleSection = ref(null)

// Workflow Steps
const workflowSteps = computed(() => [
  { title: t('home.step01Title') || 'Graph Building', desc: t('home.step01Desc') || 'Extract knowledge graph from seed materials' },
  { title: t('home.step02Title') || 'Environment Setup', desc: t('home.step02Desc') || 'Configure agent personas and behaviors' },
  { title: t('home.step03Title') || 'Simulation', desc: t('home.step03Desc') || 'Run multi-agent parallel simulation' },
  { title: t('home.step04Title') || 'Report Generation', desc: t('home.step04Desc') || 'Generate detailed prediction report' },
  { title: t('home.step05Title') || 'Deep Interaction', desc: t('home.step05Desc') || 'Chat with agents in the simulated world' }
])

// Computed
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

// Methods
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

const handleDragOver = () => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = () => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  
  if (validFiles.length !== newFiles.length) {
    showToast('Some files were skipped (unsupported format)', 'warning')
  }
  
  files.value.push(...validFiles)
  
  if (validFiles.length > 0) {
    showToast(`${validFiles.length} file(s) added`, 'success')
  }
}

const removeFile = (index) => {
  files.value.splice(index, 1)
}

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const scrollToConsole = () => {
  consoleSection.value?.scrollIntoView({ behavior: 'smooth' })
}

const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  
  loading.value = true
  
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    
    showToast('Launching prediction engine...', 'info')
    
    setTimeout(() => {
      router.push({
        name: 'Process',
        params: { projectId: 'new' }
      })
    }, 500)
  })
}
</script>

<style scoped>
/* Container */
.home-container {
  min-height: 100vh;
  position: relative;
}

/* Navigation */
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  z-index: var(--mf-z-sticky);
  border-bottom: 1px solid var(--mf-border-subtle);
}

.nav-content {
  max-width: 1400px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--mf-space-6);
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
}

.brand-icon {
  color: var(--mf-accent-primary);
  font-size: 1.2rem;
}

.brand-text {
  font-family: var(--mf-font-mono);
  font-weight: var(--mf-font-extrabold);
  font-size: var(--mf-text-lg);
  letter-spacing: 2px;
  color: var(--mf-text-primary);
}

.nav-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.nav-status {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  font-size: var(--mf-text-sm);
  color: var(--mf-text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  background: var(--mf-green);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--mf-green);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: var(--mf-space-3);
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  padding: var(--mf-space-2) var(--mf-space-4);
  background: var(--mf-surface-glass);
  border: 1px solid var(--mf-border-subtle);
  border-radius: var(--mf-radius-md);
  color: var(--mf-text-secondary);
  font-size: var(--mf-text-sm);
  cursor: pointer;
  transition: all var(--mf-transition-fast);
  text-decoration: none;
}

.nav-btn:hover {
  background: var(--mf-surface-glass-hover);
  color: var(--mf-text-primary);
  border-color: var(--mf-border-default);
}

.theme-toggle {
  width: 40px;
  padding: var(--mf-space-2);
  justify-content: center;
}

/* Hero Section */
.hero-section {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 100px var(--mf-space-6) var(--mf-space-16);
  position: relative;
}

.hero-content {
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--mf-space-16);
  align-items: center;
}

.hero-left {
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-8);
}

.badge-row {
  display: flex;
  align-items: center;
  gap: var(--mf-space-4);
}

.version-badge {
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
}

.hero-title {
  font-family: var(--mf-font-display);
  font-size: var(--mf-text-6xl);
  font-weight: var(--mf-font-bold);
  line-height: 1.1;
  letter-spacing: -2px;
}

.title-line {
  display: block;
  color: var(--mf-text-primary);
}

.gradient-line {
  margin-top: var(--mf-space-2);
}

.hero-description {
  font-size: var(--mf-text-lg);
  color: var(--mf-text-secondary);
  line-height: 1.7;
  max-width: 540px;
}

.hero-stats {
  display: flex;
  align-items: center;
  gap: var(--mf-space-8);
  padding-top: var(--mf-space-4);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-1);
}

.stat-value {
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-3xl);
  font-weight: var(--mf-font-bold);
  color: var(--mf-accent-primary);
}

.stat-label {
  font-size: var(--mf-text-sm);
  color: var(--mf-text-tertiary);
}

.stat-divider {
  width: 1px;
  height: 40px;
  background: var(--mf-border-subtle);
}

.hero-right {
  display: flex;
  justify-content: center;
  align-items: center;
}

.logo-glow-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
}

.logo-glow {
  position: absolute;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, var(--mf-accent-dim) 0%, transparent 70%);
  filter: blur(60px);
  animation: glow-pulse 3s ease-in-out infinite;
}

.hero-logo {
  max-width: 380px;
  width: 100%;
  border-radius: var(--mf-radius-2xl);
  box-shadow: var(--mf-shadow-xl);
  position: relative;
  z-index: 1;
}

.scroll-indicator {
  position: absolute;
  bottom: var(--mf-space-8);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--mf-space-2);
  cursor: pointer;
  opacity: 0.7;
  transition: opacity var(--mf-transition-fast);
}

.scroll-indicator:hover {
  opacity: 1;
}

.scroll-text {
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 2px;
}

.scroll-arrow {
  color: var(--mf-accent-primary);
  animation: bounce 2s ease-in-out infinite;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(8px); }
}

/* Dashboard Section */
.dashboard-section {
  padding: var(--mf-space-24) var(--mf-space-6);
  border-top: 1px solid var(--mf-border-subtle);
}

.dashboard-content {
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: var(--mf-space-8);
}

/* Panels */
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-6);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-sm);
  color: var(--mf-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.panel-icon {
  color: var(--mf-accent-primary);
}

/* Status Card */
.status-card {
  padding: var(--mf-space-6);
  border-radius: var(--mf-radius-xl);
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-6);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: var(--mf-space-3);
}

.status-indicator.active .indicator-dot {
  width: 10px;
  height: 10px;
  background: var(--mf-green);
  border-radius: 50%;
  box-shadow: 0 0 12px var(--mf-green);
  animation: pulse 2s ease-in-out infinite;
}

.indicator-text {
  font-size: var(--mf-text-lg);
  font-weight: var(--mf-font-semibold);
  color: var(--mf-text-primary);
}

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--mf-space-4);
}

.metric-card {
  display: flex;
  align-items: center;
  gap: var(--mf-space-3);
  padding: var(--mf-space-4);
  background: var(--mf-bg-tertiary);
  border-radius: var(--mf-radius-lg);
  border: 1px solid var(--mf-border-subtle);
}

.metric-icon {
  font-size: 1.5rem;
}

.metric-info {
  display: flex;
  flex-direction: column;
}

.metric-value {
  font-family: var(--mf-font-mono);
  font-weight: var(--mf-font-bold);
  color: var(--mf-text-primary);
}

.metric-label {
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
}

/* Workflow Card */
.workflow-card {
  padding: var(--mf-space-6);
  border-radius: var(--mf-radius-xl);
}

.workflow-header {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  margin-bottom: var(--mf-space-6);
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-sm);
  color: var(--mf-text-tertiary);
}

.workflow-icon {
  color: var(--mf-accent-primary);
}

.workflow-steps {
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-4);
}

.workflow-step {
  display: flex;
  align-items: flex-start;
  gap: var(--mf-space-4);
  padding: var(--mf-space-3) 0;
  position: relative;
}

.workflow-step:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 15px;
  top: 40px;
  bottom: -16px;
  width: 1px;
  background: var(--mf-border-subtle);
}

.step-number {
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-sm);
  font-weight: var(--mf-font-bold);
  color: var(--mf-accent-primary);
  min-width: 30px;
}

.step-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-1);
}

.step-title {
  font-weight: var(--mf-font-semibold);
  color: var(--mf-text-primary);
}

.step-desc {
  font-size: var(--mf-text-sm);
  color: var(--mf-text-tertiary);
  line-height: 1.5;
}

/* Console Card */
.console-card {
  padding: var(--mf-space-8);
  border-radius: var(--mf-radius-xl);
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-6);
}

.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.console-title {
  display: flex;
  align-items: center;
  gap: var(--mf-space-3);
  font-size: var(--mf-text-lg);
  font-weight: var(--mf-font-semibold);
  color: var(--mf-text-primary);
}

.console-icon {
  color: var(--mf-accent-primary);
  font-size: 1.2rem;
}

/* Upload Section */
.upload-section {
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-3);
}

.section-label {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  font-size: var(--mf-text-sm);
  color: var(--mf-text-secondary);
}

.label-icon {
  font-size: 1rem;
}

.label-hint {
  margin-left: auto;
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
}

.upload-dropzone {
  border: 2px dashed var(--mf-border-default);
  border-radius: var(--mf-radius-lg);
  padding: var(--mf-space-8);
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--mf-transition-fast);
  background: var(--mf-bg-tertiary);
}

.upload-dropzone:hover {
  border-color: var(--mf-accent-primary);
  background: var(--mf-bg-hover);
}

.upload-dropzone.drag-over {
  border-color: var(--mf-accent-primary);
  background: var(--mf-accent-dim);
  box-shadow: var(--mf-glow-accent-subtle);
}

.upload-dropzone.has-files {
  align-items: flex-start;
  padding: var(--mf-space-4);
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--mf-space-4);
  text-align: center;
}

.upload-icon-container {
  width: 64px;
  height: 64px;
  border-radius: var(--mf-radius-lg);
  background: var(--mf-accent-dim);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--mf-accent-primary);
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-1);
}

.upload-title {
  font-weight: var(--mf-font-semibold);
  color: var(--mf-text-primary);
}

.upload-hint {
  font-size: var(--mf-text-sm);
  color: var(--mf-text-tertiary);
}

.file-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-2);
}

.file-item {
  display: flex;
  align-items: center;
  gap: var(--mf-space-3);
  padding: var(--mf-space-3) var(--mf-space-4);
  background: var(--mf-bg-elevated);
  border-radius: var(--mf-radius-md);
  border: 1px solid var(--mf-border-subtle);
}

.file-icon {
  color: var(--mf-accent-primary);
}

.file-name {
  flex: 1;
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-sm);
  color: var(--mf-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
}

.file-remove {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--mf-text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--mf-radius-sm);
  transition: all var(--mf-transition-fast);
}

.file-remove:hover {
  background: var(--mf-red);
  background: rgba(239, 68, 68, 0.2);
  color: var(--mf-red);
}

/* Divider */
.console-divider {
  display: flex;
  align-items: center;
  gap: var(--mf-space-4);
  margin: var(--mf-space-2) 0;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: var(--mf-border-subtle);
}

.divider-text {
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
  letter-spacing: 2px;
}

/* Prompt Section */
.prompt-section {
  display: flex;
  flex-direction: column;
  gap: var(--mf-space-3);
}

.prompt-input-wrapper {
  position: relative;
}

.prompt-input {
  width: 100%;
  padding: var(--mf-space-4);
  background: var(--mf-bg-tertiary);
  border: 1px solid var(--mf-border-default);
  border-radius: var(--mf-radius-lg);
  font-family: var(--mf-font-sans);
  font-size: var(--mf-text-base);
  color: var(--mf-text-primary);
  resize: vertical;
  min-height: 120px;
  transition: all var(--mf-transition-fast);
}

.prompt-input::placeholder {
  color: var(--mf-text-tertiary);
}

.prompt-input:focus {
  outline: none;
  border-color: var(--mf-accent-primary);
  box-shadow: 0 0 0 3px var(--mf-accent-dim);
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--mf-space-2);
}

.char-count {
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
}

.engine-badge {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-xs);
  color: var(--mf-text-tertiary);
}

.badge-dot {
  width: 6px;
  height: 6px;
  background: var(--mf-green);
  border-radius: 50%;
}

/* Launch Button */
.launch-btn {
  width: 100%;
  padding: var(--mf-space-5) var(--mf-space-6);
  background: var(--mf-bg-tertiary);
  border: 1px solid var(--mf-border-default);
  border-radius: var(--mf-radius-lg);
  cursor: not-allowed;
  transition: all var(--mf-transition-fast);
  margin-top: var(--mf-space-2);
}

.launch-btn.ready {
  background: var(--mf-gradient-primary);
  border: none;
  cursor: pointer;
  box-shadow: var(--mf-glow-accent-subtle);
}

.launch-btn.ready:hover {
  box-shadow: var(--mf-glow-accent);
  transform: translateY(-2px);
}

.launch-btn.ready:active {
  transform: translateY(0);
}

.launch-btn:disabled {
  opacity: 0.6;
}

.btn-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--mf-space-3);
}

.btn-text {
  font-family: var(--mf-font-mono);
  font-size: var(--mf-text-base);
  font-weight: var(--mf-font-bold);
  color: var(--mf-text-tertiary);
  letter-spacing: 1px;
}

.launch-btn.ready .btn-text {
  color: white;
}

.btn-icon {
  color: var(--mf-text-tertiary);
}

.launch-btn.ready .btn-icon {
  color: white;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Footer */
.footer {
  padding: var(--mf-space-8) var(--mf-space-6);
  border-top: 1px solid var(--mf-border-subtle);
  margin-top: var(--mf-space-16);
}

.footer-content {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.footer-brand {
  display: flex;
  align-items: center;
  gap: var(--mf-space-2);
  font-family: var(--mf-font-mono);
  font-weight: var(--mf-font-bold);
  color: var(--mf-text-primary);
}

.footer-links {
  display: flex;
  gap: var(--mf-space-6);
}

.footer-links a {
  font-size: var(--mf-text-sm);
  color: var(--mf-text-secondary);
  transition: color var(--mf-transition-fast);
}

.footer-links a:hover {
  color: var(--mf-accent-primary);
}

.footer-copy {
  font-size: var(--mf-text-sm);
  color: var(--mf-text-tertiary);
}

/* Responsive */
@media (max-width: 1024px) {
  .hero-content {
    grid-template-columns: 1fr;
    text-align: center;
  }
  
  .hero-left {
    align-items: center;
  }
  
  .hero-description {
    max-width: 100%;
  }
  
  .hero-stats {
    justify-content: center;
  }
  
  .hero-right {
    order: -1;
  }
  
  .hero-logo {
    max-width: 280px;
  }
  
  .dashboard-content {
    grid-template-columns: 1fr;
  }
  
  .footer-content {
    flex-direction: column;
    gap: var(--mf-space-4);
    text-align: center;
  }
}

@media (max-width: 640px) {
  .hero-title {
    font-size: var(--mf-text-4xl);
  }
  
  .nav-center {
    display: none;
  }
  
  .hero-stats {
    flex-direction: column;
    gap: var(--mf-space-4);
  }
  
  .stat-divider {
    width: 40px;
    height: 1px;
  }
}
</style>
