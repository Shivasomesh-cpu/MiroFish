<template>
  <div class="workbench-panel">
    <div class="scroll-container">
      <!-- Step 01: Ontology -->
      <div class="step-card" :class="{ 'active': currentPhase === 0, 'completed': currentPhase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">{{ $t('step1.ontologyGeneration') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 0" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 0" class="badge processing">{{ $t('step1.ontologyGenerating') }}</span>
            <span v-else class="badge pending">{{ $t('step1.ontologyPending') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/graph/ontology/generate</p>
          <p class="description">
            {{ $t('step1.ontologyDesc') }}
          </p>

          <!-- Loading / Progress -->
          <div v-if="currentPhase === 0 && ontologyProgress" class="progress-section">
            <div class="spinner-sm"></div>
            <span>{{ ontologyProgress.message || $t('step1.analyzingDocs') }}</span>
          </div>

          <!-- Detail Overlay -->
          <div v-if="selectedOntologyItem" class="ontology-detail-overlay">
            <div class="detail-header">
               <div class="detail-title-group">
                  <span class="detail-type-badge">{{ selectedOntologyItem.itemType === 'entity' ? 'ENTITY' : 'RELATION' }}</span>
                  <span class="detail-name">{{ selectedOntologyItem.name }}</span>
               </div>
               <button class="close-btn" @click="selectedOntologyItem = null">×</button>
            </div>
            <div class="detail-body">
               <div class="detail-desc">{{ selectedOntologyItem.description }}</div>
               
               <!-- Attributes -->
               <div class="detail-section" v-if="selectedOntologyItem.attributes?.length">
                  <span class="section-label">ATTRIBUTES</span>
                  <div class="attr-list">
                     <div v-for="attr in selectedOntologyItem.attributes" :key="attr.name" class="attr-item">
                        <span class="attr-name">{{ attr.name }}</span>
                        <span class="attr-type">({{ attr.type }})</span>
                        <span class="attr-desc">{{ attr.description }}</span>
                     </div>
                  </div>
               </div>

               <!-- Examples (Entity) -->
               <div class="detail-section" v-if="selectedOntologyItem.examples?.length">
                  <span class="section-label">EXAMPLES</span>
                  <div class="example-list">
                     <span v-for="ex in selectedOntologyItem.examples" :key="ex" class="example-tag">{{ ex }}</span>
                  </div>
               </div>

               <!-- Source/Target (Relation) -->
               <div class="detail-section" v-if="selectedOntologyItem.source_targets?.length">
                  <span class="section-label">CONNECTIONS</span>
                  <div class="conn-list">
                     <div v-for="(conn, idx) in selectedOntologyItem.source_targets" :key="idx" class="conn-item">
                        <span class="conn-node">{{ conn.source }}</span>
                        <span class="conn-arrow">→</span>
                        <span class="conn-node">{{ conn.target }}</span>
                     </div>
                  </div>
               </div>
            </div>
          </div>

          <!-- Generated Entity Tags -->
          <div v-if="projectData?.ontology?.entity_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED ENTITY TYPES</span>
            <div class="tags-list">
              <span 
                v-for="entity in projectData.ontology.entity_types" 
                :key="entity.name" 
                class="entity-tag clickable"
                @click="selectOntologyItem(entity, 'entity')"
              >
                {{ entity.name }}
              </span>
            </div>
          </div>

          <!-- Generated Relation Tags -->
          <div v-if="projectData?.ontology?.edge_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED RELATION TYPES</span>
            <div class="tags-list">
              <span 
                v-for="rel in projectData.ontology.edge_types" 
                :key="rel.name" 
                class="entity-tag clickable"
                @click="selectOntologyItem(rel, 'relation')"
              >
                {{ rel.name }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: Graph Build -->
      <div class="step-card" :class="{ 'active': currentPhase === 1, 'completed': currentPhase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">{{ $t('step1.graphRagBuild') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 1" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 1" class="badge processing">{{ buildProgress?.progress || 0 }}%</span>
            <span v-else class="badge pending">{{ $t('step1.ontologyPending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/graph/build</p>
          <p class="description">
            {{ $t('step1.graphRagDesc') }}
          </p>
          
          <!-- Stats Cards -->
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.nodes }}</span>
              <span class="stat-label">{{ $t('step1.entityNodes') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.edges }}</span>
              <span class="stat-label">{{ $t('step1.relationEdges') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.types }}</span>
              <span class="stat-label">{{ $t('step1.schemaTypes') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: Complete -->
      <div class="step-card" :class="{ 'active': currentPhase === 2, 'completed': currentPhase >= 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">{{ $t('step1.buildComplete') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase >= 2" class="badge accent">{{ $t('step1.inProgress') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">{{ $t('step1.buildCompleteDesc') }}</p>
          <button 
            class="action-btn" 
            :disabled="currentPhase < 2 || creatingSimulation"
            @click="handleEnterEnvSetup"
          >
            <span v-if="creatingSimulation" class="spinner-sm"></span>
            {{ creatingSimulation ? $t('step1.creating') : $t('step1.enterEnvSetup') + ' ➝' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SYSTEM DASHBOARD</span>
        <span class="log-id">{{ projectData?.project_id || 'NO_PROJECT' }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { createSimulation } from '../api/simulation'

const router = useRouter()
const { t } = useI18n()

const props = defineProps({
  currentPhase: { type: Number, default: 0 },
  projectData: Object,
  ontologyProgress: Object,
  buildProgress: Object,
  graphData: Object,
  systemLogs: { type: Array, default: () => [] }
})

defineEmits(['next-step'])

const selectedOntologyItem = ref(null)
const logContent = ref(null)
const creatingSimulation = ref(false)

const handleEnterEnvSetup = async () => {
  if (!props.projectData?.project_id || !props.projectData?.graph_id) {
    console.error('缺少项目或图谱信息')
    return
  }
  
  creatingSimulation.value = true
  
  try {
    const res = await createSimulation({
      project_id: props.projectData.project_id,
      graph_id: props.projectData.graph_id,
      enable_twitter: true,
      enable_reddit: true
    })
    
    if (res.success && res.data?.simulation_id) {
      router.push({
        name: 'Simulation',
        params: { simulationId: res.data.simulation_id }
      })
    } else {
      console.error('创建模拟失败:', res.error)
      alert(t('step1.createSimulationFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    console.error('创建模拟异常:', err)
    alert(t('step1.createSimulationException', { error: err.message }))
  } finally {
    creatingSimulation.value = false
  }
}

const selectOntologyItem = (item, type) => {
  selectedOntologyItem.value = { ...item, itemType: type }
}

const graphStats = computed(() => {
  const nodes = props.graphData?.node_count || props.graphData?.nodes?.length || 0
  const edges = props.graphData?.edge_count || props.graphData?.edges?.length || 0
  const types = props.projectData?.ontology?.entity_types?.length || 0
  return { nodes, edges, types }
})

const formatDate = (dateStr) => {
  if (!dateStr) return '--:--:--'
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + d.getMilliseconds()
}

// Auto-scroll logs
watch(() => props.systemLogs.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.workbench-panel {
  height: 100%;
  background: var(--mf-bg-primary, #0a0a0f);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.scroll-container::-webkit-scrollbar {
  width: 6px;
}

.scroll-container::-webkit-scrollbar-track {
  background: transparent;
}

.scroll-container::-webkit-scrollbar-thumb {
  background: var(--mf-border, rgba(139, 92, 246, 0.3));
  border-radius: 3px;
}

.step-card {
  background: var(--mf-bg-secondary, #12121a);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  transition: all 0.3s ease;
  position: relative;
}

.step-card.active {
  border-color: var(--mf-accent, #8b5cf6);
  box-shadow: 0 0 30px rgba(139, 92, 246, 0.15);
}

.step-card.completed {
  border-color: var(--mf-success, #10b981);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 700;
  color: var(--mf-text-muted, #6b7280);
}

.step-card.active .step-num {
  color: var(--mf-accent, #8b5cf6);
  text-shadow: 0 0 20px rgba(139, 92, 246, 0.5);
}

.step-card.completed .step-num {
  color: var(--mf-success, #10b981);
}

.step-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
  color: var(--mf-text-primary, #f1f5f9);
}

.badge {
  font-size: 10px;
  padding: 4px 10px;
  border-radius: 20px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.badge.success { 
  background: rgba(16, 185, 129, 0.15); 
  color: var(--mf-success, #10b981);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.badge.processing { 
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(236, 72, 153, 0.2));
  color: var(--mf-accent, #8b5cf6);
  border: 1px solid rgba(139, 92, 246, 0.3);
  animation: pulse-glow 2s ease-in-out infinite;
}

.badge.accent { 
  background: linear-gradient(135deg, var(--mf-accent, #8b5cf6), #ec4899);
  color: white;
}

.badge.pending { 
  background: rgba(107, 114, 128, 0.15); 
  color: var(--mf-text-muted, #6b7280);
  border: 1px solid rgba(107, 114, 128, 0.2);
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 5px rgba(139, 92, 246, 0.3); }
  50% { box-shadow: 0 0 15px rgba(139, 92, 246, 0.5); }
}

.api-note {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--mf-text-muted, #6b7280);
  margin-bottom: 8px;
  padding: 4px 8px;
  background: rgba(139, 92, 246, 0.1);
  border-radius: 4px;
  display: inline-block;
}

.description {
  font-size: 12px;
  color: var(--mf-text-secondary, #94a3b8);
  line-height: 1.6;
  margin-bottom: 16px;
}

/* Step 01 Tags */
.tags-container {
  margin-top: 12px;
  transition: opacity 0.3s;
}

.tags-container.dimmed {
  opacity: 0.3;
  pointer-events: none;
}

.tag-label {
  display: block;
  font-size: 10px;
  color: var(--mf-text-muted, #6b7280);
  margin-bottom: 8px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-tag {
  background: var(--mf-bg-tertiary, #1a1a2e);
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 11px;
  color: var(--mf-text-primary, #f1f5f9);
  font-family: 'JetBrains Mono', monospace;
  transition: all 0.2s;
}

.entity-tag.clickable {
  cursor: pointer;
}

.entity-tag.clickable:hover {
  background: rgba(139, 92, 246, 0.15);
  border-color: var(--mf-accent, #8b5cf6);
  transform: translateY(-1px);
}

/* Ontology Detail Overlay */
.ontology-detail-overlay {
  position: absolute;
  top: 60px;
  left: 20px;
  right: 20px;
  bottom: 20px;
  background: rgba(18, 18, 26, 0.98);
  backdrop-filter: blur(12px);
  z-index: 10;
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.3));
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn { 
  from { opacity: 0; transform: translateY(5px); } 
  to { opacity: 1; transform: translateY(0); } 
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  background: rgba(139, 92, 246, 0.05);
}

.detail-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-type-badge {
  font-size: 9px;
  font-weight: 700;
  color: white;
  background: linear-gradient(135deg, var(--mf-accent, #8b5cf6), #ec4899);
  padding: 3px 8px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-name {
  font-size: 14px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: var(--mf-text-primary, #f1f5f9);
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
  color: var(--mf-text-muted, #6b7280);
  cursor: pointer;
  line-height: 1;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  color: var(--mf-text-primary, #f1f5f9);
  background: rgba(139, 92, 246, 0.1);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.detail-desc {
  font-size: 12px;
  color: var(--mf-text-secondary, #94a3b8);
  line-height: 1.6;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--mf-border, rgba(139, 92, 246, 0.2));
}

.detail-section {
  margin-bottom: 16px;
}

.section-label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--mf-accent, #8b5cf6);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.attr-list, .conn-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.attr-item {
  font-size: 11px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
  padding: 8px 10px;
  background: var(--mf-bg-tertiary, #1a1a2e);
  border-radius: 6px;
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.1));
}

.attr-name {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  color: var(--mf-accent, #8b5cf6);
}

.attr-type {
  color: var(--mf-text-muted, #6b7280);
  font-size: 10px;
}

.attr-desc {
  color: var(--mf-text-secondary, #94a3b8);
  flex: 1;
  min-width: 150px;
}

.example-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.example-tag {
  font-size: 11px;
  background: var(--mf-bg-tertiary, #1a1a2e);
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  padding: 4px 10px;
  border-radius: 20px;
  color: var(--mf-text-secondary, #94a3b8);
}

.conn-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  padding: 8px 10px;
  background: var(--mf-bg-tertiary, #1a1a2e);
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.1));
}

.conn-node {
  font-weight: 600;
  color: var(--mf-text-primary, #f1f5f9);
}

.conn-arrow {
  color: var(--mf-accent, #8b5cf6);
}

/* Step 02 Stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  background: var(--mf-bg-tertiary, #1a1a2e);
  padding: 16px;
  border-radius: 10px;
  border: 1px solid var(--mf-border, rgba(139, 92, 246, 0.1));
}

.stat-card {
  text-align: center;
  padding: 8px;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: var(--mf-accent, #8b5cf6);
  font-family: 'JetBrains Mono', monospace;
  text-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
}

.stat-label {
  font-size: 9px;
  color: var(--mf-text-muted, #6b7280);
  text-transform: uppercase;
  margin-top: 6px;
  display: block;
  letter-spacing: 0.5px;
}

/* Step 03 Button */
.action-btn {
  width: 100%;
  background: linear-gradient(135deg, var(--mf-accent, #8b5cf6), #ec4899);
  color: white;
  border: none;
  padding: 14px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(139, 92, 246, 0.4);
}

.action-btn:disabled {
  background: var(--mf-bg-tertiary, #1a1a2e);
  color: var(--mf-text-muted, #6b7280);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--mf-accent, #8b5cf6);
  margin-bottom: 12px;
  padding: 10px;
  background: rgba(139, 92, 246, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(139, 92, 246, 0.2);
}

.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(139, 92, 246, 0.3);
  border-top-color: var(--mf-accent, #8b5cf6);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* System Logs */
.system-logs {
  background: var(--mf-bg-secondary, #12121a);
  color: var(--mf-text-secondary, #94a3b8);
  padding: 16px;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px solid var(--mf-border, rgba(139, 92, 246, 0.2));
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid var(--mf-border, rgba(139, 92, 246, 0.15));
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 10px;
  color: var(--mf-text-muted, #6b7280);
}

.log-title {
  color: var(--mf-accent, #8b5cf6);
  font-weight: 600;
}

.log-id {
  color: var(--mf-text-muted, #6b7280);
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 80px;
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: var(--mf-border, rgba(139, 92, 246, 0.3));
  border-radius: 2px;
}

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time {
  color: var(--mf-text-muted, #6b7280);
  min-width: 75px;
}

.log-msg {
  color: var(--mf-text-secondary, #94a3b8);
  word-break: break-all;
}
</style>
