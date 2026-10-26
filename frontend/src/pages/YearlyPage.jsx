import React, { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT'];
const regions = ['JAWA BARAT', 'JAWA TENGAH', 'JAWA TIMUR'];
const regionByOperator = {
    SETU: 'JAWA BARAT',
    KHT: 'JAWA BARAT',
    BLORA: 'JAWA TENGAH',
    WUNUT: 'JAWA TIMUR',
};

const formatNumber = (value) => new Intl.NumberFormat('id-ID', {
    maximumFractionDigits: 0,
}).format(Number(value) || 0);

const formatPercent = (value) => `${(Number(value) || 0).toLocaleString('id-ID', {
    maximumFractionDigits: 1,
})}%`;

const total = (values) => values.reduce((sum, value) => sum + (Number(value) || 0), 0);
const monthNames = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
];

function periodsBetween(startDate, endDate) {
    if (!startDate || !endDate) return [];
    const periods = [];
    const [startYear, startMonth] = startDate.slice(0, 7).split('-').map(Number);
    const [endYear, endMonth] = endDate.slice(0, 7).split('-').map(Number);
    let year = startYear;
    let month = startMonth;
    while (year < endYear || (year === endYear && month <= endMonth)) {
        periods.push(`${year}-${String(month).padStart(2, '0')}`);
        month += 1;
        if (month > 12) {
            month = 1;
            year += 1;
        }
    }
    return periods;
}

function buildCustomerRows(items = [], periods = []) {
    const customers = new Map();
    const periodIndexes = new Map(periods.map((period, index) => [period, index]));

    for (const item of items) {
        if (!customers.has(item.customer_key)) {
            customers.set(item.customer_key, {
                key: item.customer_key,
                customer: item.customer,
                operator: item.operator,
                region: regionByOperator[item.operator] || 'LAINNYA',
                soByMonth: Array(periods.length).fill(0),
                actualByMonth: Array(periods.length).fill(0),
                so: 0,
                actual: 0,
            });
        }

        const customer = customers.get(item.customer_key);
        const index = periodIndexes.get(item.period);
        if (index === undefined) continue;
        customer.soByMonth[index] += Number(item.so) || 0;
        customer.actualByMonth[index] += Number(item.actual) || 0;
        customer.so += Number(item.so) || 0;
        customer.actual += Number(item.actual) || 0;
    }

    return Array.from(customers.values());
}

function periodLabel(period) {
    const [year, month] = period.split('-').map(Number);
    return `${monthNames[month - 1]} ${year}`;
}

export default function YearlyPage() {
    const { rangeStartDate, rangeEndDate } = useOutletContext();
    const period = `${rangeStartDate}–${rangeEndDate}`;
    const periodKeys = useMemo(
        () => periodsBetween(rangeStartDate, rangeEndDate),
        [rangeStartDate, rangeEndDate],
    );
    const periodLabels = useMemo(() => periodKeys.map(periodLabel), [periodKeys]);
    const [region, setRegion] = useState('Semua Wilayah');
    const [operator, setOperator] = useState('Semua MS');
    const [records, setRecords] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        let cancelled = false;

        async function loadYearlyData() {
            setLoading(true);
            setError('');
            try {
                if (!rangeStartDate || !rangeEndDate) {
                    setRecords([]);
                    return;
                }
                const params = new URLSearchParams({
                    start_date: rangeStartDate,
                    end_date: rangeEndDate,
                });
                const result = await api(`/api/monthly-range?${params.toString()}`);
                if (!cancelled) setRecords(buildCustomerRows(result.items || [], periodKeys));
            } catch (loadError) {
                if (!cancelled) {
                    setRecords([]);
                    setError(loadError.message || 'Data tahunan gagal dimuat dari database.');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        loadYearlyData();
        return () => {
            cancelled = true;
        };
    }, [rangeStartDate, rangeEndDate, periodKeys]);

    const filteredCustomers = useMemo(() => records.filter((customer) => (
        (region === 'Semua Wilayah' || customer.region === region) &&
        (operator === 'Semua MS' || customer.operator === operator)
    )), [records, region, operator]);

    const monthlyGroups = useMemo(() => regions
        .filter((area) => region === 'Semua Wilayah' || area === region)
        .map((area) => {
            const areaRows = filteredCustomers.filter((customer) => customer.region === area);
            const operatorGroups = operators
                .filter((name) => operator === 'Semua MS' || name === operator)
                .map((name) => {
                    const operatorRows = areaRows.filter((customer) => customer.operator === name);
                    const otherRows = operatorRows.filter((customer) => !customer.key.startsWith('manualfob-'));
                    const fobRows = operatorRows.filter((customer) => customer.key.startsWith('manualfob-'));
                    const valuesFor = (list, field) => periodKeys.map((_, index) =>
                        total(list.map((customer) => customer[field][index])));
                    return {
                        name,
                        hasOtherRows: otherRows.length > 0,
                        hasFobRows: fobRows.length > 0,
                        otherSoValues: valuesFor(otherRows, 'soByMonth'),
                        otherActualValues: valuesFor(otherRows, 'actualByMonth'),
                        fobSoValues: valuesFor(fobRows, 'soByMonth'),
                        fobActualValues: valuesFor(fobRows, 'actualByMonth'),
                    };
                })
                .filter((group) => group.hasOtherRows || group.hasFobRows);
            return {
                area,
                operators: operatorGroups,
                soValues: periodKeys.map((_, index) => total(areaRows.map((customer) => customer.soByMonth[index]))),
                actualValues: periodKeys.map((_, index) => total(areaRows.map((customer) => customer.actualByMonth[index]))),
            };
        })
        .filter((group) => group.operators.length), [filteredCustomers, periodKeys, region, operator]);

    const totals = useMemo(() => ({
        so: total(filteredCustomers.map((customer) => customer.so)),
        actual: total(filteredCustomers.map((customer) => customer.actual)),
    }), [filteredCustomers]);

    const achievement = totals.so ? totals.actual / totals.so * 100 : 0;
    const variance = totals.actual - totals.so;
    const topCustomers = useMemo(() => [...filteredCustomers]
        .sort((left, right) => right.actual - left.actual)
        .slice(0, 10), [filteredCustomers]);
    const maxTopActual = Math.max(1, ...topCustomers.map((customer) => customer.actual));

    return (
        <div className="yearly-page">
            {error && <div className="notice bad" role="alert">{error}</div>}
            {!error && !loading && records.length === 0 && (
                <div className="notice" role="status">
                    Belum ada data penjualan pada periode ini. Impor data melalui halaman Harian terlebih dahulu.
                </div>
            )}

            <section className="yearly-kpis" aria-label="Ringkasan tahunan">
                <article className="yearly-kpi">
                    <span className="yearly-kpi-icon blue" aria-hidden="true">▤</span>
                    <div><small>REALISASI PENJUALAN</small><strong>{formatNumber(totals.actual)} Sm³</strong><span>Periode terpilih</span></div>
                </article>
                <article className="yearly-kpi">
                    <span className="yearly-kpi-icon green" aria-hidden="true">◎</span>
                    <div><small>TARGET SO</small><strong>{formatNumber(totals.so)} Sm³</strong><span>Target dari data SO</span></div>
                </article>
                <article className={`yearly-kpi ${variance < 0 ? 'is-negative' : ''}`}>
                    <span className="yearly-kpi-icon orange" aria-hidden="true">↗</span>
                    <div><small>VARIANCE / SELISIH</small><strong>{variance < 0 ? '−' : '+'}{formatNumber(Math.abs(variance))} Sm³</strong><span>Actual dikurangi SO</span></div>
                </article>
                <article className="yearly-kpi">
                    <span className="yearly-kpi-icon teal" aria-hidden="true">%</span>
                    <div><small>SO FULFILLMENT</small><strong>{formatPercent(achievement)}</strong><span>Actual ÷ SO</span></div>
                </article>
            </section>

            <section className="yearly-content">
                <article className="yearly-panel yearly-top-panel">
                    <div className="yearly-panel-heading">
                        <h2>TOP 10 CUSTOMER TERBESAR (PERIODE)</h2>
                    </div>
                    <div className="yearly-table-wrap">
                        <table className="yearly-table">
                            <thead><tr><th>No.</th><th>Customer</th><th>Actual (Sm³)</th><th>Share %</th><th>SO Ful %</th></tr></thead>
                            <tbody>
                                {topCustomers.map((customer, index) => (
                                    <tr key={customer.key}>
                                        <td>{index + 1}</td>
                                        <td>{customer.customer}</td>
                                        <td>{formatNumber(customer.actual)}</td>
                                        <td>{formatPercent(totals.actual ? customer.actual / totals.actual * 100 : 0)}</td>
                                        <td>{formatPercent(customer.so ? customer.actual / customer.so * 100 : 0)}</td>
                                    </tr>
                                ))}
                                {topCustomers.length === 0 && (
                                    <tr><td colSpan="5">{loading ? 'Memuat data...' : 'Tidak ada data untuk filter yang dipilih.'}</td></tr>
                                )}
                                {topCustomers.length > 0 && (
                                    <tr className="yearly-subtotal">
                                        <td colSpan="2">Subtotal Top 10</td>
                                        <td>{formatNumber(total(topCustomers.map((customer) => customer.actual)))}</td>
                                        <td>{formatPercent(totals.actual ? total(topCustomers.map((customer) => customer.actual)) / totals.actual * 100 : 0)}</td>
                                        <td>{formatPercent(total(topCustomers.map((customer) => customer.so)) ? total(topCustomers.map((customer) => customer.actual)) / total(topCustomers.map((customer) => customer.so)) * 100 : 0)}</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </article>

                <article className="yearly-panel yearly-chart-panel">
                    <div className="yearly-panel-heading"><h2>Volume Penjualan Top 10 Customer (Sm³)</h2></div>
                    <div className="yearly-bars" role="img" aria-label="Grafik actual penjualan untuk sepuluh customer terbesar">
                        {topCustomers.length === 0 && <p className="yearly-empty">{loading ? 'Memuat data...' : 'Belum ada data untuk ditampilkan.'}</p>}
                        {topCustomers.map((customer) => (
                            <div className="yearly-bar-row" key={customer.key} title={`${customer.customer}: ${formatNumber(customer.actual)} Sm³`}>
                                <span>{customer.customer}</span>
                                <div><i style={{ width: `${customer.actual / maxTopActual * 100}%` }} /></div>
                                <b>{formatNumber(customer.actual)}</b>
                            </div>
                        ))}
                    </div>
                    {topCustomers.length > 0 && <div className="yearly-chart-axis"><span>0</span><span>{formatNumber(maxTopActual / 2)}</span><span>{formatNumber(maxTopActual)}</span></div>}
                </article>

                <aside className="yearly-panel yearly-filters">
                    <h2><span aria-hidden="true">▽</span> FILTERS / SLICERS</h2>
                    <label>Wilayah
                        <select value={region} onChange={(event) => setRegion(event.target.value)}>
                            {['Semua Wilayah', ...regions].map((value) => <option key={value} value={value}>{value}</option>)}
                        </select>
                    </label>
                    <label>MS
                        <select value={operator} onChange={(event) => setOperator(event.target.value)}>
                            {['Semua MS', ...operators].map((value) => <option key={value} value={value}>{value}</option>)}
                        </select>
                    </label>
                    <p className="yearly-filter-note">Ringkasan menghitung seluruh transaksi dalam rentang tanggal terpilih.</p>
                </aside>
            </section>

            <section className="yearly-panel yearly-recap monthly-table-card">
                <div className="monthly-table-title">
                    <h2>Rekapitulasi Data Bulanan</h2>
                </div>

                <div className="monthly-table-scroll">
                    <table className="monthly-table">
                        <colgroup>
                            <col style={{ width: 110 }} />
                            <col style={{ width: 90 }} />
                            {periodKeys.map((key) => (
                                <React.Fragment key={key}>
                                    <col style={{ width: 80 }} />
                                    <col style={{ width: 80 }} />
                                </React.Fragment>
                            ))}
                            <col style={{ width: 110 }} />
                            <col style={{ width: 110 }} />
                        </colgroup>
                        <thead>
                            <tr>
                                <th className="yearly-fixed-left yearly-fixed-region">Wilayah</th>
                                <th className="yearly-fixed-left yearly-fixed-label">MS / FOB</th>
                                {periodLabels.map((label) => (
                                    <th className="monthly-month-heading" key={label} colSpan={2}>{label}</th>
                                ))}
                                <th className="yearly-fixed-right yearly-fixed-total-so">Total SO</th>
                                <th className="yearly-fixed-right yearly-fixed-total-actual">Total Actual</th>
                            </tr>
                            <tr>
                                <th className="yearly-fixed-left yearly-fixed-region yearly-header-spacer" aria-hidden="true" />
                                <th className="yearly-fixed-left yearly-fixed-label yearly-header-spacer" aria-hidden="true" />
                                {periodLabels.map((label) => (
                                    <React.Fragment key={label}>
                                        <th className="monthly-month-start">SO</th>
                                        <th className="monthly-month-end">Actual</th>
                                    </React.Fragment>
                                ))}
                                <th className="yearly-fixed-right yearly-fixed-total-so yearly-header-spacer" aria-hidden="true" />
                                <th className="yearly-fixed-right yearly-fixed-total-actual yearly-header-spacer" aria-hidden="true" />
                            </tr>
                        </thead>
                        <tbody>
                            {monthlyGroups.map((group) => (
                                <React.Fragment key={group.area}>
                                    <tr className="monthly-region-row">
                                        <td className="yearly-fixed-left" colSpan={2}>⌄ &nbsp; {group.area}</td>
                                        <td colSpan={periodKeys.length * 2} />
                                        <td className="yearly-fixed-right yearly-fixed-total-so" />
                                        <td className="yearly-fixed-right yearly-fixed-total-actual" />
                                    </tr>
                                    {group.operators.map((operatorGroup) => (
                                        <React.Fragment key={operatorGroup.name}>
                                            <tr className="monthly-operator-row">
                                                <td className="yearly-fixed-left" colSpan={2}>{operatorGroup.name}</td>
                                                <td colSpan={periodKeys.length * 2} />
                                                <td className="yearly-fixed-right yearly-fixed-total-so" />
                                                <td className="yearly-fixed-right yearly-fixed-total-actual" />
                                            </tr>
                                            {operatorGroup.hasOtherRows && (
                                                <tr>
                                                    <td className="yearly-fixed-left" />
                                                    <td className="yearly-fixed-left yearly-fixed-label yearly-other-label">Pelanggan lainnya (non-FOB)</td>
                                                    {periodKeys.map((_, index) => (
                                                        <React.Fragment key={index}>
                                                            <td className="monthly-month-start">{formatNumber(operatorGroup.otherSoValues[index])}</td>
                                                            <td className="monthly-month-end">{formatNumber(operatorGroup.otherActualValues[index])}</td>
                                                        </React.Fragment>
                                                    ))}
                                                    <td className="yearly-fixed-right yearly-fixed-total-so">{formatNumber(total(operatorGroup.otherSoValues))}</td>
                                                    <td className="yearly-fixed-right yearly-fixed-total-actual">{formatNumber(total(operatorGroup.otherActualValues))}</td>
                                                </tr>
                                            )}
                                            {operatorGroup.hasFobRows && (
                                                <tr className="monthly-fob-row">
                                                    <td className="yearly-fixed-left" />
                                                    <td className="yearly-fixed-left yearly-fixed-label">Total FOB</td>
                                                    {periodKeys.map((_, index) => (
                                                        <React.Fragment key={index}>
                                                            <td className="monthly-month-start">{formatNumber(operatorGroup.fobSoValues[index])}</td>
                                                            <td className="monthly-month-end">{formatNumber(operatorGroup.fobActualValues[index])}</td>
                                                        </React.Fragment>
                                                    ))}
                                                    <td className="yearly-fixed-right yearly-fixed-total-so">{formatNumber(total(operatorGroup.fobSoValues))}</td>
                                                    <td className="yearly-fixed-right yearly-fixed-total-actual">{formatNumber(total(operatorGroup.fobActualValues))}</td>
                                                </tr>
                                            )}
                                        </React.Fragment>
                                    ))}
                                    <tr className="monthly-subtotal">
                                        <td className="yearly-fixed-left" colSpan={2}>Total {group.area.replace('JAWA ', 'Jawa ')}</td>
                                        {periodKeys.map((_, index) => (
                                            <React.Fragment key={index}>
                                                <td className="monthly-month-start">{formatNumber(group.soValues[index])}</td>
                                                <td className="monthly-month-end">{formatNumber(group.actualValues[index])}</td>
                                            </React.Fragment>
                                        ))}
                                        <td className="yearly-fixed-right yearly-fixed-total-so">{formatNumber(total(group.soValues))}</td>
                                        <td className="yearly-fixed-right yearly-fixed-total-actual">{formatNumber(total(group.actualValues))}</td>
                                    </tr>
                                </React.Fragment>
                            ))}
                            {filteredCustomers.length === 0 && !loading && (
                                <tr>
                                    <td className="yearly-fixed-left" colSpan={2}>Tidak ada data untuk filter yang dipilih.</td>
                                    <td colSpan={periodKeys.length * 2} />
                                    <td className="yearly-fixed-right yearly-fixed-total-so" />
                                    <td className="yearly-fixed-right yearly-fixed-total-actual" />
                                </tr>
                            )}
                            {filteredCustomers.length > 0 && (
                                <tr className="monthly-grand-total">
                                    <td className="yearly-fixed-left" colSpan={2}>TOTAL</td>
                                    {periodKeys.map((_, index) => (
                                        <React.Fragment key={index}>
                                            <td className="monthly-month-start">{formatNumber(total(filteredCustomers.map((customer) => customer.soByMonth[index])))}</td>
                                            <td className="monthly-month-end">{formatNumber(total(filteredCustomers.map((customer) => customer.actualByMonth[index])))}</td>
                                        </React.Fragment>
                                    ))}
                                    <td className="yearly-fixed-right yearly-fixed-total-so">{formatNumber(total(filteredCustomers.map((customer) => customer.so)))}</td>
                                    <td className="yearly-fixed-right yearly-fixed-total-actual">{formatNumber(total(filteredCustomers.map((customer) => customer.actual)))}</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}
