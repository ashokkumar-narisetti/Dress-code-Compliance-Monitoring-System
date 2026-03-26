/**
 * Login.jsx - Public login page for both Admin and Student roles.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'
import { ShieldCheck, Eye, EyeOff } from 'lucide-react'

export default function Login() {
    const { login } = useAuth()
    const navigate = useNavigate()

    const [form, setForm] = useState({ email: '', password: '' })
    const [showPw, setShowPw] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const handleChange = (e) => {
        setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))
        setError('')
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setError('')
        try {
            const { data } = await client.post('/auth/login', form)
            login(data)
            navigate(data.role === 'admin' ? '/admin' : '/student', { replace: true })
        } catch (err) {
            setError(err.response?.data?.detail || 'Login failed. Please check your credentials.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div style={styles.bg}>
            {/* Background glow blobs */}
            <div style={styles.blob1} />
            <div style={styles.blob2} />

            <div style={styles.card} className="fade-up">
                {/* Logo */}
                <div style={styles.logoWrap}>
                    <ShieldCheck size={36} color="#6366f1" strokeWidth={1.5} />
                </div>

                <h1 style={styles.title}>DressCode Monitor</h1>
                <p style={styles.subtitle}>Sign in to your account</p>

                {error && <div style={styles.errorBox}>{error}</div>}

                <form onSubmit={handleSubmit} style={styles.form}>
                    <div style={styles.fieldGroup}>
                        <label style={styles.label}>Email</label>
                        <input
                            id="email"
                            className="input"
                            type="email"
                            name="email"
                            value={form.email}
                            onChange={handleChange}
                            placeholder="you@dresscode.com"
                            required
                            autoComplete="email"
                        />
                    </div>

                    <div style={styles.fieldGroup}>
                        <label style={styles.label}>Password</label>
                        <div style={styles.pwWrap}>
                            <input
                                id="password"
                                className="input"
                                type={showPw ? 'text' : 'password'}
                                name="password"
                                value={form.password}
                                onChange={handleChange}
                                placeholder="••••••••"
                                required
                                autoComplete="current-password"
                                style={{ paddingRight: 44 }}
                            />
                            <button
                                type="button"
                                style={styles.eyeBtn}
                                onClick={() => setShowPw(v => !v)}
                                aria-label="Toggle password visibility"
                            >
                                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </div>

                    <button
                        id="login-submit"
                        type="submit"
                        className="btn btn-primary"
                        disabled={loading}
                        style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
                    >
                        {loading ? <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} /> : 'Sign In'}
                    </button>
                </form>

                <div style={styles.demoHints}>
                    <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)', textAlign: 'center', marginBottom: 8 }}>
                        Demo credentials
                    </p>
                    <div style={styles.demoRow}>
                        <span className="badge badge-primary">Admin</span>
                        <code style={styles.code}>admin@dresscode.com / admin123</code>
                    </div>
                    <div style={styles.demoRow}>
                        <span className="badge badge-success">Student</span>
                        <code style={styles.code}>arjun@dresscode.com / student123</code>
                    </div>
                </div>
            </div>
        </div>
    )
}

const styles = {
    bg: {
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--color-bg)',
        padding: 24,
        overflow: 'hidden',
        position: 'relative',
    },
    blob1: {
        position: 'absolute',
        width: 400,
        height: 400,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(99,102,241,0.18) 0%, transparent 70%)',
        top: -100,
        left: -100,
        pointerEvents: 'none',
    },
    blob2: {
        position: 'absolute',
        width: 300,
        height: 300,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(16,185,129,0.12) 0%, transparent 70%)',
        bottom: -80,
        right: -60,
        pointerEvents: 'none',
    },
    card: {
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: '40px 36px',
        width: '100%',
        maxWidth: 420,
        position: 'relative',
        zIndex: 1,
        boxShadow: 'var(--shadow-lg)',
    },
    logoWrap: {
        display: 'flex',
        justifyContent: 'center',
        marginBottom: 20,
    },
    title: {
        fontSize: 'var(--font-size-2xl)',
        fontWeight: 800,
        textAlign: 'center',
        letterSpacing: '-0.02em',
        marginBottom: 6,
    },
    subtitle: {
        color: 'var(--color-text-muted)',
        textAlign: 'center',
        fontSize: 'var(--font-size-sm)',
        marginBottom: 28,
    },
    errorBox: {
        background: 'rgba(239,68,68,0.1)',
        border: '1px solid rgba(239,68,68,0.3)',
        color: 'var(--color-danger)',
        borderRadius: 'var(--radius-sm)',
        padding: '10px 14px',
        fontSize: 'var(--font-size-sm)',
        marginBottom: 16,
    },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
    },
    fieldGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
    },
    label: {
        fontSize: 'var(--font-size-sm)',
        fontWeight: 500,
        color: 'var(--color-text-muted)',
    },
    pwWrap: { position: 'relative' },
    eyeBtn: {
        position: 'absolute',
        right: 12,
        top: '50%',
        transform: 'translateY(-50%)',
        background: 'none',
        border: 'none',
        color: 'var(--color-text-muted)',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
    },
    demoHints: {
        marginTop: 28,
        borderTop: '1px solid var(--color-border)',
        paddingTop: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
    },
    demoRow: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
    },
    code: {
        fontSize: 11,
        color: 'var(--color-text-muted)',
        background: 'var(--color-surface-2)',
        padding: '2px 6px',
        borderRadius: 4,
    },
}
