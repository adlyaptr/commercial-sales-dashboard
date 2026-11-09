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
            <section className="login-card">
                <div className="login-mark"><img src={faviconImage} alt="Logo" /></div>
                <p className="eyebrow">REFINED ENERGY · BUSINESS SYSTEMS</p>
                <h1>Selamat datang</h1>
                <p className="muted">Pilih aplikasi, lalu masuk dengan akun Anda.</p>
                <form onSubmit={submit}>
                    <fieldset className="login-app-options">
                        <legend>Pilih aplikasi</legend>
                        <label className={application === 'commercial' ? 'selected' : ''}>
                            <input
                                type="radio"
                                name="application"
                                value="commercial"
                                checked={application === 'commercial'}
                                onChange={() => setApplication('commercial')}
                            />
                            <span>
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
                            <span>
                                <strong>SPH CNG Reethau</strong>
                                <small>Penawaran harga dan alur persetujuan</small>
                            </span>
                        </label>
                    </fieldset>
                    <label htmlFor="username">Username</label>
                    <input id="username" autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Masukkan username" />
                    <label htmlFor="password">Password</label>
                    <input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Masukkan password" />
                    <button className="primary full" type="submit" disabled={busy}>{busy ? 'MEMERIKSA...' : <>MASUK <span>→</span></>}</button>
                    {error && <p className="error" role="alert">{error}</p>}
                </form>
            </section>
        </main>
    );
}