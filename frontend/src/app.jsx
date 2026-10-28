import { lazy, Suspense, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import './app.css';
import { api } from './api';
import DashboardLayout from './components/DashboardLayout';
import DailyPage from './pages/DailyPage';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import MonthlyPage from './pages/MonthlyPage';
import ReportsPage from './pages/ReportsPage';
import WeeklyAveragePricePage from './pages/WeeklyAveragePricePage';
import WeeklyComplainPage from './pages/WeeklyComplainPage';
import WeeklyPage from './pages/WeeklyPage';
import WeeklyVolumePage from './pages/WeeklyVolumePage';
import UsersPage from './pages/UsersPage';

const YearlyPage = lazy(() => import('./pages/YearlyPage'));

function DashboardAccess({ user, onLogout }) {
    const location = useLocation();
    if (!user && !['/', '/beranda'].includes(location.pathname)) {
        return <Navigate to="/login" replace />;
    }
    if (user?.role === 'division' && !['/', '/beranda'].includes(location.pathname)) {
        return <Navigate to="/beranda" replace />;
    }
    return (
        <DashboardLayout
            user={user || { role: 'public' }}
            onLogout={onLogout}
        />
    );
}

function App() {
    const [user, setUser] = useState(undefined);

    useEffect(() => {
        let active = true;
        api('/api/me')
            .then((profile) => active && setUser(profile))
            .catch(() => active && setUser(null));

        return () => {
            active = false;
        };
    }, []);

    if (user === undefined) {
        return <div className="app-loading">Memuat dashboard...</div>;
    }

    return (
        <BrowserRouter>
            <Routes>
                <Route
                    path="/login"
                    element={user ? <Navigate to="/beranda" replace /> : <LoginPage onLogin={setUser} />}
                />
                <Route
                    element={(
                        <DashboardAccess
                            user={user}
                            onLogout={() => setUser(null)}
                        />
                    )}
                >
                    <Route index element={<Navigate to="/beranda" replace />} />
                    <Route path="beranda" element={<HomePage />} />
                    {(user?.role === 'admin' || user?.role === 'user') && (
                        <>
                            <Route path="harian" element={<DailyPage />} />
                            <Route path="mingguan" element={<WeeklyPage />} />
                            <Route path="mingguan/volume" element={<WeeklyVolumePage />} />
                            <Route path="mingguan/average-price" element={<WeeklyAveragePricePage />} />
                            <Route path="mingguan/complain" element={<WeeklyComplainPage />} />
                            <Route path="bulanan" element={<MonthlyPage />} />
                            <Route
                                path="tahunan"
                                element={(
                                    <Suspense fallback={<div className="app-loading">Memuat halaman tahunan...</div>}>
                                        <YearlyPage />
                                    </Suspense>
                                )}
                            />
                            <Route path="laporan" element={<ReportsPage />} />
                            {user.role === 'admin' && (
                                <Route path="pengguna" element={<UsersPage />} />
                            )}
                        </>
                    )}
                </Route>
                <Route path="*" element={<Navigate to={user ? '/beranda' : '/login'} replace />} />
            </Routes>
        </BrowserRouter>
    );
}

const root = document.getElementById('app');

if (root) {
    createRoot(root).render(<App />);
}