import { useEffect, useMemo, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from 'chart.js';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';
import SectionIcon from '../components/SectionIcon';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT'];
const complaintColors = ['#16845b', '#e5a12c', '#3885b8', '#8a6bb8', '#d45f62', '#55a6a0'];

const formatNumber = (value, maximumFractionDigits = 2) =>
    new Intl.NumberFormat('id-ID', { maximumFractionDigits }).format(Number(value ?? 0));
const formatVolume = (value) =>
    new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(Number(value ?? 0));
const formatAveragePrice = (value) =>
    `Rp ${new Intl.NumberFormat('id-ID', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number(value ?? 0))}`;
const formatPercent = (value) =>
    `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 }).format(Number(value ?? 0))}%`;

const kpiIcons = {
    target: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="1" /></>,
    order: <><path d="M7 4h8l4 4v12H7z" /><path d="M15 4v5h4M10 13h6m-6 3h6" /></>,
    actual: <><path d="M4 19V5m0 14h16" /><path d="m7 15 4-4 3 2 5-6" /><path d="M15 7h4v4" /></>,
    variance: <><path d="M5 8h13m0 0-3-3m3 3-3 3M19 16H6m0 0 3-3m-3 3 3 3" /></>,
    achievement: <><path d="M4 17a8 8 0 1 1 16 0" /><path d="m12 13 4-4m-9 8h10" /><circle cx="12" cy="13" r="1" /></>,
};

function KpiIcon({ name }) {
    return (
        <div className="kpi-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                {kpiIcons[name]}
            </svg>
        </div>
    );
}

const volumeValueLabels = {
    id: 'homeVolumeValueLabels',
    afterDatasetsDraw(chart) {
        const { ctx } = chart;
        ctx.save();
        ctx.font = '9px "Segoe UI", Arial, sans-serif';
        ctx.fillStyle = '#354b40';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        chart.data.datasets.forEach((dataset, datasetIndex) => {
            const metadata = chart.getDatasetMeta(datasetIndex);
            metadata.data.forEach((element, index) => {
                const value = Number(dataset.data[index] ?? 0);
                if (!Number.isFinite(value) || value === 0) return;
                const { x, y } = element.tooltipPosition();
                ctx.fillText(formatVolume(value), x, y - 4);
            });
        });
        ctx.restore();
    },
};

const volumeChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    layout: { padding: { top: 8 } },
    interaction: { mode: 'index', intersect: false },
    plugins: {
        legend: {
            position: 'top',
            align: 'end',
            labels: { boxWidth: 9, boxHeight: 9, font: { size: 10 }, usePointStyle: true, pointStyle: 'rect' },
        },
        tooltip: {
            callbacks: {
                label: (context) => `${context.dataset.label}: ${formatVolume(context.raw)}`,
            },
        },
    },
    scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 0, autoSkip: false } },
        y: { beginAtZero: true, grid: { color: '#e9f0f6' }, ticks: { display: false } },
    },
};

function Message({ loading, error, empty, children }) {
    if (loading) return <div className="home-message">Memuat data...</div>;
    if (error) return <div className="home-message home-message-error" role="alert">{error}</div>;
    if (empty) return <div className="home-message">{empty}</div>;
    return children;
}

function PeriodMetrics({ summary, reportSummary }) {
    const displayedSO = summary?.manual_so ?? reportSummary?.so;
    const displayedActual = reportSummary?.actual ?? 0;
    const displayedDiff = displayedActual - Number(displayedSO ?? 0);
    const target = summary?.manual_so;
    const achievement = target != null && Number(target) > 0
        ? displayedActual / Number(target) * 100
        : null;
    const achievementProgress = achievement == null
        ? 0
        : Math.min(Math.max(achievement, 0), 100);
    return (
        <div className="home-period-metrics" role="group" aria-label="Indikator kinerja penjualan">
            <article className="kpi kpi-blue">
                <KpiIcon name="target" />
                <div className="home-kpi-content"><span>Target Penjualan</span><strong>{formatNumber(displayedSO)}</strong><small>{summary?.manual_so == null ? 'Data pada periode terpilih' : 'Target bulanan dari halaman Bulanan'}</small></div>
            </article>
            <article className="kpi kpi-teal">
                <KpiIcon name="order" />
                <div className="home-kpi-content"><span>Total Sales Order</span><strong>{formatNumber(reportSummary?.so)}</strong><small>Total dari Summary Report</small></div>
            </article>
            <article className="kpi kpi-green">
                <KpiIcon name="actual" />
                <div className="home-kpi-content"><span>Realisasi Penjualan</span><strong>{formatNumber(displayedActual)}</strong><small>Realisasi dari Summary Report</small></div>
            </article>
            <article className={`kpi ${Number(displayedDiff ?? 0) >= 0 ? 'kpi-purple' : 'kpi-negative'}`}>
                <KpiIcon name="variance" />
                <div className="home-kpi-content"><span>Varians terhadap Target</span><strong>{Number(displayedDiff ?? 0) > 0 ? '+' : ''}{formatNumber(displayedDiff)}</strong><small>{Number(displayedDiff ?? 0) >= 0 ? 'Di atas target' : 'Di bawah target'}</small></div>
            </article>
            <article className="kpi kpi-purple">
                <KpiIcon name="achievement" />
                <div className="home-kpi-content"><span>Pencapaian Target</span><strong>{achievement == null ? '—' : formatPercent(achievement)}</strong><small>{target != null && Number(target) > 0 ? 'Realisasi dibanding target' : 'Target belum tersedia'}</small>
                    {achievement != null && <div className="home-kpi-progress" role="progressbar" aria-label="Pencapaian target" aria-valuemin={0} aria-valuemax={100} aria-valuenow={achievementProgress}><span style={{ width: `${achievementProgress}%` }} /></div>}
                </div>
            </article>
        </div>
    );
}

export default function HomePage() {
    const {
        rangeStartDate,
        rangeEndDate,
        dataError,
        loadingDates,
        canEdit,
        canViewHomeAverage,
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
        const requests = [
            ['summary', api(`/api/home-summary-range?${query.toString()}`)],
            ...(canViewHomeAverage ? [['price', api(`/api/monthly-average-price-range?${query.toString()}`)]] : []),
            ['complaints', api('/api/complaints')],
        ];
        if (!canEdit) setPriceReport(null);
        Promise.allSettled(requests.map(([, request]) => request)).then((results) => {
            if (!active) return;
            const nextErrors = {};
            results.forEach((result, index) => {
                const key = requests[index][0];
                if (result.status === 'fulfilled') {
                    if (key === 'summary') {
                        setSummary(result.value);
                    } else if (key === 'price') {
                        setPriceReport(result.value);
                    } else if (key === 'complaints') {
                        setComplaints(result.value);
                    }
                } else {
                    if (key === 'summary') setSummary(null);
                    if (key === 'price') setPriceReport(null);
                    if (key === 'complaints') setComplaints([]);
                    nextErrors[key] = result.reason?.message || 'Data gagal dimuat.';
                }
            });
            setErrors(nextErrors);
        }).finally(() => {
            if (active) setLoading(false);
        });

        return () => { active = false; };
    }, [rangeStartDate, rangeEndDate, canEdit, canViewHomeAverage]);

    const monthlyComplaints = complaints.filter((item) =>
        item.date >= rangeStartDate && item.date <= rangeEndDate);
    const openComplaints = monthlyComplaints.filter((item) => item.status === 'Open').length;
    const closedComplaints = monthlyComplaints.filter((item) => item.status === 'Closed').length;
    const monitoringComplaints = monthlyComplaints.filter((item) => item.status === 'Monitoring').length;
    const complaintTypeTotals = Object.entries(monthlyComplaints.reduce((counts, item) => {
        const type = String(item.type || 'Belum dikategorikan');
        counts[type] = (counts[type] || 0) + 1;
        return counts;
    }, {})).map(([name, value]) => ({ name, value }));
    const complaintTotal = complaintTypeTotals.reduce((total, item) => total + item.value, 0);
    let complaintSliceEnd = 0;
    const complaintDonut = complaintTotal
        ? `conic-gradient(${complaintTypeTotals.map((item, index) => {
            const start = complaintSliceEnd / complaintTotal * 100;
            complaintSliceEnd += item.value;
            const end = complaintSliceEnd / complaintTotal * 100;
            return `${complaintColors[index % complaintColors.length]} ${start}% ${end}%`;
        }).join(', ')})`
        : '#e7eee9';
    const validPriceRows = priceReport?.rows?.filter((row) =>
        row.price_unit === 'IDR_SM3'
            ? Number(row.price_rp_per_sm3) > 0
            : Number(row.price_usd_per_mmbtu) > 0
                && Number(row.sm3_per_mmbtu) > 0
                && (Number(row.exchange_rate) > 0 || Number(row.rupiah_multiplier) > 0)) ?? [];
    const validPriceCount = priceReport?.valid_price_count ?? validPriceRows.length;
    const volumeComparison = useMemo(() => {
        const operatorTotals = summary?.month_summary?.operators ?? {};
        return {
            labels: operators,
            datasets: [
                { label: 'SO', data: operators.map((operator) => operatorTotals[operator]?.so ?? 0), backgroundColor: '#1777d1', borderRadius: 3, maxBarThickness: 32 },
                { label: 'Actual', data: operators.map((operator) => operatorTotals[operator]?.actual ?? 0), backgroundColor: '#f0a43a', borderRadius: 3, maxBarThickness: 32 },
            ],
        };
    }, [summary]);
    const regionalVolumes = useMemo(() => {
        const totals = {
            'JAWA BARAT': 0,
            'JAWA TENGAH': 0,
            'JAWA TIMUR': 0,
        };
        (summary?.regional_volumes ?? []).forEach((row) => {
            const normalizedRegion = String(row.region || '').trim().toUpperCase().replace(/_/g, ' ').replace(/\s+/g, ' ');
            if (!normalizedRegion || normalizedRegion === 'BELUM DITENTUKAN') return;
            const regionKey = normalizedRegion.includes('JAWA BARAT') || normalizedRegion === 'JABAR'
                ? 'JAWA BARAT'
                : normalizedRegion.includes('JAWA TENGAH') || normalizedRegion === 'JATENG'
                    ? 'JAWA TENGAH'
                    : normalizedRegion.includes('JAWA TIMUR') || normalizedRegion === 'JATIM'
                        ? 'JAWA TIMUR'
                        : normalizedRegion;
            totals[regionKey] = (totals[regionKey] ?? 0) + Number(row.actual_sm3 ?? 0);
        });
        const labels = {
            'JAWA BARAT': 'JABAR',
            'JAWA TENGAH': 'JATENG',
            'JAWA TIMUR': 'JATIM',
        };
        return Object.entries(totals).map(([region, volume]) => ({
            region: labels[region] ?? region,
            volume,
        }));
    }, [summary]);
    return (
        <div className="home-page">
            <section className="home-section home-kpi-section" aria-label="Ringkasan">
                {!rangeStartDate && <div className="home-message">{dataError || (loadingDates ? 'Memuat periode...' : 'Pilih periode laporan.')}</div>}
                <Message loading={loading} error={errors.summary} empty={!summary ? '' : ''}>
                    {summary && <PeriodMetrics summary={summary.month_summary} reportSummary={summary.summary_report} />}
                </Message>
            </section>

            <section className="home-section" aria-label="Informasi mingguan">
                <div className="home-weekly-details">
                <article className="home-subpanel home-volume-panel">
                    <h3><SectionIcon name="volume" />Perbandingan Volume per MS</h3>
                    <Message loading={loading} error={errors.summary}>
                        <div className="home-volume-comparison-body">
                            <div className="home-volume-summary">
                                <div className="home-total-volume">
                                    <small>Total volume keseluruhan</small>
                                    <strong>{formatVolume(summary?.summary_report?.actual)} <span>Sm3</span></strong>
                                </div>
                                <div className="home-regional-volume">
                                    <small>Volume per daerah</small>
                                    {regionalVolumes.map(({ region, volume }) => (
                                        <span key={region}><b>{region}</b>{formatVolume(volume)} Sm3</span>
                                    ))}
                                </div>
                            </div>
                            <div className="home-volume-chart">
                                <Bar data={volumeComparison} options={volumeChartOptions} plugins={[volumeValueLabels]} />
                            </div>
                        </div>
                    </Message>
                </article>
                    <div className="home-insights-stack">
                        {canViewHomeAverage && (
                            <article className="home-subpanel home-average-panel">
                                <h3><SectionIcon name="price" />Average Price periode terpilih</h3>
                                <Message loading={loading} error={errors.price} empty={validPriceCount === 0 ? 'Data harga/kurs belum cukup untuk menghitung Average Price.' : ''}>
                                    <div className="home-year-summary home-price-summary">
                                        <div><small>Average Rp/Sm³</small><strong>{formatAveragePrice(priceReport?.totals?.average_price_rp_sm3)}</strong></div>
                                        <div><small>Total MMBTU</small><strong>{formatNumber(priceReport?.totals?.mmbtu)}</strong></div>
                                    </div>
                                </Message>
                            </article>
                        )}
                        <article className="home-subpanel home-complaint-panel">
                            <h3><SectionIcon name="complaint" />Complain periode terpilih</h3>
                            <Message loading={loading} error={errors.complaints} empty={monthlyComplaints.length === 0 ? 'Tidak ada complain pada periode terpilih.' : ''}>
                                <div className="home-complaint-chart">
                                    <div className="home-complaint-donut" style={{ background: complaintDonut }}>
                                        <div><small>Total Complain</small><strong>{formatNumber(complaintTotal, 0)}</strong></div>
                                    </div>
                                    <div className="home-complaint-legend">
                                        {complaintTypeTotals.map((item, index) => (
                                            <div key={item.name}>
                                                <i style={{ background: complaintColors[index % complaintColors.length] }} />
                                                <p><b>{item.name}</b><span>{item.value} ({(item.value / complaintTotal * 100).toLocaleString('id-ID', { maximumFractionDigits: 1 })}%)</span></p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <div className="home-complaint-status">
                                    <span><i className="open" />Open <b>{openComplaints}</b></span>
                                    <span><i className="closed" />Closed <b>{closedComplaints}</b></span>
                                    <span><i className="monitoring" />Monitoring <b>{monitoringComplaints}</b></span>
                                </div>
                            </Message>
                        </article>
                    </div>
                </div>
            </section>

        </div>
    );
}
