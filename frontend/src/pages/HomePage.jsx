import React, { useEffect, useMemo, useState } from 'react';
import { Line } from 'react-chartjs-2';
import {
    CategoryScale,
    Chart as ChartJS,
    Legend,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
} from 'chart.js';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT', 'OFF'];

ChartJS.register(
    CategoryScale,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
    Legend,
);

const months = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
];
const formatNumber = (value, maximumFractionDigits = 2) =>
    new Intl.NumberFormat('id-ID', { maximumFractionDigits }).format(Number(value ?? 0));
const formatCurrency = (value) =>
    `Rp ${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(Number(value ?? 0))}`;
const formatAveragePrice = (value) =>
    `Rp ${new Intl.NumberFormat('id-ID', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number(value ?? 0))}`;
const formatPercent = (value) =>
    `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 }).format(Number(value ?? 0))}%`;

function SectionHeading({ title, description }) {
    return (
        <div className="home-section-heading">
            <div>
                <h2>{title}</h2>
                <p>{description}</p>
            </div>
        </div>
    );
}

function Message({ loading, error, empty, children }) {
    if (loading) return <div className="home-message">Memuat data...</div>;
    if (error) return <div className="home-message home-message-error" role="alert">{error}</div>;
    if (empty) return <div className="home-message">{empty}</div>;
    return children;
}

const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
        legend: {
            position: 'bottom',
            labels: { boxWidth: 9, boxHeight: 9, font: { size: 10 }, usePointStyle: true },
        },
        tooltip: {
            callbacks: {
                label: (context) => `${context.dataset.label}: ${formatNumber(context.raw)}`,
            },
        },
    },
    scales: {
        x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 0, autoSkip: true } },
        y: {
            beginAtZero: true,
            grid: { color: '#e9f0f6' },
            ticks: {
                font: { size: 9 },
                callback: (value) => new Intl.NumberFormat('id-ID', { notation: 'compact' }).format(value),
            },
        },
    },
};

function PeriodMetrics({ summary, reportSummary }) {
    const displayedSO = summary?.manual_so ?? reportSummary?.so;
    const displayedActual = reportSummary?.actual ?? 0;
    const displayedDiff = displayedActual - Number(displayedSO ?? 0);
    const achievement = reportSummary?.so
        ? displayedActual / reportSummary.so * 100
        : null;
    return (
        <div className="home-period-metrics">
            <article className="kpi kpi-blue">
                <div className="kpi-icon">◎</div>
                <div><span>TOTAL TARGET</span><strong>{formatNumber(displayedSO)}</strong><small>{summary?.manual_so == null ? 'Data pada periode terpilih' : 'Target bulanan dari halaman Bulanan'}</small></div>
            </article>
            <article className="kpi kpi-green">
                <div className="kpi-icon">↗</div>
                <div><span>TOTAL ACTUAL</span><strong>{formatNumber(displayedActual)}</strong><small>Total Actual Summary Report</small></div>
            </article>
            <article className={`kpi ${Number(displayedDiff ?? 0) >= 0 ? 'kpi-purple' : 'kpi-negative'}`}>
                <div className="kpi-icon">±</div>
                <div><span>DIFF (ACTUAL − TARGET)</span><strong>{Number(displayedDiff ?? 0) > 0 ? '+' : ''}{formatNumber(displayedDiff)}</strong><small>{Number(displayedDiff ?? 0) >= 0 ? 'Di atas target' : 'Di bawah target'}</small></div>
            </article>
            <article className="kpi kpi-teal">
                <div className="kpi-icon">♙</div>
                <div><span>CUSTOMER AKTIF</span><strong>{formatNumber(summary?.customers, 0)}</strong><small>Tidak termasuk customer OFF</small></div>
            </article>
            <article className="kpi kpi-purple">
                <div className="kpi-icon">%</div>
                <div><span>PENCAPAIAN SO</span><strong>{achievement == null ? '—' : formatPercent(achievement)}</strong><small>{summary?.so ? 'Actual dibanding SO' : 'Target belum tersedia'}</small></div>
            </article>
        </div>
    );
}

export default function HomePage() {
    const { rangeStartDate, rangeEndDate, dataError, loadingDates } = useOutletContext();
    const [summary, setSummary] = useState(null);
    const [priceReport, setPriceReport] = useState(null);
    const [complaints, setComplaints] = useState([]);
    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!rangeStartDate || !rangeEndDate) {
            setSummary(null);
            setPriceReport(null);
            setComplaints([]);
            setErrors({});
            return undefined;
        }

        let active = true;
        setLoading(true);
        setErrors({});

        const query = new URLSearchParams({
            start_date: rangeStartDate,
            end_date: rangeEndDate,
        });
        Promise.allSettled([
            api(`/api/home-summary-range?${query.toString()}`),
            api(`/api/monthly-average-price-range?${query.toString()}`),
            api('/api/complaints'),
        ]).then((results) => {
            if (!active) return;
            const keys = ['summary', 'price', 'complaints'];
            const nextErrors = {};
            results.forEach((result, index) => {
                if (result.status === 'fulfilled') {
                    if (index === 0) {
                        setSummary(result.value);
                    } else if (index === 1) {
                        setPriceReport(result.value);
                    } else {
                        setComplaints(result.value);
                    }
                } else {
                    if (index === 0) setSummary(null);
                    if (index === 1) setPriceReport(null);
                    if (index === 2) setComplaints([]);
                    nextErrors[keys[index]] = result.reason?.message || 'Data gagal dimuat.';
                }
            });
            setErrors(nextErrors);
        }).finally(() => {
            if (active) setLoading(false);
        });

        return () => { active = false; };
    }, [rangeStartDate, rangeEndDate]);

    const monthlyComplaints = complaints.filter((item) =>
        item.date >= rangeStartDate && item.date <= rangeEndDate);
    const openComplaints = monthlyComplaints.filter((item) => item.status === 'Open').length;
    const closedComplaints = monthlyComplaints.filter((item) => item.status === 'Closed').length;
    const monitoringComplaints = monthlyComplaints.filter((item) => item.status === 'Monitoring').length;
    const validPriceRows = priceReport?.rows?.filter((row) =>
        row.price_unit === 'IDR_SM3'
            ? Number(row.price_rp_per_sm3) > 0
            : Number(row.price_usd_per_mmbtu) > 0
                && Number(row.sm3_per_mmbtu) > 0
                && Number(row.exchange_rate) > 0) ?? [];
    const validPriceCount = priceReport?.valid_price_count ?? validPriceRows.length;
    const regionalVolume = useMemo(() => {
        if (priceReport?.regions) {
            return priceReport.regions.map((region) => ({
                region: region.region,
                so: region.so_sm3,
                actual: region.actual_sm3,
            }));
        }
        const regions = new Map();
        for (const row of priceReport?.rows ?? []) {
            const region = row.region || 'Belum ditentukan';
            const current = regions.get(region) ?? { so: 0, actual: 0 };
            current.so += Number(row.so_sm3 ?? 0);
            current.actual += Number(row.actual_sm3 ?? 0);
            regions.set(region, current);
        }
        return [...regions.entries()].map(([region, totals]) => ({ region, ...totals }));
    }, [priceReport]);

    const monthlyChart = useMemo(() => ({
        labels: summary?.year_months?.map((item) => {
            const [year, month] = item.month.split('-');
            return `${months[Number(month) - 1].slice(0, 3)} '${year.slice(-2)}`;
        }) ?? [],
        datasets: [
            {
                label: 'Target',
                data: summary?.year_months?.map((item) =>
                    item.manual_so ?? (item.has_data ? item.so : null)) ?? [],
                borderColor: '#139768',
                backgroundColor: 'rgb(19 151 104 / 12%)',
                tension: 0.28,
                spanGaps: false,
            },
            {
                label: 'SO',
                data: summary?.year_months?.map((item) => item.has_data ? item.so : null) ?? [],
                borderColor: '#1777d1',
                backgroundColor: 'rgb(23 119 209 / 12%)',
                tension: 0.28,
                spanGaps: false,
            },
            {
                label: 'Actual',
                data: summary?.year_months?.map((item) => item.has_data ? item.actual : null) ?? [],
                borderColor: '#f0a43a',
                backgroundColor: 'rgb(240 164 58 / 12%)',
                tension: 0.28,
                spanGaps: false,
            },
        ],
    }), [summary]);

    return (
        <div className="home-page">
            <section className="home-section home-kpi-section" aria-label="Ringkasan">
                {!rangeStartDate && <div className="home-message">{dataError || (loadingDates ? 'Memuat periode...' : 'Pilih periode laporan.')}</div>}
                <Message loading={loading} error={errors.summary} empty={!summary ? '' : ''}>
                    {summary && <PeriodMetrics summary={summary.month_summary} reportSummary={summary.summary_report} />}
                </Message>
                <p className="home-kpi-note">Total SO dan Actual mencakup seluruh customer termasuk OFF; jumlah customer aktif tidak menghitung customer berstatus OFF. Bulan tanpa data ditampilkan tanpa angka rekaan.</p>
            </section>

            <section className="home-section home-monthly-chart-section">
                <SectionHeading
                    title="Rekapan Bulanan"
                    description="Perbandingan target, SO, dan actual per bulan pada rentang tanggal terpilih."
                />
                <Message
                    loading={loading}
                    error={errors.summary}
                    empty={!summary?.year_months?.some((item) => item.has_data) ? 'Belum ada transaksi pada rentang tanggal yang dipilih.' : ''}
                >
                    {summary && <div className="home-monthly-chart"><Line data={monthlyChart} options={chartOptions} /></div>}
                </Message>
            </section>

            <section className="home-section" aria-label="Informasi mingguan">
                <div className="home-weekly-details">
                <article className="home-subpanel home-volume-panel">
                    <h3>Volume dan perbandingan wilayah</h3>
                    <p className="home-subpanel-caption">Volume menggunakan SO/Actual sales. Wilayah mengikuti data yang diinput pada laporan Average Price.</p>
                    <Message loading={loading} error={errors.price} empty={priceReport?.rows?.length === 0 ? 'Belum ada volume pada periode ini.' : ''}>
                        <div className="home-region-list">
                            {regionalVolume.length === 0
                                ? <span className="home-muted">Belum ada data wilayah yang dapat dibandingkan.</span>
                                : regionalVolume.map((region) => (
                                    <div key={region.region}>
                                        <span>{region.region}</span>
                                        <small>SO {formatNumber(region.so)} · Actual {formatNumber(region.actual)} Sm³</small>
                                    </div>
                                ))}
                        </div>
                    </Message>
                </article>
                    <article className="home-subpanel">
                        <h3>Average Price periode terpilih</h3>
                        <p className="home-subpanel-caption">Mengikuti volume dan hasil pada tab AVG untuk bulan yang telah tersedia.</p>
                        <Message loading={loading} error={errors.price} empty={validPriceCount === 0 ? 'Data harga/kurs belum cukup untuk menghitung Average Price.' : ''}>
                            <div className="home-year-summary home-price-summary">
                                <div><small>Average Rp/Sm³</small><strong>{formatAveragePrice(priceReport?.totals?.average_price_rp_sm3)}</strong></div>
                                <div><small>Total MMBTU</small><strong>{formatNumber(priceReport?.totals?.mmbtu, 3)}</strong></div>
                                <div><small>Total USD</small><strong>{formatCurrency(priceReport?.totals?.usd)}</strong></div>
                                <div><small>Total Rupiah</small><strong>{formatCurrency(priceReport?.totals?.rupiah)}</strong></div>
                            </div>
                            <small className="home-data-coverage">Perhitungan mencakup {validPriceCount} customer dengan harga/kurs valid.</small>
                        </Message>
                    </article>
                    <article className="home-subpanel">
                        <h3>Complain periode terpilih</h3>
                        <p className="home-subpanel-caption">Jumlah keluhan menurut tanggal laporan dan status penyelesaian.</p>
                        <Message loading={loading} error={errors.complaints}>
                            <div className="home-complaint-total"><strong>{monthlyComplaints.length}</strong><span>Total keluhan</span></div>
                            <div className="home-complaint-status">
                                <span><i className="open" />Open <b>{openComplaints}</b></span>
                                <span><i className="closed" />Closed <b>{closedComplaints}</b></span>
                                <span><i className="monitoring" />Monitoring <b>{monitoringComplaints}</b></span>
                            </div>
                        </Message>
                    </article>
                </div>
            </section>

        </div>
    );
}
