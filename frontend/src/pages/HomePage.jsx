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

function PeriodMetrics({ summary, reportSummary, periodType }) {
    const displayedSO = periodType === 'daily'
        ? reportSummary?.so
        : summary?.manual_so ?? reportSummary?.so;
    const displayedActual = reportSummary?.actual ?? 0;
    const displayedDiff = displayedActual - Number(displayedSO ?? 0);
    const achievement = reportSummary?.so
        ? displayedActual / reportSummary.so * 100
        : null;
    return (
        <div className="home-period-metrics">
            <article className="kpi kpi-blue">
                <div className="kpi-icon">◎</div>
                <div><span>{periodType === 'daily' ? 'TOTAL SO' : 'TOTAL TARGET'}</span><strong>{formatNumber(displayedSO)}</strong><small>{periodType === 'daily' ? 'Sales Order pada tanggal terpilih' : summary?.manual_so == null ? 'Data pada periode terpilih' : 'Target dari halaman Bulanan'}</small></div>
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
    const {
        homePeriodType,
        rangeStartDate,
        rangeEndDate,
        dataError,
        loadingDates,
    } = useOutletContext();
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

    const dailyRowsByDate = new Map(
        (summary?.days ?? []).map((item) => [item.date, item]),
    );
    const dailyChartRows = useMemo(() => {
        if (!rangeStartDate || !rangeEndDate) return [];
        const current = new Date(`${rangeStartDate}T00:00:00Z`);
        const end = new Date(`${rangeEndDate}T00:00:00Z`);
        const rows = [];
        while (current <= end) {
            const date = current.toISOString().slice(0, 10);
            rows.push(dailyRowsByDate.get(date) ?? {
                date,
                has_data: false,
                so: 0,
                actual: 0,
            });
            current.setUTCDate(current.getUTCDate() + 1);
        }
        return rows;
    }, [rangeStartDate, rangeEndDate, summary]);
    const chartRows = homePeriodType === 'yearly'
        ? summary?.year_months ?? []
        : dailyChartRows;
    const chartLabels = chartRows.map((item) => {
        if (homePeriodType === 'yearly') {
            const [year, month] = item.month.split('-');
            return `${months[Number(month) - 1].slice(0, 3)} '${year.slice(-2)}`;
        }
        const [, month, day] = item.date.split('-');
        return homePeriodType === 'monthly'
            ? day
            : `${day} ${months[Number(month) - 1].slice(0, 3)}`;
    });
    const periodChart = useMemo(() => {
        const datasets = [];
        if (homePeriodType === 'yearly') {
            datasets.push({
                label: 'Target',
                data: chartRows.map((item) =>
                    item.manual_so ?? (item.has_data ? item.so : null)),
                borderColor: '#139768',
                backgroundColor: 'rgb(19 151 104 / 12%)',
                tension: 0.28,
                spanGaps: false,
            });
        }
        datasets.push(
            {
                label: 'SO',
                data: chartRows.map((item) => item.has_data ? item.so : null),
                borderColor: '#1777d1',
                backgroundColor: 'rgb(23 119 209 / 12%)',
                tension: 0.28,
                spanGaps: false,
            },
            {
                label: 'Actual',
                data: chartRows.map((item) => item.has_data ? item.actual : null),
                borderColor: '#f0a43a',
                backgroundColor: 'rgb(240 164 58 / 12%)',
                tension: 0.28,
                spanGaps: false,
            },
        );
        return { labels: chartLabels, datasets };
    }, [chartRows, chartLabels, homePeriodType]);
    const periodSummary = homePeriodType === 'daily'
        ? summary?.days?.[0]
        : homePeriodType === 'yearly'
            ? summary?.year_summary
            : summary?.month_summary;
    const periodChartTitle = homePeriodType === 'daily'
        ? 'Rekapan Harian'
        : homePeriodType === 'yearly'
            ? 'Rekapan Tahunan'
            : 'Rekapan Bulanan';
    const periodChartDescription = homePeriodType === 'daily'
        ? 'Perbandingan Target, SO, dan Actual pada tanggal yang dipilih.'
        : homePeriodType === 'yearly'
            ? 'Perbandingan Target, SO, dan Actual per bulan pada tahun yang dipilih.'
            : 'Perbandingan Target, SO, dan Actual per hari pada bulan yang dipilih.';

    return (
        <div className="home-page">
            <section className="home-section home-kpi-section" aria-label="Ringkasan">
                {!rangeStartDate && <div className="home-message">{dataError || (loadingDates ? 'Memuat periode...' : 'Pilih periode laporan.')}</div>}
                <Message loading={loading} error={errors.summary} empty={!summary ? '' : ''}>
                    {summary && <PeriodMetrics summary={periodSummary} reportSummary={summary.summary_report} periodType={homePeriodType} />}
                </Message>
                <p className="home-kpi-note">Ringkasan mengikuti periode terpilih. Total SO dan Actual mencakup seluruh customer termasuk OFF; jumlah customer aktif tidak menghitung customer berstatus OFF.</p>
            </section>

            <section className="home-section home-monthly-chart-section">
                <SectionHeading
                    title={periodChartTitle}
                    description={periodChartDescription}
                />
                <Message
                    loading={loading}
                    error={errors.summary}
                    empty={!chartRows.some((item) => item.has_data) ? 'Belum ada transaksi pada periode yang dipilih.' : ''}
                >
                    {summary && <div className="home-monthly-chart"><Line data={periodChart} options={chartOptions} /></div>}
                </Message>
            </section>

            <section className="home-section" aria-label="Informasi mingguan">
                <div className="home-weekly-details">
                <article className="home-subpanel home-volume-panel">
                    <h3>Volume dan perbandingan wilayah</h3>
                    <p className="home-subpanel-caption">Volume mengikuti periode terpilih; wilayah mengikuti data pada laporan Average Price.</p>
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
                        <p className="home-subpanel-caption">Perhitungan mengikuti periode yang dipilih dan harga efektif pada tab Average Price.</p>
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
