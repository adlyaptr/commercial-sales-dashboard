import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import faviconImage from '../assets/favicon.png';

export default function LoginPage({ onLogin }) {
    const navigate = useNavigate();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [application, setApplication] = useState('commercial');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    async function submit(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        try {
            await api('/api/login', {
                method: 'POST',
                body: { username, password, application },
            });
            const profile = await api('/api/me');
            onLogin(profile);
            navigate(application === 'sph' ? '/sph' : '/beranda', { replace: true });
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setBusy(false);
        }
    }

    return (
        <main className="login-page">
            <section className="login-brand" aria-label="Reethau Cipta Energi">
                <div className="login-brand-logo">
                    <span className="login-brand-mark"><img src={faviconImage} alt="" /></span>
                    <span><strong>Reethau</strong><small>Clean Energy</small></span>
                </div>
                <div className="login-brand-copy">
                    <h2>Commercial<br /><span>Sales Dashboard</span></h2>
                    <span className="login-brand-rule" />
                </div>
                <div className="login-brand-footer">
                    <span className="login-brand-accent" />
                    <span><strong>PT Reethau Cipta Energi</strong><small>Together for a Sustainable Energy Future</small></span>
                </div>
            </section>

            <section className="login-card">
                <header className="login-heading">
                    <div className="login-mark"><img src={faviconImage} alt="" /></div>
                    <div>
                        <p className="eyebrow">CLEAN ENERGY· BUSINESS SYSTEM</p>
                        <h1>Selamat datang</h1>
                    </div>
                </header>
                <form onSubmit={submit}>
                    <fieldset className="login-app-options">
                        <label className={application === 'commercial' ? 'selected' : ''}>
                            <input
                                type="radio"
                                name="application"
                                value="commercial"
                                checked={application === 'commercial'}
                                onChange={() => setApplication('commercial')}
                            />
                            <span className="login-app-icon" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none">
                                    <rect x="3.5" y="4.5" width="17" height="12" rx="2" />
                                    <path d="M8 20h8M12 16.5V20M7 13l3-3 2 2 4-4M14 8h2v2" />
                                </svg>
                            </span>
                            <span className="login-app-option-copy">
                                <strong>Commercial Monitoring</strong>
                                <small>Dashboard penjualan dan operasional</small>
                            </span>
                        </label>
                        <label className={application === 'sph' ? 'selected' : ''}>
                            <input
                                type="radio"
                                name="application"
                                value="sph"
                                checked={application === 'sph'}
                                onChange={() => setApplication('sph')}
                            />
                            <span className="login-app-icon" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none">
                                    <path d="M12.1 2.8c.5 3.2-1.6 4.3-2.7 6.1-.9 1.4-.7 2.7.2 3.7.1-1.5 1-2.4 2-3.1-.1 2.1 2.2 2.8 2.2 5.2 0 1.8-1.2 3-2.9 3-2 0-3.6-1.5-3.6-3.7 0-1.4.6-2.8 1.6-4.1C6.1 11.6 5 14 5 16.1a7 7 0 0 0 14 0c0-4.7-3.4-7.5-6.9-13.3Z" />
                                </svg>
                            </span>
                            <span className="login-app-option-copy">
                                <strong>SPH CNG Reethau</strong>
                                <small>Penawaran harga dan persetujuan · Admin dan Commercial Head</small>
                            </span>
                        </label>
                    </fieldset>
                    <div className="login-field">
                        <label htmlFor="username">Username</label>
                        <div className="login-input-wrap">
                            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                <circle cx="12" cy="8" r="3.5" />
                                <path d="M5 20c.5-3.3 2.9-5 7-5s6.5 1.7 7 5" />
                            </svg>
                            <input id="username" autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Masukkan username" />
                        </div>
                    </div>
                    <div className="login-field">
                        <label htmlFor="password">Password</label>
                        <div className="login-input-wrap">
                            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                <rect x="5" y="10" width="14" height="11" rx="2" />
                                <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
                            </svg>
                            <input id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Masukkan password" />
                            <button
                                className="login-password-toggle"
                                type="button"
                                aria-label={showPassword ? 'Sembunyikan password' : 'Tampilkan password'}
                                onClick={() => setShowPassword((visible) => !visible)}
                            >
                                {showPassword ? (
                                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                        <path d="M3 3l18 18M10.6 10.7a2 2 0 0 0 2.7 2.7" />
                                        <path d="M9.9 5.2A10.7 10.7 0 0 1 12 5c5.1 0 8.5 4.6 9.5 7-.4.9-1.2 2.1-2.4 3.2M6.2 6.3C4.2 7.7 3 9.7 2.5 12c.5 1.2 1.7 3.2 4.1 4.7A9.8 9.8 0 0 0 12 18c1 0 2-.2 2.9-.5" />
                                    </svg>
                                ) : (
                                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                        <path d="M2.5 12s3.4-7 9.5-7 9.5 7 9.5 7-3.4 7-9.5 7-9.5-7-9.5-7Z" />
                                        <circle cx="12" cy="12" r="2.7" />
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>
                    <button className="primary full" type="submit" disabled={busy}>
                        <span className="login-submit-copy">
                            {busy ? 'MEMERIKSA...' : (
                                <>
                                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                        <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4M14 4h6v6M20 4l-9 9" />
                                    </svg>
                                    Masuk
                                </>
                            )}
                        </span>
                        <span className="login-submit-arrow" aria-hidden="true">→</span>
                    </button>
                    {error && <p className="error" role="alert">{error}</p>}
                </form>
            </section>
        </main>
    );
}