import { apiGet, apiPost } from './base'

export const getClawBotStatus = () => apiGet('/api/clawbot/status')
export const requestClawBotLogin = () => apiPost('/api/clawbot/login')
