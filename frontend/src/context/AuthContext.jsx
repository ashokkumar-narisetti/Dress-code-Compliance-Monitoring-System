/**
 * AuthContext.jsx
 * Provides authentication state (user info, JWT token) across the app.
 * Stores token in localStorage so session persists on refresh.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { jwtDecode } from 'jwt-decode'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const [token, setToken] = useState(() => localStorage.getItem('dcm_token'))
    const [user, setUser] = useState(null)
    const [loading, setLoading] = useState(true)

    // Decode stored token on mount
    useEffect(() => {
        if (token) {
            try {
                const decoded = jwtDecode(token)
                // Check expiry
                if (decoded.exp * 1000 < Date.now()) {
                    logout()
                } else {
                    setUser(decoded)
                }
            } catch {
                logout()
            }
        }
        setLoading(false)
    }, [])

    const login = useCallback((tokenData) => {
        // tokenData is the full TokenResponse from /auth/login
        const tok = tokenData.access_token
        localStorage.setItem('dcm_token', tok)
        // Also store role and name for quick access without decoding
        localStorage.setItem('dcm_role', tokenData.role)
        localStorage.setItem('dcm_name', tokenData.name)
        localStorage.setItem('dcm_user_id', String(tokenData.user_id))
        setToken(tok)
        setUser({
            sub: String(tokenData.user_id),
            role: tokenData.role,
            name: tokenData.name,
            user_id: tokenData.user_id,
        })
    }, [])

    const logout = useCallback(() => {
        localStorage.removeItem('dcm_token')
        localStorage.removeItem('dcm_role')
        localStorage.removeItem('dcm_name')
        localStorage.removeItem('dcm_user_id')
        setToken(null)
        setUser(null)
    }, [])

    return (
        <AuthContext.Provider value={{ token, user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
    const ctx = useContext(AuthContext)
    if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
    return ctx
}
