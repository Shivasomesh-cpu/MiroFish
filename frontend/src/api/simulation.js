import service, { requestWithRetry } from './index'

/**
 * 创建模拟
 * @param {Object} data - { project_id, graph_id?, enable_twitter?, enable_reddit? }
 */
export const createSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/create', data), 3, 1000)
}

/**
 * 准备模拟环境（异步任务）
 * @param {Object} data - { simulation_id, entity_types?, use_llm_for_profiles?, parallel_profile_count?, force_regenerate? }
 */
export const prepareSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/prepare', data), 3, 1000)
}

/**
 * 查询准备任务进度
 * @param {Object} data - { task_id?, simulation_id? }
 */
export const getPrepareStatus = (data) => {
  return service.post('/api/simulation/prepare/status', data)
}

/**
 * 获取模拟状态
 * @param {string} simulationId
 */
export const getSimulation = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}`)
}

/**
 * 获取模拟的 Agent Profiles
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 */
export const getSimulationProfiles = (simulationId, platform = 'reddit') => {
  return service.get(`/api/simulation/${simulationId}/profiles`, { params: { platform } })
}

/**
 * 实时获取生成中的 Agent Profiles
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 */
export const getSimulationProfilesRealtime = (simulationId, platform = 'reddit') => {
  return service.get(`/api/simulation/${simulationId}/profiles/realtime`, { params: { platform } })
}

/**
 * 获取模拟配置
 * @param {string} simulationId
 */
export const getSimulationConfig = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config`)
}

/**
 * 实时获取生成中的模拟配置
 * @param {string} simulationId
 * @returns {Promise} 返回配置信息，包含元数据和配置内容
 */
export const getSimulationConfigRealtime = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config/realtime`)
}

/**
 * 列出所有模拟
 * @param {string} projectId - 可选，按项目ID过滤
 */
export const listSimulations = (projectId) => {
  const params = projectId ? { project_id: projectId } : {}
  return service.get('/api/simulation/list', { params })
}

/**
 * 启动模拟
 * @param {Object} data - { simulation_id, platform?, max_rounds?, enable_graph_memory_update? }
 */
export const startSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/start', data), 3, 1000)
}

/**
 * 停止模拟
 * @param {Object} data - { simulation_id }
 */
export const stopSimulation = (data) => {
  return service.post('/api/simulation/stop', data)
}

/**
 * 获取模拟运行实时状态
 * @param {string} simulationId
 */
export const getRunStatus = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status`)
}

/**
 * 获取模拟运行详细状态（包含最近动作）
 * @param {string} simulationId
 */
export const getRunStatusDetail = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status/detail`)
}

/**
 * 获取模拟中的帖子
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 * @param {number} limit - 返回数量
 * @param {number} offset - 偏移量
 */
export const getSimulationPosts = (simulationId, platform = 'reddit', limit = 50, offset = 0) => {
  return service.get(`/api/simulation/${simulationId}/posts`, {
    params: { platform, limit, offset }
  })
}

/**
 * 获取模拟时间线（按轮次汇总）
 * @param {string} simulationId
 * @param {number} startRound - 起始轮次
 * @param {number} endRound - 结束轮次
 */
export const getSimulationTimeline = (simulationId, startRound = 0, endRound = null) => {
  const params = { start_round: startRound }
  if (endRound !== null) {
    params.end_round = endRound
  }
  return service.get(`/api/simulation/${simulationId}/timeline`, { params })
}

/**
 * 获取Agent统计信息
 * @param {string} simulationId
 */
export const getAgentStats = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/agent-stats`)
}

/**
 * 获取模拟动作历史
 * @param {string} simulationId
 * @param {Object} params - { limit, offset, platform, agent_id, round_num }
 */
export const getSimulationActions = (simulationId, params = {}) => {
  return service.get(`/api/simulation/${simulationId}/actions`, { params })
}

/**
 * 关闭模拟环境（优雅退出）
 * @param {Object} data - { simulation_id, timeout? }
 */
export const closeSimulationEnv = (data) => {
  return service.post('/api/simulation/close-env', data)
}

/**
 * 获取模拟环境状态
 * @param {Object} data - { simulation_id }
 */
export const getEnvStatus = (data) => {
  return service.post('/api/simulation/env-status', data)
}

/**
 * 批量采访 Agent
 * @param {Object} data - { simulation_id, interviews: [{ agent_id, prompt }] }
 */
export const interviewAgents = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/interview/batch', data), 3, 1000)
}

/**
 * 获取历史模拟列表（带项目详情）
 * 用于首页历史项目展示
 * @param {number} limit - 返回数量限制
 */
export const getSimulationHistory = (limit = 20) => {
  return service.get('/api/simulation/history', { params: { limit } })
}

// ============== SSE Real-time Updates ==============

/**
 * Create a Server-Sent Events connection for real-time simulation updates.
 * 
 * This replaces polling-based updates with push-based streaming.
 * 
 * @param {string} simulationId - The simulation ID to subscribe to
 * @param {Object} callbacks - Event callbacks
 * @param {Function} callbacks.onInit - Called with initial state
 * @param {Function} callbacks.onStateUpdate - Called on state changes
 * @param {Function} callbacks.onStepComplete - Called when a round completes
 * @param {Function} callbacks.onDone - Called when simulation finishes
 * @param {Function} callbacks.onError - Called on error
 * @param {Function} callbacks.onConnectionError - Called on connection failure
 * @returns {Object} - Object with close() method to disconnect
 * 
 * @example
 * const stream = subscribeToSimulation('sim_xxx', {
 *   onStateUpdate: (data) => console.log('State:', data),
 *   onStepComplete: (data) => console.log('Round:', data.current_round),
 *   onDone: (data) => console.log('Done!'),
 *   onError: (data) => console.error('Error:', data.error)
 * })
 * 
 * // Later: disconnect
 * stream.close()
 */
export const subscribeToSimulation = (simulationId, callbacks = {}) => {
  const baseUrl = import.meta.env.VITE_API_URL || ''
  const url = `${baseUrl}/api/stream/${simulationId}`
  
  let eventSource = null
  let retryCount = 0
  const maxRetries = 5
  const baseRetryDelay = 1000 // 1 second
  
  const connect = () => {
    eventSource = new EventSource(url)
    
    eventSource.onopen = () => {
      retryCount = 0 // Reset retry count on successful connection
      console.log(`[SSE] Connected to simulation ${simulationId}`)
    }
    
    eventSource.onerror = (error) => {
      console.warn(`[SSE] Connection error for ${simulationId}:`, error)
      eventSource.close()
      
      // Attempt reconnection with exponential backoff
      if (retryCount < maxRetries) {
        retryCount++
        const delay = baseRetryDelay * Math.pow(2, retryCount - 1)
        console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${retryCount}/${maxRetries})`)
        setTimeout(connect, delay)
      } else {
        console.error(`[SSE] Max retries exceeded for ${simulationId}`)
        if (callbacks.onConnectionError) {
          callbacks.onConnectionError({ 
            message: 'Connection lost after max retries',
            retries: maxRetries 
          })
        }
      }
    }
    
    // Event handlers
    eventSource.addEventListener('init', (event) => {
      const data = JSON.parse(event.data)
      if (callbacks.onInit) callbacks.onInit(data)
    })
    
    eventSource.addEventListener('state_update', (event) => {
      const data = JSON.parse(event.data)
      if (callbacks.onStateUpdate) callbacks.onStateUpdate(data)
    })
    
    eventSource.addEventListener('step_complete', (event) => {
      const data = JSON.parse(event.data)
      if (callbacks.onStepComplete) callbacks.onStepComplete(data)
    })
    
    eventSource.addEventListener('simulation_done', (event) => {
      const data = JSON.parse(event.data)
      if (callbacks.onDone) callbacks.onDone(data)
      eventSource.close()
    })
    
    eventSource.addEventListener('simulation_error', (event) => {
      const data = JSON.parse(event.data)
      if (callbacks.onError) callbacks.onError(data)
      eventSource.close()
    })
    
    eventSource.addEventListener('simulation_stopped', (event) => {
      const data = JSON.parse(event.data)
      if (callbacks.onStopped) callbacks.onStopped(data)
      eventSource.close()
    })
    
    eventSource.addEventListener('heartbeat', () => {
      // Heartbeat received, connection is alive
    })
  }
  
  // Start connection
  connect()
  
  // Return control object
  return {
    close: () => {
      if (eventSource) {
        eventSource.close()
        console.log(`[SSE] Disconnected from simulation ${simulationId}`)
      }
    },
    getReadyState: () => eventSource ? eventSource.readyState : -1
  }
}

// ============== Job Queue API ==============

/**
 * List all simulation jobs
 * @param {Object} params - { limit, offset, status }
 */
export const listJobs = (params = {}) => {
  return service.get('/api/simulation/jobs', { params })
}

/**
 * Get a specific job
 * @param {string} jobId
 */
export const getJob = (jobId) => {
  return service.get(`/api/simulation/jobs/${jobId}`)
}

/**
 * Get interrupted/restartable jobs
 */
export const getInterruptedJobs = () => {
  return service.get('/api/simulation/jobs/interrupted')
}

/**
 * Restart an interrupted job
 * @param {string} jobId
 * @param {Object} data - { from_checkpoint, max_rounds }
 */
export const restartJob = (jobId, data = {}) => {
  return service.post(`/api/simulation/jobs/${jobId}/restart`, data)
}

/**
 * Delete a job record
 * @param {string} jobId
 */
export const deleteJob = (jobId) => {
  return service.delete(`/api/simulation/jobs/${jobId}`)
}

// ============== Pause/Resume/Checkpoint API ==============

/**
 * Pause a running simulation and create a checkpoint
 * @param {string} simulationId
 * @param {Object} data - { description }
 */
export const pauseSimulation = (simulationId, data = {}) => {
  return service.post(`/api/simulation/${simulationId}/pause`, data)
}

/**
 * Resume a paused simulation from checkpoint
 * @param {string} simulationId
 * @param {Object} data - { checkpoint_id, max_rounds }
 */
export const resumeSimulation = (simulationId, data = {}) => {
  return service.post(`/api/simulation/${simulationId}/resume`, data)
}

/**
 * List all checkpoints for a simulation
 * @param {string} simulationId
 */
export const listCheckpoints = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/checkpoints`)
}

/**
 * Get details of a specific checkpoint
 * @param {string} simulationId
 * @param {string} checkpointId
 */
export const getCheckpoint = (simulationId, checkpointId) => {
  return service.get(`/api/simulation/${simulationId}/checkpoints/${checkpointId}`)
}

/**
 * Create a manual checkpoint
 * @param {string} simulationId
 * @param {Object} data - { description }
 */
export const createCheckpoint = (simulationId, data = {}) => {
  return service.post(`/api/simulation/${simulationId}/checkpoints`, data)
}

/**
 * Delete a checkpoint
 * @param {string} simulationId
 * @param {string} checkpointId
 */
export const deleteCheckpoint = (simulationId, checkpointId) => {
  return service.delete(`/api/simulation/${simulationId}/checkpoints/${checkpointId}`)
}

// ============== Cost Tracking API ==============

/**
 * Estimate the cost of running a simulation
 * @param {Object} data - { num_agents, num_rounds, model_name }
 */
export const estimateCost = (data) => {
  return service.post('/api/simulation/cost/estimate', data)
}

/**
 * Get current cost tracking for a simulation
 * @param {string} simulationId
 */
export const getSimulationCost = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/cost`)
}
