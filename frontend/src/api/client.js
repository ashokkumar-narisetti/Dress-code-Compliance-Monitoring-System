git add .
git commit -m "Removed node_modules"/**
 * client.js - Axios instance pre-configured with the API base URL
 * and a request interceptor that attaches the JWT Authorization header.
 */

import axios from 'axios'

const client = axios.create({
    baseURL: '/api/v1',
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
