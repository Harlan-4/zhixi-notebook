import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/api', timeout: 300000 })

api.interceptors.response.use(
  (r) => r.data,
  (err) => {
    const detail = err.response?.data?.detail || err.message
    ElMessage.error({ message: String(detail), duration: 5000, showClose: true })
    return Promise.reject(err)
  }
)

export default api
