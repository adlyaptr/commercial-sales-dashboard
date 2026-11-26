
import { useCallback, useEffect, useState } from 'react';
import {
    NavLink,
    Outlet,
    useLocation,
    useNavigate,
} from 'react-router-dom';
import { api } from '../api';
import logoImage from '../assets/reethau.png';

const classForNav = ({ isActive }) =>
    `nav-link${isActive ? ' active' : ''}`;

const classForCompactNav = ({ isActive }) =>
    `nav-link nav-link-compact${isActive ? ' active' : ''}`;

const AUTO_REFRESH_INTERVAL_MS = 310_000;

function NavigationIcon({ name }) {
    const commonProps = {
        'aria-hidden': true,
        fill: 'none',
        stroke: 'currentColor',
        strokeLinecap: 'round',
        strokeLinejoin: 'round',
        strokeWidth: 1.8,
        viewBox: '0 0 24 24',
    };

    const paths = {
        home: (
            <>
                <path d="m3 10 9-7 9 7" />
                <path d="M5 9v11h14V9M9 20v-6h6v6" />
            </>
        ),
        daily: (
            <>
                <rect x="4" y="5" width="16" height="16" rx="2" />
                <path d="M8 3v4m8-4v4M4 10h16m-11 4h2m3 0h2m-7 3h2" />
            </>
        ),
        issue: (
            <>
                <rect x="4" y="3.5" width="16" height="17" rx="2" />
                <path d="M8 8h8M8 12h8m-8 4h5" />
            </>
        ),
        budget: (
            <>
                <rect x="3.5" y="5" width="17" height="15" rx="2" />
                <path d="M7 9h10M7 13h3m3 0h4M7 16h2m4 0h4M8 3v4m8-4v4" />
            </>
        ),
        weekly: (
            <>
                <rect x="3.5" y="5" width="17" height="16" rx="2" />
                <path d="M8 3v4m8-4v4M3.5 10h17" />
                <rect x="7" y="13" width="3" height="3" rx=".5" />
                <rect x="14" y="13" width="3" height="3" rx=".5" />
            </>
        ),
        volume: (
            <>
                <path d="M4 20h16" />
                <rect x="5" y="12" width="3" height="8" rx=".5" />
                <rect x="10.5" y="8" width="3" height="12" rx=".5" />
                <rect x="16" y="4" width="3" height="16" rx=".5" />
            </>
        ),
        averagePrice: (
            <>
                <circle cx="12" cy="12" r="9" />
                <path d="M15.5 8.5c-.7-.7-1.6-1-2.8-1-1.5 0-2.5.8-2.5 1.8 0 2.8 5.2 1.2 5.2 4.2 0 1.2-1.1 2.1-2.8 2.1-1.2 0-2.2-.4-3-1.1M12 5.5v13" />
            </>
        ),
        complain: (
            <>
                <path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H7l-3 2v-5.3A7.5 7.5 0 1 1 20 11.5Z" />
                <path d="M12.5 8v4m0 3h.01" />
            </>
        ),
        monthly: (
            <>
                <rect x="3.5" y="5" width="17" height="16" rx="2" />
                <path d="M8 3v4m8-4v4M3.5 10h17M8 13.5h.01M12 13.5h.01M16 13.5h.01M8 17h.01M12 17h.01M16 17h.01" />
            </>
        ),
        yearly: (
            <>
                <path d="M4 19.5h16M5 17V5m0 12 5-5 3 2 6-7" />
                <path d="M15 7h4v4" />
            </>
        ),
        cooperation: (
            <>
                <rect x="3.5" y="5" width="17" height="15" rx="2" />
                <path d="M8 5V3m8 2V3M3.5 10h17M8 14l2.2 2.2L16 11" />
            </>
        ),
        cooperationList: (
            <>
                <rect x="4" y="3.5" width="16" height="17" rx="2" />
                <path d="M8 8h8M8 12h8m-8 4h5" />
            </>
        ),
        validity: (
            <>
                <rect x="3.5" y="5" width="17" height="16" rx="2" />
                <path d="M8 3v4m8-4v4M3.5 10h17" />
                <circle cx="14.5" cy="15.5" r="3.2" />
                <path d="M14.5 13.9v1.8l1.2.7" />
            </>
        ),
    };

    return <svg className="nav-ico" {...commonProps}>{paths[name]}</svg>;
}

const formatReportDate = (date) => {
    if (!date) return 'Belum ada data';

    const parsed = new Date(`${date}T00:00:00`);

    if (Number.isNaN(parsed.getTime())) return date;

    return parsed.toLocaleDateString('id-ID', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
    });
};

const formatPeriodDate = (date) =>
    date ? date.split('-').reverse().join('/') : 'Pilih tanggal';

function readSidebarPreference() {
    try {
        return localStorage.getItem('sidebar-hidden') === 'true';
    } catch {
        return false;
    }
}

function saveSidebarPreference(hidden) {
    try {
        localStorage.setItem('sidebar-hidden', String(hidden));
    } catch {
        // Preferensi tidak tersimpan; aplikasi tetap dapat digunakan.
    }
}

export default function DashboardLayout({ user, onLogout }) {
    const location = useLocation();
    const navigate = useNavigate();

    const isDaily = location.pathname === '/harian';
    const isWeeklyVolume = location.pathname === '/mingguan/volume';
    const isAveragePrice = location.pathname === '/mingguan/average-price';
    const isYearly = location.pathname === '/tahunan';
    const isMonthly = location.pathname === '/bulanan';
    const isBudget = location.pathname === '/budget';
    const isHome = location.pathname === '/beranda';
    const isUsers = location.pathname === '/pengguna';
    const isCooperation = location.pathname.startsWith('/kerja-sama');
    const canViewAllFeatures = user?.role === 'admin' || user?.role === 'user';
    const hasAuthenticatedUser = canViewAllFeatures;
    const [isCompactViewport, setIsCompactViewport] = useState(
        () => window.matchMedia('(max-width: 1024px)').matches,
    );
    const [sidebarHidden, setSidebarHidden] =
        useState(readSidebarPreference);
    const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

    const [dates, setDates] = useState([]);
    const [latestActualDate, setLatestActualDate] = useState('');
    const [selectedDate, setSelectedDate] = useState('');
    const [rangeStartDate, setRangeStartDate] = useState('');
    const [rangeEndDate, setRangeEndDate] = useState('');
    const [averagePriceMonth, setAveragePriceMonth] = useState('');
    const [rangePickerOpen, setRangePickerOpen] = useState(false);
    const [dashboard, setDashboard] = useState(null);
    const [forecastRefreshKey, setForecastRefreshKey] = useState(0);
    const [homeRefreshKey, setHomeRefreshKey] = useState(0);
    const [dataError, setDataError] = useState('');
    const [loadingDates, setLoadingDates] = useState(true);
    const [loggingOut, setLoggingOut] = useState(false);

    useEffect(() => {
        const mediaQuery = window.matchMedia('(max-width: 1024px)');
        const updateViewport = (event) => {
            setIsCompactViewport(event.matches);
            if (!event.matches) setMobileSidebarOpen(false);
        };
        setIsCompactViewport(mediaQuery.matches);
        mediaQuery.addEventListener('change', updateViewport);
        return () => mediaQuery.removeEventListener('change', updateViewport);
    }, []);

    useEffect(() => {
        if (!isCompactViewport || !mobileSidebarOpen) return undefined;
        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => {
            document.body.style.overflow = previousOverflow;
        };
    }, [isCompactViewport, mobileSidebarOpen]);

    useEffect(() => {
        if (!mobileSidebarOpen) return undefined;
        const closeOnEscape = (event) => {
            if (event.key === 'Escape') setMobileSidebarOpen(false);
        };
        window.addEventListener('keydown', closeOnEscape);
        return () => window.removeEventListener('keydown', closeOnEscape);
    }, [mobileSidebarOpen]);

    // Memuat tanggal yang tersedia dari backend.
    const loadDates = useCallback(async () => {
        setLoadingDates(true);

        try {
            const [result, latestActual] = await Promise.all([
                api('/api/dates'),
                api('/api/latest-actual-date'),
            ]);

            if (!Array.isArray(result)) {
                throw new Error(
                    'Format daftar tanggal dari server tidak valid.'
                );
            }
            if (latestActual !== null && typeof latestActual !== 'string') {
                throw new Error(
                    'Format tanggal actual terakhir dari server tidak valid.'
                );
            }

            const normalizedDates = [
                ...new Set(
                    result
                        .filter((date) => typeof date === 'string')
                        .map((date) => date.trim())
                        .filter(Boolean)
                ),
            ].sort((a, b) => b.localeCompare(a));

            setDates(normalizedDates);
            setLatestActualDate(latestActual ?? '');

            const defaultDate = normalizedDates.includes(latestActual)
                ? latestActual
                : normalizedDates[0] ?? '';
            setSelectedDate((current) => current && normalizedDates.includes(current) ? current : defaultDate);
            setRangeStartDate((current) => current && normalizedDates.includes(current) ? current : defaultDate);
            setRangeEndDate((current) => current && normalizedDates.includes(current) ? current : defaultDate);
            setAveragePriceMonth((current) => current || defaultDate.slice(0, 7));
            setDataError('');
            return {
                dates: normalizedDates,
                latestActualDate: latestActual ?? '',
            };
        } catch (error) {
            setDataError(
                error?.message || 'Gagal mengambil daftar tanggal.'
            );
            throw error;
        } finally {
            setLoadingDates(false);
        }
    }, []);

    useEffect(() => {
        let active = true;

        async function initializeDates() {
            setLoadingDates(true);

            try {
                const [result, latestActual] = await Promise.all([
                    api('/api/dates'),
                    api('/api/latest-actual-date'),
                ]);

                if (!active) return;

                if (!Array.isArray(result)) {
                    throw new Error(
                        'Format daftar tanggal dari server tidak valid.'
                    );
                }
                if (latestActual !== null && typeof latestActual !== 'string') {
                    throw new Error(
                        'Format tanggal actual terakhir dari server tidak valid.'
                    );
                }

                const normalizedDates = [
                    ...new Set(
                        result
                            .filter((date) => typeof date === 'string')
                            .map((date) => date.trim())
                            .filter(Boolean)
                    ),
                ].sort((a, b) => b.localeCompare(a));

                setDates(normalizedDates);
                setLatestActualDate(latestActual ?? '');

                const defaultDate = normalizedDates.includes(latestActual)
                    ? latestActual
                    : normalizedDates[0] ?? '';
                setSelectedDate((current) => current && normalizedDates.includes(current) ? current : defaultDate);
                setRangeStartDate((current) => current && normalizedDates.includes(current) ? current : defaultDate);
                setRangeEndDate((current) => current && normalizedDates.includes(current) ? current : defaultDate);
                setAveragePriceMonth((current) => current || defaultDate.slice(0, 7));
                setDataError('');
            } catch (error) {
                if (active) {
                    setDataError(
                        error?.message ||
                        'Gagal mengambil daftar tanggal.'
                    );
                }
            } finally {
                if (active) setLoadingDates(false);
            }
        }

        initializeDates();

        return () => {
            active = false;
        };
    }, []);

    // Mengambil data dashboard sesuai tanggal yang dipilih.
    useEffect(() => {
        let active = true;

        async function loadDashboard() {
            if (!canViewAllFeatures) {
                setDashboard(null);
                return;
            }
            if (!selectedDate) {
                setDashboard(null);
                return;
            }

            try {
                const query =
                    `?report_date=${encodeURIComponent(selectedDate)}`;

                const result = await api(`/api/dashboard${query}`);

                if (!active) return;

                setDashboard(result);
                setDataError('');
            } catch (error) {
                if (!active) return;

                setDataError(
                    error?.message ||
                    'Gagal mengambil data dashboard.'
                );
            }
        }

        loadDashboard();

        return () => {
            active = false;
        };
    }, [selectedDate, canViewAllFeatures]);

    useEffect(() => {
        if (!isHome) return undefined;

        let active = true;
        let refreshInFlight = false;
        const refreshHome = async () => {
            if (!active || refreshInFlight || document.visibilityState === 'hidden') return;
            refreshInFlight = true;
            try {
                const [result, latestActual] = await Promise.all([
                    api('/api/dates'),
                    api('/api/latest-actual-date'),
                ]);
                if (!active) return;
                if (!Array.isArray(result)) {
                    throw new Error('Format daftar tanggal dari server tidak valid.');
                }
                if (latestActual !== null && typeof latestActual !== 'string') {
                    throw new Error('Format tanggal actual terakhir dari server tidak valid.');
                }

                const normalizedDates = [
                    ...new Set(
                        result
                            .filter((reportDate) => typeof reportDate === 'string')
                            .map((reportDate) => reportDate.trim())
                            .filter(Boolean)
                    ),
                ].sort((a, b) => b.localeCompare(a));
                const followsLatestDate = Boolean(
                    latestActualDate
                    && selectedDate === latestActualDate
                    && rangeStartDate === latestActualDate
                    && rangeEndDate === latestActualDate
                );

                setDates(normalizedDates);
                setLatestActualDate(latestActual ?? '');
                if (followsLatestDate && latestActual && latestActual !== latestActualDate) {
                    setSelectedDate(latestActual);
                    setRangeStartDate(latestActual);
                    setRangeEndDate(latestActual);
                    setAveragePriceMonth(latestActual.slice(0, 7));
                }
                setHomeRefreshKey((key) => key + 1);
                setDataError('');
            } catch (error) {
                if (active) {
                    setDataError(error?.message || 'Gagal memperbarui data Beranda.');
                }
            } finally {
                refreshInFlight = false;
            }
        };
        const handleVisibilityChange = () => {
            if (document.visibilityState !== 'hidden') refreshHome();
        };
        const timer = window.setInterval(refreshHome, AUTO_REFRESH_INTERVAL_MS);
        document.addEventListener('visibilitychange', handleVisibilityChange);

        return () => {
            active = false;
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            window.clearInterval(timer);
        };
    }, [isHome, latestActualDate, rangeEndDate, rangeStartDate, selectedDate]);

    useEffect(() => {
        if (!isDaily || !canViewAllFeatures || !selectedDate) return undefined;

        let active = true;
        const timer = window.setInterval(async () => {
            if (document.visibilityState === 'hidden') return;
            try {
                const refreshed = await api(
                    `/api/dashboard?report_date=${encodeURIComponent(selectedDate)}`
                );
                if (!active) return;
                setDashboard(refreshed);
                setForecastRefreshKey((key) => key + 1);
                setDataError('');
            } catch (error) {
                if (active) {
                    setDataError(
                        error?.message || 'Gagal memperbarui prognosa dari Google Sheets.'
                    );
                }
            }
        }, AUTO_REFRESH_INTERVAL_MS);

        return () => {
            active = false;
            window.clearInterval(timer);
        };
    }, [isDaily, selectedDate, canViewAllFeatures]);

    // Dipanggil oleh halaman import setelah proses import berhasil.
    // Memuat ulang daftar tanggal dan mempertahankan tanggal lama
    // jika tanggal tersebut masih ada.
    const refreshDashboard = useCallback(async (preferredDate) => {
        const previousDate = selectedDate;

        try {
            const {
                dates: availableDates,
                latestActualDate: latestActual,
            } = await loadDates();

            if (preferredDate && !availableDates.includes(preferredDate)) {
                throw new Error(`Tanggal ${preferredDate} belum muncul pada daftar data setelah penyimpanan.`);
            }

            const nextDate =
                preferredDate && availableDates.includes(preferredDate)
                    ? preferredDate
                    : previousDate && availableDates.includes(previousDate)
                        ? previousDate
                        : availableDates.includes(latestActual)
                            ? latestActual
                            : availableDates[0] ?? '';

            setSelectedDate(nextDate);
            setRangeStartDate(nextDate);
            setRangeEndDate(nextDate);
            setAveragePriceMonth(nextDate.slice(0, 7));
            if (nextDate && nextDate === previousDate) {
                const refreshed = await api(
                    `/api/dashboard?report_date=${encodeURIComponent(nextDate)}`
                );
                setDashboard(refreshed);
            }
            setDataError('');
            return nextDate;
        } catch (error) {
            setDataError(error?.message || 'Gagal memperbarui data dashboard.');
            throw error;
        }
    }, [latestActualDate, loadDates, selectedDate]);

    const refreshForecast = useCallback(async () => {
        try {
            if (selectedDate) {
                const refreshed = await api(
                    `/api/dashboard?report_date=${encodeURIComponent(selectedDate)}`
                );
                setDashboard(refreshed);
            }
            setForecastRefreshKey((key) => key + 1);
            setDataError('');
        } catch (error) {
            setDataError(error?.message || 'Gagal memperbarui data prognosis.');
            throw error;
        }
    }, [selectedDate]);

    async function logout() {
        if (loggingOut) return;

        setLoggingOut(true);

        try {
            await api('/api/logout', { method: 'POST' });
        } catch (error) {
            // Tetap arahkan pengguna ke halaman login.
            // Jika API logout gagal, server perlu memeriksa sesi
            // yang mungkin masih aktif.
            console.error('Logout API gagal:', error);
        } finally {
            onLogout?.();
            navigate('/login', { replace: true });
            setLoggingOut(false);
        }
    }

    function toggleSidebar() {
        setSidebarHidden((current) => {
            const next = !current;
            saveSidebarPreference(next);
            return next;
        });
    }

    const outletContext = {
        dashboard,
        canEdit: user?.role === 'admin',
        canSyncDailySales: user?.role === 'admin' || user?.role === 'user',
        canViewHomeAverage: isHome,
        forecastRefreshKey,
        homeRefreshKey,
        selectedDate,
        rangeStartDate,
        rangeEndDate,
        averagePriceMonth,
        setAveragePriceMonth,
        dates,
        refreshDashboard,
        refreshForecast,
        dataError,
        loadingDates,
        setSelectedDate,
        setRangeStartDate,
        setRangeEndDate,
    };

    const availablePeriodMonths = [...new Set(dates.map((date) => date.slice(0, 7)))];

    function selectBudgetPeriodMonth(month) {
        const monthDate = dates.find((date) => date.startsWith(`${month}-`));
        if (!monthDate) return;
        setSelectedDate(monthDate);
        setRangeStartDate(monthDate);
        setRangeEndDate(monthDate);
    }

    function updateDailyRangeStart(value) {
        setRangeStartDate(value);
        if (!rangeEndDate || value > rangeEndDate) {
            setRangeEndDate(value);
            setSelectedDate(value);
        }
    }

    function updateDailyRangeEnd(value) {
        setRangeEndDate(value);
        setSelectedDate(value);
        if (!rangeStartDate || value < rangeStartDate) setRangeStartDate(value);
    }

    function updateRangeStart(value) {
        setRangeStartDate(value);
        if (!rangeEndDate || value > rangeEndDate) setRangeEndDate(value);
    }

    function updateRangeEnd(value) {
        setRangeEndDate(value);
        if (!rangeStartDate || value < rangeStartDate) setRangeStartDate(value);
    }

    function toggleSidebar() {
        if (isCompactViewport) {
            setMobileSidebarOpen((open) => !open);
            return;
        }
        setSidebarHidden((current) => {
            const next = !current;
            saveSidebarPreference(next);
            return next;
        });
    }

    function closeMobileSidebarAfterNavigation(event) {
        if (isCompactViewport && event.target.closest('a')) {
            setMobileSidebarOpen(false);
        }
    }

    const sidebarVisible = isCompactViewport
        ? mobileSidebarOpen
        : !sidebarHidden;
    const sidebarToggleButton = (
        <button
            type="button"
            className="sidebar-toggle"
            onClick={toggleSidebar}
            aria-controls="sidebar"
            aria-expanded={sidebarVisible}
            aria-label={
                !sidebarVisible
                    ? 'Tampilkan sidebar'
                    : 'Sembunyikan sidebar'
            }
            title={
                !sidebarVisible
                    ? 'Tampilkan sidebar'
                    : 'Sembunyikan sidebar'
            }
        >
            {!sidebarVisible ? '☰' : '☷'}
        </button>
    );

    return (
        <div
            className={
                `layout-shell${sidebarHidden ? ' sidebar-hidden' : ''}${isCompactViewport && mobileSidebarOpen ? ' mobile-sidebar-open' : ''}`
            }
        >
            {isCompactViewport && mobileSidebarOpen && (
                <button
                    className="sidebar-overlay"
                    type="button"
                    aria-label="Tutup navigasi"
                    onClick={() => setMobileSidebarOpen(false)}
                />
            )}
            <aside
                className="sidebar"
                id="sidebar"
                inert={isCompactViewport && !mobileSidebarOpen}
            >
                    <NavLink
                        className="side-brand"
                        to="/beranda"
                        aria-label="Kembali ke Beranda"
                    >
                        <img
                            src={logoImage}
                            alt="Logo Reethau"
                            style={{
                                height: '50px',
                                width: 'auto',
                                maxWidth: '100%',
                                objectFit: 'contain',
                            }}
                        />
                    </NavLink>

                    <nav
                        className="side-nav"
                        aria-label="Navigasi utama"
                        onClick={closeMobileSidebarAfterNavigation}
                    >
                        <NavLink
                            className={classForNav}
                            to="/beranda"
                        >
                            <NavigationIcon name="home" />
                            <span>Beranda</span>
                        </NavLink>

                        {canViewAllFeatures && (
                            <>
                                <span className="nav-section-label">MONITORING KOMERSIAL</span>

                                <NavLink
                                    className={classForNav}
                                    to="/harian"
                                >
                                    <NavigationIcon name="daily" />
                                    <span>Harian</span>
                                </NavLink>

                                <NavLink
                                    className={classForNav}
                                    to="/issue"
                                >
                                    <NavigationIcon name="issue" />
                                    <span>Issue</span>
                                </NavLink>

                                <NavLink
                                    className={classForNav}
                                    to="/budget"
                                >
                                    <NavigationIcon name="budget" />
                                    <span>Budget</span>
                                </NavLink>

                                <hr className="nav-divider" aria-hidden="true" />
                                <span className="nav-section-label">MINGGUAN</span>

                                <NavLink
                                    className={classForCompactNav}
                                    to="/mingguan/volume"
                                >
                                    <NavigationIcon name="volume" />
                                    <span>Volume</span>
                                </NavLink>

                                <NavLink
                                    className={classForCompactNav}
                                    to="/mingguan/average-price"
                                >
                                    <NavigationIcon name="averagePrice" />
                                    <span>Average Price</span>
                                </NavLink>

                                <NavLink
                                    className={classForCompactNav}
                                    to="/mingguan/complain"
                                >
                                    <NavigationIcon name="complain" />
                                    <span>Complain</span>
                                </NavLink>

                                <hr className="nav-divider" aria-hidden="true" />
                                <NavLink
                                    className={classForNav}
                                    to="/bulanan"
                                >
                                    <NavigationIcon name="monthly" />
                                    <span>Bulanan</span>
                                </NavLink>

                                <NavLink
                                    className={classForNav}
                                    to="/tahunan"
                                >
                                    <NavigationIcon name="yearly" />
                                    <span>Tahunan</span>
                                </NavLink>

                                <hr className="nav-divider" aria-hidden="true" />
                                <span className="nav-section-label">KERJA SAMA</span>

                                <div
                                    className="nav-submenu cooperation-submenu"
                                    id="cooperationSubmenu"
                                >
                                    {user.role === 'admin' && (
                                        <NavLink
                                            className={classForCompactNav}
                                            to="/kerja-sama"
                                            end
                                        >
                                            <NavigationIcon name="cooperationList" />
                                            Daftar kerja sama
                                        </NavLink>
                                    )}
                                    <NavLink
                                        className={classForCompactNav}
                                        to="/kerja-sama/masa-berlaku"
                                    >
                                        <NavigationIcon name="validity" />
                                        Masa berlaku
                                    </NavLink>
                                </div>


                                {user.role === 'admin' && (
                                    <>
                                        <hr className="nav-divider" aria-hidden="true" />
                                        <span className="nav-section-label">PENGELOLAAN</span>
                                        <NavLink className={classForNav} to="/pengguna">
                                            <span className="nav-ico" aria-hidden="true">♙</span>
                                            <span>Pengguna</span>
                                        </NavLink>
                                    </>
                                )}
                            </>
                        )}

                    </nav>

                    <div className="sidebar-foot">
                        <div className="sidebar-user-avatar" aria-hidden="true">
                            {(user?.name || user?.username || 'A').charAt(0).toUpperCase()}
                        </div>
                        <div className="sidebar-user-details">
                            <strong>{user?.name || user?.username || 'Pengunjung'}</strong>
                            <span>{user?.role === 'admin' ? 'Administrator' : user?.role === 'user' ? 'User' : 'Guest'}</span>
                        </div>
                        <button
                            className="sidebar-logout"
                            type="button"
                            aria-label={hasAuthenticatedUser ? 'Keluar dari aplikasi' : 'Login Admin atau User'}
                            title={hasAuthenticatedUser ? 'Keluar dari aplikasi' : 'Login Admin atau User'}
                            disabled={loggingOut}
                            onClick={hasAuthenticatedUser ? logout : () => navigate('/login')}
                        >
                            <span aria-hidden="true">↪</span>
                        </button>
                    </div>

            </aside>

            <main className={`app-shell${isWeeklyVolume ? ' weekly-volume-shell' : ''}${isYearly ? ' yearly-shell' : ''}${isMonthly ? ' monthly-shell' : ''}${isHome ? ' home-shell' : ''}${isBudget ? ' budget-shell' : ''}${isUsers ? ' users-shell' : ''}${isCooperation ? ' cooperation-shell' : ''}${isAveragePrice && user?.role === 'user' ? ' average-price-user-shell' : ''}`}>
                <header className="topbar">
                    <div className="topbar-brand">
                        {(!isCompactViewport || !mobileSidebarOpen) && sidebarToggleButton}

                        <div
                            className="topbar-logo"
                            aria-hidden="true"
                        >
                            <span className="logo-bar logo-bar-one" />
                            <span className="logo-bar logo-bar-two" />
                            <span className="logo-bar logo-bar-three" />
                        </div>

                        <div className="topbar-brand-text">
                            <h1>COMMERCIAL MONITORING</h1>
                            <p>Reethau Clean Energy</p>
                        </div>
                    </div>

            
                    <div className="topbar-actions">
                        {!isCooperation && (
                        <div className={`topbar-period-control${isAveragePrice || isBudget ? ' single-date' : ` date-range${rangePickerOpen ? ' is-open' : ''}`}`}>
                                <span
                                    className="topbar-calendar"
                                    aria-hidden="true"
                                >
                                    ▦
                                </span>

                                <div className="topbar-period-content">
                                    <small>Periode Data</small>
                                    {isAveragePrice ? (
                                        <input
                                            aria-label="Bulan Average Price"
                                            type="month"
                                            value={averagePriceMonth}
                                            disabled={loadingDates || dates.length === 0}
                                            onChange={(event) => setAveragePriceMonth(event.target.value)}
                                        />
                                    ) : isBudget ? (
                                        <select
                                            aria-label="Bulan Periode Data Budget"
                                            value={selectedDate.slice(0, 7)}
                                            disabled={loadingDates || availablePeriodMonths.length === 0}
                                            onChange={(event) => selectBudgetPeriodMonth(event.target.value)}
                                        >
                                            {availablePeriodMonths.map((month) => (
                                                <option key={month} value={month}>
                                                    {new Date(`${month}-01T00:00:00`).toLocaleDateString('id-ID', {
                                                        month: 'long',
                                                        year: 'numeric',
                                                    })}
                                                </option>
                                            ))}
                                        </select>
                                    ) : (
                                        <>
                                            <button
                                                className="topbar-period-summary"
                                                type="button"
                                                aria-label="Pilih rentang tanggal"
                                                aria-expanded={rangePickerOpen}
                                                onClick={() => setRangePickerOpen((open) => !open)}
                                            >
                                                <span>
                                                    {isDaily
                                                        ? `${formatPeriodDate(rangeStartDate)} - ${formatPeriodDate(rangeEndDate)}`
                                                        : formatPeriodDate(rangeStartDate)}
                                                </span>
                                                <span className="topbar-period-summary-icon" aria-hidden="true">▾</span>
                                            </button>
                                            {rangePickerOpen && (
                                                <div className="topbar-period-range">
                                                    <label>
                                                        <span>Dari</span>
                                                        <input
                                                            aria-label="Tanggal awal periode"
                                                            type="date"
                                                            value={rangeStartDate}
                                                            disabled={loadingDates || dates.length === 0}
                                                            onChange={(event) => isDaily
                                                                ? updateDailyRangeStart(event.target.value)
                                                                : updateRangeStart(event.target.value)}
                                                        />
                                                    </label>
                                                    <label>
                                                        <span>Sampai</span>
                                                        <input
                                                            aria-label="Tanggal akhir periode"
                                                            type="date"
                                                            value={rangeEndDate}
                                                            min={rangeStartDate || undefined}
                                                            disabled={loadingDates || dates.length === 0}
                                                            onChange={(event) => isDaily
                                                                ? updateDailyRangeEnd(event.target.value)
                                                                : updateRangeEnd(event.target.value)}
                                                        />
                                                    </label>
                                                    <button
                                                        className="topbar-period-done"
                                                        type="button"
                                                        onClick={() => setRangePickerOpen(false)}
                                                    >
                                                        Selesai
                                                    </button>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                        </div>
                        )}

                    </div>
                </header>

                {dataError && (
                    <div className="notice bad" role="alert">
                        {dataError}
                    </div>
                )}

                <Outlet context={outletContext} />

            </main>
        </div>
    );
}
