/**
 * client.js - Axios instance pre-configured with the API base URL
 * and a request interceptor that attaches the JWT Authorization header.
 */

import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const client = axios.create({
    baseURL: `${API_BASE_URL}/api/v1`,
    headers: { 'Content-Type': 'application/json' },
})

// Attach token from localStorage on every request
client.interceptors.request.use((config) => {
    const token = localStorage.getItem('dcm_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Redirect to login on 401
client.interceptors.response.use(
    (res) => res,
    (err) => {
        if (err.response?.status === 401) {
            localStorage.clear()
            window.location.href = '/login'
        }
        return Promise.reject(err)
    }
)

export default client
