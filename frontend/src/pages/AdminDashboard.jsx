import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LayoutDashboard, Upload, FileCheck2, Bell, MessageSquare, Users, BarChart3, LogOut, Check, X, ZoomIn } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'

const TABS = [
    ['overview', 'Overview', LayoutDashboard],
    ['upload', 'Upload', Upload],
    ['review', 'Review', FileCheck2],
    ['alerts', 'Alerts', Bell],
    ['appeals', 'Appeals', MessageSquare],
    ['students', 'Students', Users],
    ['analytics', 'Analytics', BarChart3],
]

const formatDate = (v) => new Date(v).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

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

/* ── Clickable Thumb ─────────────────────────────────────────────────────── */
function EvidenceThumb({ path, onOpen }) {
    if (!path) return null
    // Clean up slashes just in case
    const cleanPath = path.replace(/\\/g, '/').replace(/^\/+/, '')
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const url = cleanPath.startsWith('http') ? cleanPath : `${API_BASE_URL}/${cleanPath}`
    return (
        <div style={{ position: 'relative', display: 'inline-block', cursor: 'pointer' }} onClick={() => onOpen(url)}>
            <img className="evidence-thumb" src={url} alt="proof"
                style={{ width: 72, height: 72, objectFit: 'cover', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)' }} />
            <div style={{
                position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.35)',
                borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
                opacity: 0, transition: 'opacity 0.2s',
            }}
                onMouseEnter={e => e.currentTarget.style.opacity = 1}
                onMouseLeave={e => e.currentTarget.style.opacity = 0}
            >
                <ZoomIn size={22} color="#fff" />
            </div>
        </div>
    )
}

export default function AdminDashboard() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()
    const [tab, setTab] = useState('overview')
    const [error, setError] = useState('')
    const [info, setInfo] = useState('')
    const [videoFile, setVideoFile] = useState(null)
    const [lightboxSrc, setLightboxSrc] = useState(null)

    const [analytics, setAnalytics] = useState({ total_students: 0, total_sessions: 0, compliance_rate: 0, violations_by_type: {} })
    const [sessions, setSessions] = useState([])
    const [selectedSession, setSelectedSession] = useState(null)
    const [results, setResults] = useState({ compliant: [], non_compliant: [], pending_review: 0 })
    const [alerts, setAlerts] = useState([])
    const [appeals, setAppeals] = useState([])
    const [students, setStudents] = useState([])
    const [policies, setPolicies] = useState([])
    const [studentForm, setStudentForm] = useState({ name: '', email: '', password: 'student123', roll_no: '', department: '', year: '', gender: '' })
    const [photoFiles, setPhotoFiles] = useState({})
    const [facePhotoForNew, setFacePhotoForNew] = useState(null)
    const faceInputRef = useRef(null)

    const loadAll = async () => {
        try {
            const [a, s, al, ap, st, sp] = await Promise.all([
                client.get('/admin/analytics/compliance'),
                client.get('/admin/video-sessions'),
                client.get('/admin/alerts'),
                client.get('/admin/appeals-v2?status=pending'),
                client.get('/admin/students/detail'),
                client.get('/admin/score-policies'),
            ])
            setAnalytics(a.data); setSessions(s.data); setAlerts(al.data); setAppeals(ap.data); setStudents(st.data); setPolicies(sp.data)
            if (!selectedSession && s.data.length) setSelectedSession(s.data[0].id)
        } catch (e) { setError(e.response?.data?.detail || 'Failed to load admin data') }
    }

    const loadResults = async (sessionId) => {
        if (!sessionId) return
        try { setResults((await client.get(`/admin/video-sessions/${sessionId}/results`)).data) }
        catch (e) { setError(e.response?.data?.detail || 'Failed to load session results') }
    }

    useEffect(() => { loadAll() }, [])
    useEffect(() => { loadResults(selectedSession) }, [selectedSession])

    const pendingAlertDetections = useMemo(() => {
        const alerted = new Set(alerts.map((a) => a.detection_id))
        return results.non_compliant.filter((d) => d.review_status === 'confirmed' && !alerted.has(d.id))
    }, [alerts, results.non_compliant])

    const uploadVideo = async () => {
        if (!videoFile) return
        setInfo('Uploading and queuing for processing…')
        const fd = new FormData(); fd.append('file', videoFile)
        try {
            await client.post('/admin/video-sessions/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
            setInfo('Video uploaded and queued for processing. Check back in the Review tab.'); setVideoFile(null); loadAll()
        } catch (e) { setError(e.response?.data?.detail || 'Video upload failed') }
    }

    const reviewDetection = async (id, action) => {
        try { await client.post(`/admin/detections/${id}/review`, { action }); loadResults(selectedSession) }
        catch (e) { setError(e.response?.data?.detail || 'Review action failed') }
    }

    const sendAlerts = async () => {
        try {
            await client.post('/admin/alerts/send', { detection_ids: pendingAlertDetections.map((d) => d.id) })
            setInfo('Alerts sent and scores updated'); loadAll(); loadResults(selectedSession)
        } catch (e) { setError(e.response?.data?.detail || 'Sending alerts failed') }
    }

    const decideAppeal = async (id, status) => {
        try { await client.post(`/admin/appeals-v2/${id}/decide`, { status }); loadAll() }
        catch (e) { setError(e.response?.data?.detail || 'Failed to decide appeal') }
    }

    const registerStudent = async () => {
        if (!studentForm.name || !studentForm.email) { setError('Name and email are required'); return }
        try {
            const res = await client.post('/admin/students/register', studentForm)
            const newId = res.data.id
            setInfo(`Student "${studentForm.name}" registered (ID #${newId})`)
            setStudentForm({ name: '', email: '', password: 'student123', roll_no: '', department: '', year: '', gender: '' })

            // Upload face photo if selected
            if (facePhotoForNew) {
                const fd = new FormData()
                fd.append('files', facePhotoForNew)
                try {
                    await client.post(`/admin/students/${newId}/face-photos`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
                    setInfo(`Student "${studentForm.name}" registered with face photo ✓`)
                } catch (fe) {
                    setError(`Student registered but face photo failed: ${fe.response?.data?.detail || 'unknown error'}`)
                }
                setFacePhotoForNew(null)
                if (faceInputRef.current) faceInputRef.current.value = ''
            }
            loadAll()
        } catch (e) { setError(e.response?.data?.detail || 'Registration failed') }
    }

    const uploadFacePhotos = async (studentId) => {
        const files = photoFiles[studentId]
        if (!files || !files.length) return
        const fd = new FormData(); Array.from(files).forEach((f) => fd.append('files', f))
        try {
            await client.post(`/admin/students/${studentId}/face-photos`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
            setInfo(`Face photos uploaded for student #${studentId}`)
            setPhotoFiles(p => ({ ...p, [studentId]: null }))
            loadAll()
        } catch (e) { setError(e.response?.data?.detail || 'Face upload failed') }
    }

    const savePolicy = async (p) => {
        try { await client.put('/admin/score-policies', p); setInfo(`Updated ${p.violation_type}`) }
        catch (e) { setError(e.response?.data?.detail || 'Policy save failed') }
    }

    const signOut = () => { logout(); navigate('/login') }

    // Helper: find student name by id
    const studentName = (id) => {
        if (!id) return 'Unknown Person'
        const s = students.find(st => st.id === id)
        return s ? s.name : `Student #${id}`
    }

    return (
        <div className="layout">
            <aside className="sidebar">
                <div className="sidebar-brand">Dress<span>Code</span><div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Admin Compliance</div></div>
                {TABS.map(([id, label, Icon]) => <div key={id} className={`nav-item ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}><Icon size={16} />{label}</div>)}
                <div className="sidebar-spacer" />
                <div style={{ padding: 16 }}>
                    <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Logged in as</div>
                    <div style={{ marginBottom: 10 }}>{user?.name}</div>
                    <button className="btn btn-ghost" style={{ width: '100%', justifyContent: 'center' }} onClick={signOut}><LogOut size={14} /> Sign Out</button>
                </div>
            </aside>

            <div className="main-content">
                <div className="topbar"><h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700 }}>{tab}</h2><button className="btn btn-ghost" onClick={loadAll}>Refresh</button></div>
                <div className="page-content" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {info && <div className="card-sm" style={{ color: 'var(--color-success)' }}>{info}</div>}
                    {error && <div className="card-sm" style={{ color: 'var(--color-danger)', cursor: 'pointer' }} onClick={() => setError('')}>{error} ✕</div>}

                    {/* ── Overview ── */}
                    {tab === 'overview' && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12 }}>
                        <div className="stat-card"><span className="stat-label">Students</span><span className="stat-value">{analytics.total_students}</span></div>
                        <div className="stat-card"><span className="stat-label">Sessions</span><span className="stat-value">{analytics.total_sessions}</span></div>
                        <div className="stat-card"><span className="stat-label">Compliance Rate</span><span className="stat-value">{analytics.compliance_rate}%</span></div>
                    </div>}

                    {/* ── Upload ── */}
                    {tab === 'upload' && <div className="card">
                        <h3 style={{ marginBottom: 10 }}>Upload Surveillance Video</h3>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: 13, marginBottom: 10 }}>
                            Upload a video to detect registered students and check dress-code compliance.
                            Make sure students have face photos uploaded first (Students tab).
                        </p>
                        <input className="input" type="file" accept=".mp4,.avi,.mov,.mkv,.webm" onChange={(e) => setVideoFile(e.target.files?.[0] || null)} />
                        {videoFile && <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginTop: 6 }}>Selected: {videoFile.name} ({(videoFile.size / 1024 / 1024).toFixed(1)} MB)</div>}
                        <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={uploadVideo} disabled={!videoFile}>Upload & Process</button>
                    </div>}

                    {/* ── Review ── */}
                    {tab === 'review' && <div className="card">
                        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 }}>
                            <select className="input" style={{ maxWidth: 340 }} value={selectedSession || ''} onChange={(e) => setSelectedSession(Number(e.target.value))}>
                                {sessions.map((s) => <option key={s.id} value={s.id}>#{s.id} {s.original_filename} ({s.status})</option>)}
                            </select>
                            <span className="badge badge-warning">{results.pending_review || 0} pending</span>
                        </div>
                        <h4 style={{ marginBottom: 8 }}>Non-compliant Detections</h4>
                        {results.non_compliant.length === 0 && <p style={{ color: 'var(--color-text-muted)' }}>No non-compliant detections for this session.</p>}
                        {results.non_compliant.map((d) => (
                            <div key={d.id} className="card-sm" style={{ marginBottom: 8, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                                <div>
                                    <div style={{ fontWeight: 600 }}>{studentName(d.student_id)}</div>
                                    <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>{d.violations.join(', ')}</div>
                                </div>
                                <span className="badge badge-warning">{d.review_status}</span>
                                {d.frame_path && <EvidenceThumb path={d.frame_path} onOpen={setLightboxSrc} />}
                                {d.review_status === 'pending' && <>
                                    <button className="btn btn-primary" style={{ padding: '6px 10px' }} onClick={() => reviewDetection(d.id, 'confirm')}><Check size={13} /> Confirm</button>
                                    <button className="btn btn-ghost" style={{ padding: '6px 10px' }} onClick={() => reviewDetection(d.id, 'dismiss')}><X size={13} /> Dismiss</button>
                                </>}
                            </div>
                        ))}
                    </div>}

                    {/* ── Alerts ── */}
                    {tab === 'alerts' && <div className="card">
                        <div style={{ marginBottom: 10 }}>
                            <button className="btn btn-primary" onClick={sendAlerts} disabled={!pendingAlertDetections.length}>
                                Send Alerts ({pendingAlertDetections.length})
                            </button>
                            <span style={{ marginLeft: 10, fontSize: 13, color: 'var(--color-text-muted)' }}>
                                {pendingAlertDetections.length > 0 ? 'Confirmed detections ready to alert students' : 'No pending detections to alert'}
                            </span>
                        </div>
                        <div className="table-wrapper">
                            <table><thead><tr><th>ID</th><th>Student</th><th>Violations</th><th>Deduction</th><th>Status</th><th>Time</th><th>Proof</th></tr></thead><tbody>
                                {alerts.map((a) => <tr key={a.id}>
                                    <td>#{a.id}</td>
                                    <td>{studentName(a.student_id)}</td>
                                    <td style={{ color: 'var(--color-danger)', maxWidth: 200 }}>{a.violations?.join(', ') || '—'}</td>
                                    <td>-{a.score_deducted}</td>
                                    <td>{a.status}</td>
                                    <td>{formatDate(a.sent_at)}</td>
                                    <td>{a.frame_path && <EvidenceThumb path={a.frame_path} onOpen={setLightboxSrc} />}</td>
                                </tr>)}
                                {alerts.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--color-text-muted)' }}>No alerts sent yet</td></tr>}
                            </tbody></table>
                        </div>
                    </div>}

                    {/* ── Appeals ── */}
                    {tab === 'appeals' && <div className="card">
                        {appeals.length === 0 && <p style={{ color: 'var(--color-text-muted)' }}>No pending appeals.</p>}
                        {appeals.map((a) => <div key={a.id} className="card-sm" style={{ marginBottom: 8 }}>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}><strong>Appeal #{a.id}</strong><span className="badge badge-warning">{a.status}</span></div>
                            <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Student: {studentName(a.student_id)} | Alert #{a.alert_id}</div>
                            <div style={{ marginTop: 6 }}>{a.justification}</div>
                            {a.proof_path && <EvidenceThumb path={a.proof_path} onOpen={setLightboxSrc} />}
                            {a.status === 'pending' && <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                                <button className="btn btn-primary" style={{ padding: '6px 10px' }} onClick={() => decideAppeal(a.id, 'approved')}><Check size={13} /> Approve</button>
                                <button className="btn btn-ghost" style={{ padding: '6px 10px' }} onClick={() => decideAppeal(a.id, 'rejected')}><X size={13} /> Reject</button>
                            </div>}
                        </div>)}
                    </div>}

                    {/* ── Students ── */}
                    {tab === 'students' && <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        <div className="card">
                            <h3 style={{ marginBottom: 8 }}>Register New Student</h3>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 8 }}>
                                <input className="input" placeholder="Full Name *" value={studentForm.name} onChange={(e) => setStudentForm((p) => ({ ...p, name: e.target.value }))} />
                                <input className="input" placeholder="Email *" value={studentForm.email} onChange={(e) => setStudentForm((p) => ({ ...p, email: e.target.value }))} />
                                <input className="input" placeholder="Password (default: student123)" value={studentForm.password} onChange={(e) => setStudentForm((p) => ({ ...p, password: e.target.value }))} />
                                <input className="input" placeholder="Roll No" value={studentForm.roll_no} onChange={(e) => setStudentForm((p) => ({ ...p, roll_no: e.target.value }))} />
                                <input className="input" placeholder="Department" value={studentForm.department} onChange={(e) => setStudentForm((p) => ({ ...p, department: e.target.value }))} />
                                <input className="input" placeholder="Year (e.g. 2)" value={studentForm.year} onChange={(e) => setStudentForm((p) => ({ ...p, year: e.target.value }))} />
                                <select className="input" value={studentForm.gender} onChange={(e) => setStudentForm((p) => ({ ...p, gender: e.target.value }))}>
                                    <option value="">Gender</option><option value="Male">Male</option><option value="Female">Female</option>
                                </select>
                            </div>
                            <div style={{ marginTop: 10 }}>
                                <label style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 4, display: 'block' }}>
                                    📷 Face Photo (Clear frontal face — used for video detection)
                                </label>
                                <input ref={faceInputRef} className="input" type="file" accept=".jpg,.jpeg,.png,.webp"
                                    onChange={(e) => setFacePhotoForNew(e.target.files?.[0] || null)} />
                                {facePhotoForNew && <div style={{ fontSize: 12, color: 'var(--color-success)', marginTop: 4 }}>✓ {facePhotoForNew.name} selected</div>}
                            </div>
                            <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={registerStudent}>Register Student</button>
                        </div>

                        <div className="card table-wrapper">
                            <h3 style={{ marginBottom: 8 }}>Registered Students</h3>
                            <table><thead><tr><th>ID</th><th>Name</th><th>Roll</th><th>Score</th><th>Face Photos</th><th>Add More Photos</th></tr></thead><tbody>
                                {students.map((s) => <tr key={s.id}>
                                    <td>#{s.id}</td><td>{s.name}</td><td>{s.roll_no || '-'}</td><td>{s.score}</td>
                                    <td>
                                        <span className={`badge ${s.face_photos > 0 ? 'badge-success' : 'badge-danger'}`}>
                                            {s.face_photos > 0 ? `${s.face_photos} photo${s.face_photos > 1 ? 's' : ''} ✓` : '⚠ No photo'}
                                        </span>
                                    </td>
                                    <td>
                                        <input type="file" multiple accept=".jpg,.jpeg,.png,.webp"
                                            onChange={(e) => setPhotoFiles((p) => ({ ...p, [s.id]: e.target.files }))} />
                                        <button className="btn btn-ghost" style={{ padding: '5px 8px', marginTop: 4 }}
                                            onClick={() => uploadFacePhotos(s.id)}>Upload</button>
                                    </td>
                                </tr>)}
                            </tbody></table>
                        </div>
                    </div>}

                    {/* ── Analytics ── */}
                    {tab === 'analytics' && <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div className="card">{Object.entries(analytics.violations_by_type || {}).map(([k, v]) => <div key={k} className="card-sm" style={{ marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}><span>{k}</span><span className="badge badge-danger">{v}</span></div>)}</div>
                        <div className="card">{policies.map((p) => <div key={p.id} className="card-sm" style={{ marginBottom: 6, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <span style={{ minWidth: 180 }}>{p.violation_type}</span>
                            <input className="input" style={{ maxWidth: 100 }} type="number" value={p.deduction_points} onChange={(e) => setPolicies((prev) => prev.map((x) => x.id === p.id ? { ...x, deduction_points: Number(e.target.value) } : x))} />
                            <label><input type="checkbox" checked={p.active} onChange={(e) => setPolicies((prev) => prev.map((x) => x.id === p.id ? { ...x, active: e.target.checked } : x))} /> Active</label>
                            <button className="btn btn-ghost" style={{ padding: '5px 8px' }} onClick={() => savePolicy(p)}>Save</button>
                        </div>)}</div>
                    </div>}
                </div>
            </div>

            {/* Lightbox */}
            <ImageModal src={lightboxSrc} onClose={() => setLightboxSrc(null)} />
        </div>
    )
}
