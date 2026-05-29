import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { ShieldCheck, LogOut, Bell, MessageSquare, History, UserCircle, ZoomIn } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'

const formatDate = (v) => new Date(v).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const scoreColor = (s) => (s >= 80 ? 'var(--color-success)' : s >= 60 ? 'var(--color-warning)' : 'var(--color-danger)')

/* ── Lightbox ────────────────────────────────────────────────────────────── */
function ImageModal({ src, onClose }) {
    if (!src) return null
    return (
        <div
            onClick={onClose}
            style={{
                position: 'fixed', inset: 0, zIndex: 1000,
                background: 'rgba(0,0,0,0.88)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'zoom-out',
            }}
        >
            <img
                src={src}
                alt="Evidence"
                onClick={(e) => e.stopPropagation()}
                style={{
                    maxWidth: '90vw', maxHeight: '88vh',
                    borderRadius: 10, border: '2px solid rgba(255,255,255,0.15)',
                    boxShadow: '0 8px 48px rgba(0,0,0,0.6)',
                    cursor: 'default',
                }}
            />
            <button
                onClick={onClose}
                style={{
                    position: 'absolute', top: 18, right: 22,
                    background: 'rgba(255,255,255,0.12)', border: 'none',
                    borderRadius: 8, padding: '6px 12px', color: '#fff',
                    fontSize: 14, cursor: 'pointer',
                }}
            >✕ Close</button>
        </div>
    )
}

/* ── Clickable Evidence Thumb ────────────────────────────────────────────── */
function EvidenceThumb({ path, onOpen, size = 80 }) {
    if (!path) return null
    // Clean up slashes just in case
    const cleanPath = path.replace(/\\/g, '/').replace(/^\/+/, '')
    const url = cleanPath.startsWith('http') ? cleanPath : `https://dress-code-api.onrender.com/${cleanPath}`
    return (
        <div
            style={{ position: 'relative', display: 'inline-block', cursor: 'pointer', borderRadius: 8, overflow: 'hidden' }}
            onClick={() => onOpen(url)}
            title="Click to view full size"
        >
            <img
                src={url}
                alt="evidence"
                style={{ width: size, height: size, objectFit: 'cover', display: 'block', border: '2px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
            />
            <div style={{
                position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.40)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                opacity: 0, transition: 'opacity 0.2s', borderRadius: 8,
            }}
                onMouseEnter={e => e.currentTarget.style.opacity = 1}
                onMouseLeave={e => e.currentTarget.style.opacity = 0}
            >
                <ZoomIn size={20} color="#fff" />
                <span style={{ color: '#fff', fontSize: 11, fontWeight: 600 }}>View</span>
            </div>
        </div>
    )
}

export default function StudentDashboard() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()
    const [lightboxSrc, setLightboxSrc] = useState(null)

    const [profile, setProfile] = useState(null)
    const [dashboard, setDashboard] = useState({ score: 100, unread_alerts: 0, pending_alerts: 0, pending_appeals: 0 })
    const [alerts, setAlerts] = useState([])
    const [appeals, setAppeals] = useState([])
    const [history, setHistory] = useState([])
    const [scoreHistory, setScoreHistory] = useState([])
    const [photos, setPhotos] = useState([])
    const [activeTab, setActiveTab] = useState('home')
    const [appealTarget, setAppealTarget] = useState(null)
    const [appealText, setAppealText] = useState('')
    const [appealProof, setAppealProof] = useState(null)
    const [info, setInfo] = useState('')
    const [error, setError] = useState('')

    const appealMap = useMemo(() => {
        const map = {}
        appeals.forEach((a) => { map[a.alert_id] = a })
        return map
    }, [appeals])

    const loadAll = async () => {
        try {
            const [p, d, a, ap, h, sh, ph] = await Promise.all([
                client.get('/student/me'),
                client.get('/student/dashboard-v2'),
                client.get('/student/alerts'),
                client.get('/student/appeals-v2'),
                client.get('/student/compliance-history'),
                client.get('/student/score-history'),
                client.get('/student/profile/photos'),
            ])
            setProfile(p.data)
            setDashboard(d.data)
            setAlerts(a.data)
            setAppeals(ap.data)
            setHistory(h.data)
            setScoreHistory(sh.data)
            setPhotos(ph.data)
        } catch (e) {
            setError(e.response?.data?.detail || 'Failed to load dashboard')
        }
    }

    useEffect(() => { loadAll() }, [])

    const signOut = () => { logout(); navigate('/login') }

    const markRead = async (alertId) => {
        try { await client.post(`/student/alerts/${alertId}/read`); loadAll() }
        catch (e) { setError(e.response?.data?.detail || 'Failed to mark as read') }
    }

    const submitAppeal = async () => {
        if (!appealTarget || !appealText.trim()) return
        const fd = new FormData()
        fd.append('justification', appealText.trim())
        if (appealProof) fd.append('proof', appealProof)
        try {
            await client.post(`/student/alerts/${appealTarget.id}/appeal`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
            setInfo('Appeal submitted successfully.')
            setAppealTarget(null); setAppealText(''); setAppealProof(null)
            loadAll()
        } catch (e) {
            setError(e.response?.data?.detail || 'Appeal submission failed')
        }
    }

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg)' }}>
            {/* ── Topbar ── */}
            <div style={{ background: 'var(--color-surface)', borderBottom: '1px solid var(--color-border)', padding: '12px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <ShieldCheck size={22} color="var(--color-primary)" />
                    <strong>Dress<span style={{ color: 'var(--color-primary)' }}>Code</span></strong>
                    <span className="badge badge-success">Student</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>{user?.name}</span>
                    <button className="btn btn-ghost" style={{ padding: '6px 12px' }} onClick={signOut}><LogOut size={14} /> Sign Out</button>
                </div>
            </div>

            <div style={{ maxWidth: 980, margin: '0 auto', padding: 20 }}>
                {info && <div className="card-sm" style={{ color: 'var(--color-success)', marginBottom: 10 }}>{info}</div>}
                {error && <div className="card-sm" style={{ color: 'var(--color-danger)', marginBottom: 10, cursor: 'pointer' }} onClick={() => setError('')}>{error} ✕</div>}

                {/* ── Stats ── */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10, marginBottom: 14 }}>
                    <div className="stat-card"><span className="stat-label">Credit Score</span><span className="stat-value" style={{ color: scoreColor(dashboard.score) }}>{dashboard.score}</span></div>
                    <div className="stat-card"><span className="stat-label">Unread Alerts</span><span className="stat-value">{dashboard.unread_alerts}</span></div>
                    <div className="stat-card"><span className="stat-label">Pending Alerts</span><span className="stat-value">{dashboard.pending_alerts}</span></div>
                    <div className="stat-card"><span className="stat-label">Pending Appeals</span><span className="stat-value">{dashboard.pending_appeals}</span></div>
                </div>

                {/* ── Tabs ── */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                    <button className={`btn ${activeTab === 'home' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setActiveTab('home')}><ShieldCheck size={14} /> Home</button>
                    <button className={`btn ${activeTab === 'alerts' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setActiveTab('alerts')}>
                        <Bell size={14} /> Alerts {dashboard.unread_alerts > 0 && <span className="badge badge-danger" style={{ marginLeft: 4 }}>{dashboard.unread_alerts}</span>}
                    </button>
                    <button className={`btn ${activeTab === 'history' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setActiveTab('history')}><History size={14} /> History</button>
                    <button className={`btn ${activeTab === 'profile' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setActiveTab('profile')}><UserCircle size={14} /> Profile</button>
                </div>

                {/* ── Home ── */}
                {activeTab === 'home' && <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div className="card">
                        <h3 style={{ marginBottom: 8 }}>Score History</h3>
                        {scoreHistory.length < 2 ? (
                            <p style={{ color: 'var(--color-text-muted)' }}>Not enough data points yet. Score changes will appear here.</p>
                        ) : (
                            <ResponsiveContainer width="100%" height={220}>
                                <LineChart data={scoreHistory.map((s) => ({ t: formatDate(s.recorded_at), score: s.score }))}>
                                    <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                                    <XAxis dataKey="t" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} hide />
                                    <YAxis domain={[0, 100]} tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} />
                                    <Tooltip />
                                    <Line type="monotone" dataKey="score" stroke="var(--color-primary)" strokeWidth={2.5} dot={{ r: 3 }} />
                                </LineChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                    <div className="card">
                        <h3 style={{ marginBottom: 8 }}>Quick Status</h3>
                        <p style={{ color: dashboard.pending_alerts > 0 ? 'var(--color-warning)' : 'var(--color-success)' }}>
                            {dashboard.pending_alerts > 0
                                ? `⚠ You have ${dashboard.pending_alerts} pending alert${dashboard.pending_alerts > 1 ? 's' : ''} requiring attention.`
                                : '✓ You are currently compliant. Keep it up!'}
                        </p>
                    </div>
                </div>}

                {/* ── Alerts ── */}
                {activeTab === 'alerts' && <div className="card">
                    <h3 style={{ marginBottom: 10 }}>Alert Notifications</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {alerts.map((a) => {
                            const appeal = appealMap[a.id]
                            return (
                                <div key={a.id} className="card-sm" style={{ display: 'flex', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                                    {/* Evidence image - prominent, left side */}
                                    {a.frame_path && (
                                        <EvidenceThumb path={a.frame_path} onOpen={setLightboxSrc} size={96} />
                                    )}
                                    <div style={{ flex: 1, minWidth: 200 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                            <strong>Alert #{a.id}</strong>
                                            {!a.is_read && <span className="badge badge-warning">NEW</span>}
                                            {appeal && <span className={`badge ${appeal.status === 'approved' ? 'badge-success' : appeal.status === 'rejected' ? 'badge-danger' : 'badge-warning'}`}>Appeal {appeal.status}</span>}
                                        </div>
                                        <div style={{ marginBottom: 4 }}>{a.message}</div>
                                        <div style={{ color: 'var(--color-danger)', fontWeight: 600, fontSize: 14 }}>−{a.score_deducted} credit points</div>
                                        <div style={{ color: 'var(--color-text-muted)', fontSize: 12, marginTop: 2 }}>{formatDate(a.sent_at)} · Status: {a.status}</div>
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignSelf: 'center' }}>
                                        {!a.is_read && (
                                            <button className="btn btn-ghost" style={{ padding: '6px 10px' }} onClick={() => markRead(a.id)}>Mark Read</button>
                                        )}
                                        {!appeal && a.status !== 'resolved' && (
                                            <button className="btn btn-primary" style={{ padding: '6px 10px' }} onClick={() => setAppealTarget(a)}>
                                                <MessageSquare size={14} /> Appeal
                                            </button>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                        {alerts.length === 0 && <div style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: 24 }}>No alerts yet. You're compliant! 🎉</div>}
                    </div>
                </div>}

                {/* ── History ── */}
                {activeTab === 'history' && <div className="card">
                    <h3 style={{ marginBottom: 10 }}>Score History Ledger</h3>
                    <div className="table-wrapper">
                        <table>
                            <thead><tr><th>Time</th><th>Reason</th><th>Change</th><th>Alert</th></tr></thead>
                            <tbody>
                                {history.map((h) => <tr key={h.id}>
                                    <td>{formatDate(h.timestamp)}</td>
                                    <td>{h.reason}</td>
                                    <td style={{ color: h.change_amount < 0 ? 'var(--color-danger)' : 'var(--color-success)', fontWeight: 600 }}>{h.change_amount > 0 ? '+' : ''}{h.change_amount}</td>
                                    <td>{h.alert_id ? `#${h.alert_id}` : '-'}</td>
                                </tr>)}
                                {history.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--color-text-muted)' }}>No score history yet.</td></tr>}
                            </tbody>
                        </table>
                    </div>
                </div>}

                {/* ── Profile ── */}
                {activeTab === 'profile' && <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div className="card">
                        <h3 style={{ marginBottom: 8 }}>My Profile</h3>
                        <p>Name: <strong>{profile?.name}</strong></p>
                        <p>Email: {profile?.email}</p>
                        <p>Department: {profile?.department || '—'}</p>
                        <p style={{ marginTop: 8, color: 'var(--color-text-muted)', fontSize: 13 }}>
                            Credit Score: <span style={{ color: scoreColor(dashboard.score), fontWeight: 700 }}>{dashboard.score} / 100</span>
                        </p>
                    </div>
                    <div className="card">
                        <h3 style={{ marginBottom: 8 }}>Registered Face Photos</h3>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: 13, marginBottom: 8 }}>
                            These photos are used to identify you in surveillance videos.
                        </p>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {photos.map((p) => <EvidenceThumb key={p.id} path={p.photo_path} onOpen={setLightboxSrc} size={96} />)}
                            {photos.length === 0 && <span style={{ color: 'var(--color-text-muted)' }}>No face photos registered yet. Contact admin.</span>}
                        </div>
                    </div>
                </div>}
            </div>

            {/* ── Appeal Modal ── */}
            {appealTarget && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 999 }}>
                    <div className="card" style={{ maxWidth: 520, width: '100%' }}>
                        <h3 style={{ marginBottom: 8 }}>Appeal Alert #{appealTarget.id}</h3>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: 13, marginBottom: 10 }}>
                            Explain why you believe this violation is incorrect. You may also attach supporting proof.
                        </p>
                        <textarea className="input" rows={4}
                            placeholder="e.g. I was wearing proper uniform on that day. The camera angle may have been misleading."
                            value={appealText} onChange={(e) => setAppealText(e.target.value)} />
                        <input className="input" style={{ marginTop: 8 }} type="file" accept=".jpg,.jpeg,.png,.webp"
                            onChange={(e) => setAppealProof(e.target.files?.[0] || null)} />
                        {appealProof && <div style={{ fontSize: 12, color: 'var(--color-success)', marginTop: 4 }}>✓ {appealProof.name}</div>}
                        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                            <button className="btn btn-primary" onClick={submitAppeal} disabled={!appealText.trim()}>Submit Appeal</button>
                            <button className="btn btn-ghost" onClick={() => { setAppealTarget(null); setAppealText(''); setAppealProof(null) }}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Lightbox ── */}
            <ImageModal src={lightboxSrc} onClose={() => setLightboxSrc(null)} />
        </div>
    )
}
