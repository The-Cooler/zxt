import { apiGet, apiPost, apiPut, apiDelete } from './base'

/**
 * SubAgent 管理 API 模块
 * 包含 SubAgent 的增删改查功能
 */

const BASE_URL = '/api/system/subagents'

// =============================================================================
// === SubAgent CRUD ===
// =============================================================================

/**
 * 获取所有 SubAgent 配置
 * @returns {Promise} - SubAgent 列表
 */
export const getSubAgents = async () => {
  return apiGet(BASE_URL)
}

/**
 * 获取单个 SubAgent 配置
 * @param {string} name - SubAgent 名称
 * @returns {Promise} - SubAgent 配置
 */
export const getSubAgent = async (name) => {
  return apiGet(`${BASE_URL}/${encodeURIComponent(name)}`)
}

/**
 * 创建新的 SubAgent
 * @param {Object} data - SubAgent 配置数据
 * @returns {Promise} - 创建结果
 */
export const createSubAgent = async (data) => {
  return apiPost(BASE_URL, data)
}

/**
 * 更新 SubAgent 配置
 * @param {string} name - SubAgent 名称
 * @param {Object} data - 更新数据
 * @returns {Promise} - 更新结果
 */
export const updateSubAgent = async (name, data) => {
  return apiPut(`${BASE_URL}/${encodeURIComponent(name)}`, data)
}

/**
 * 删除 SubAgent
 * @param {string} name - SubAgent 名称
 * @returns {Promise} - 删除结果
 */
export const deleteSubAgent = async (name) => {
  return apiDelete(`${BASE_URL}/${encodeURIComponent(name)}`)
}

export const updateSubAgentStatus = async (name, enabled) => {
  return apiPut(`${BASE_URL}/${encodeURIComponent(name)}/status`, { enabled })
}

// =============================================================================
// === 导出为对象形式（兼容现有代码风格）===
// =============================================================================

export const subagentApi = {
  getSubAgents,
  getSubAgent,
  createSubAgent,
  updateSubAgent,
  deleteSubAgent,
  updateSubAgentStatus
}

export default subagentApi
