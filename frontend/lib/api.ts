import axios from "axios"
import Cookies from "js-cookie"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export const api = axios.create({
    baseURL: API_URL,
    withCredentials: true, // Send httpOnly cookies (refresh_token)
})

// Attach access token to every request
api.interceptors.request.use((config) => {
    const token = Cookies.get("access_token")
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Handle 401 responses: try refresh, then redirect to login
let isRefreshing = false
let failedQueue: Array<{ resolve: (value: any) => void; reject: (reason?: any) => void }> = []

const processQueue = (error: any, token: string | null = null) => {
    failedQueue.forEach((prom) => {
        if (error) {
            prom.reject(error)
        } else {
            prom.resolve(token)
        }
    })
    failedQueue = []
}

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config

        // Only handle 401s, and don't retry login/register/refresh endpoints
        if (
            error.response?.status === 401 &&
            !originalRequest._retry &&
            !originalRequest.url?.includes("/auth/login") &&
            !originalRequest.url?.includes("/auth/register") &&
            !originalRequest.url?.includes("/auth/refresh")
        ) {
            if (isRefreshing) {
                // Queue requests while refreshing
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject })
                }).then((token) => {
                    originalRequest.headers.Authorization = `Bearer ${token}`
                    return api(originalRequest)
                })
            }

            originalRequest._retry = true
            isRefreshing = true

            try {
                // Try to refresh using the httpOnly cookie
                const res = await axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true })
                const newToken = res.data.access_token
                Cookies.set("access_token", newToken, { path: "/" })
                originalRequest.headers.Authorization = `Bearer ${newToken}`
                processQueue(null, newToken)
                return api(originalRequest)
            } catch (refreshError) {
                processQueue(refreshError, null)
                // Refresh failed — session is truly expired, redirect to login
                Cookies.remove("access_token")
                if (typeof window !== "undefined") {
                    window.location.href = "/login"
                }
                return Promise.reject(refreshError)
            } finally {
                isRefreshing = false
            }
        }

        return Promise.reject(error)
    }
)
