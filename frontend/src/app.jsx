import React, { lazy, Suspense, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
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

const YearlyPage = lazy(() => import('./pages/YearlyPage'));

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
                    element={user ? <DashboardLayout user={user} onLogout={() => setUser(null)} /> : <Navigate to="/login" replace />}
                >
                    <Route index element={<Navigate to="/beranda" replace />} />
                    <Route path="beranda" element={<HomePage />} />
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