import { apiGet, apiPost } from './base'

export const getClawBotStatus = () => apiGet('/clawbot/status')
export const requestClawBotLogin = () => apiPost('/clawbot/login')
