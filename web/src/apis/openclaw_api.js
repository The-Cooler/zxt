import { apiGet, apiPost, apiPut } from './base'

export async function getOpenClawStatus() {
  return apiGet('/openclaw/status')
}

export async function testOpenClawConnection() {
  return apiPost('/openclaw/test-connection')
}

export async function triggerReminder() {
  return apiPost('/openclaw/trigger-reminder')
}

export async function getOpenClawConfig() {
  return apiGet('/openclaw/config')
}

export async function updateOpenClawConfig(data) {
  return apiPut('/openclaw/config', data)
}
