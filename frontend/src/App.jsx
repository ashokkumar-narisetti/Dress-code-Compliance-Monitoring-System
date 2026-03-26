/**
 * App.jsx - Root router with role-based protected routes.
 *
 * Route map:
 *   /login           → Login page (public)
 *   /admin/*         → Admin Dashboard (admin only)
 *   /student/*       → Student Dashboard (student only)
 *   /                → redirect based on role
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login from './pages/Login'
import AdminDashboard from './pages/AdminDashboard'
import StudentDashboard from './pages/StudentDashboard'

function ProtectedRoute({ children, requiredRole }) {
    const { user, loading } = useAuth()

    if (loading) return (
        <div className="center-fill">
            <div className="spinner" />
        </div>
    )

    if (!user) return <Navigate to="/login" replace />
    if (requiredRole && user.role !== requiredRole) {
        return <Navigate to={user.role === 'admin' ? '/admin' : '/student'} replace />
    }
    return children
}

function RootRedirect() {
    const { user, loading } = useAuth()
    if (loading) return <div className="center-fill"><div className="spinner" /></div>
    if (!user) return <Navigate to="/login" replace />
    return <Navigate to={user.role === 'admin' ? '/admin' : '/student'} replace />
}

export default function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/login" element={<Login />} />
                    <Route
                        path="/admin/*"
                        element={
                            <ProtectedRoute requiredRole="admin">
                                <AdminDashboard />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/student/*"
                        element={
                            <ProtectedRoute requiredRole="student">
                                <StudentDashboard />
                            </ProtectedRoute>
                        }
                    />
                    <Route path="*" element={<RootRedirect />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    )
}
