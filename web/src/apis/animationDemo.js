import { apiPost } from './base'

export const animationDemoApi = {
  create: (payload) => apiPost('/api/animation-demos', payload)
}
