import React, { useLayoutEffect, useRef, useState } from 'react';

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT', 'OFF'];
const maxTableHeight = 480;
const formatNumber = (value) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(Number(value ?? 0));
const formatPercent = (value) => `${Number(value ?? 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })}%`;
const formatDate = (value) => value
    ? new Date(`${value}T00:00:00`).toLocaleDateString('id-ID', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' })
    : '';

function SummaryTable({ title, totals, target, loading = false, error = '' }) {
    const so = Number(totals?.so ?? 0);
    const actual = Number(totals?.actual ?? 0);
    const diff = Number(totals?.diff ?? actual - so);
    const percent = so ? diff / so * 100 : null;
    const targetDiff = target == null ? null : actual - Number(target);
    const targetPercent = targetDiff == null || !Number(target) ? null : targetDiff / Number(target) * 100;

    return (
        <section className="daily-summary-block">
            <h3>{title}</h3>
            {error ? <p className="daily-summary-message bad">{error}</p> : loading ? (
                <p className="daily-summary-message">Memuat ringkasan...</p>
            ) : (
                <div className="daily-summary-table-wrap">
                    <table className={`daily-summary-table${target !== undefined ? ' has-target' : ''}`}>
                        <thead><tr>{target !== undefined && <th>Target</th>}<th>SO</th><th>Actual</th><th>{target !== undefined ? 'Selisih SO/Act' : 'Selisih'}</th>{target !== undefined ? <th>Selisih Target</th> : <th>Persentase</th>}</tr></thead>
                        <tbody><tr>
                            {target !== undefined && <td>{target == null ? '—' : formatNumber(target)}</td>}
                            <td>{formatNumber(so)}</td>
                            <td>{formatNumber(actual)}</td>
                            <td className={diff >= 0 ? 'diff-pos' : 'diff-neg'}>{diff > 0 ? '+' : ''}{formatNumber(diff)}</td>
                            {target !== undefined
                                ? <td className={targetDiff == null ? '' : targetDiff >= 0 ? 'diff-pos' : 'diff-neg'}>{targetDiff == null ? '—' : `${targetDiff > 0 ? '+' : ''}${formatNumber(targetDiff)}`}</td>
                                : <td>{percent == null ? '—' : formatPercent(percent)}</td>}
                        </tr>
                        {target !== undefined && <tr className="summary-percent-row">
                            <td colSpan="3" />
                            <td>{percent == null ? '—' : formatPercent(percent)}</td>
                            <td>{targetPercent == null ? '—' : formatPercent(targetPercent)}</td>
                        </tr>}
                        </tbody>
                    </table>
                </div>
            )}
        </section>
    );
}

function getCustomerGroup(row) {
    if (row.manual_fob) return 'fob';
    const customer = row.customer;
    const name = customer.toLocaleUpperCase('id-ID');
    if (name.includes('KSO')) return 'kso';
    if (name.includes('FOB')) return 'fob';
    return 'direct';
}

function sumRows(rows) {
    return rows.reduce((totals, row) => ({
        so: totals.so + Number(row.so ?? 0),
        actual: totals.actual + Number(row.actual ?? 0),
    }), { so: 0, actual: 0 });
}

function OperatorCard({
    operator,
    rows,
    tableHeight,
    tableRef,
    onEditManualFob,
    onDeleteManualFob,
}) {
    const groups = [
        { key: 'direct', label: 'Direct Customer' },
        { key: 'kso', label: 'KSO Customer' },
        { key: 'fob', label: 'FOB Customer' },
    ]
        .map((group) => ({
            ...group,
            rows: rows
                .filter((row) => getCustomerGroup(row) === group.key)
                .sort((a, b) => Number(a.diff ?? 0) - Number(b.diff ?? 0)
                    || a.customer.localeCompare(b.customer, 'id')),
        }))
        .filter((group) => group.rows.length > 0);
    const totals = sumRows(rows);

    return (
        <article className={`operator-card ${operator.toLowerCase()}`}>
            <div className="operator-heading"><span className="operator-icon">♟</span><b>{operator}</b><small>{rows.length} Customer</small></div>
            <div className={`table-wrap ${operator.toLowerCase()}-table-wrap`} ref={tableRef} style={operator === 'SETU' || operator === 'KHT' ? undefined : { maxHeight: `${tableHeight}px` }}><table className="operator-table">
                <thead><tr><th>Customer / Kelompok</th><th>SO</th><th>Actual</th><th>Diff</th></tr></thead>
                <tbody>
                    {groups.length === 0 ? <tr><td colSpan="4" className="empty-row">Tidak ada data pada tanggal ini</td></tr> : groups.map((group) => {
                        const groupTotals = sumRows(group.rows);
                        const groupDiff = groupTotals.actual - groupTotals.so;
                        return (
                            <React.Fragment key={group.key}>
                                <tr className="operator-group-row">
                                    <th>{group.label} ({group.rows.length})</th>
                                    <td>{formatNumber(groupTotals.so)}</td>
                                    <td>{formatNumber(groupTotals.actual)}</td>
                                    <td className={groupDiff >= 0 ? 'diff-pos' : 'diff-neg'}>{groupDiff > 0 ? '+' : ''}{formatNumber(groupDiff)}</td>
                                </tr>
                                {group.rows.map((row, index) => (
                                    <tr key={`${group.key}-${row.customer}-${index}`}>
                                        <td title={row.customer}>
                                            {row.customer}
                                            {row.manual_fob && (onEditManualFob || onDeleteManualFob) && <span className="manual-fob-row-actions">
                                                {onEditManualFob && <button type="button" onClick={() => onEditManualFob(row, operator)}>Edit</button>}
                                                {onDeleteManualFob && <button type="button" onClick={() => onDeleteManualFob(row)}>Hapus</button>}
                                            </span>}
                                        </td><td>{formatNumber(row.so)}</td><td>{formatNumber(row.actual)}</td>
                                        <td className={row.diff >= 0 ? 'diff-pos' : 'diff-neg'}>{row.diff > 0 ? '+' : ''}{formatNumber(row.diff)}</td>
                                    </tr>
                                ))}
                            </React.Fragment>
                        );
                    })}
                </tbody>
                <tfoot><tr className="operator-total-row">
                    <th>Total {operator}</th><td>{formatNumber(totals.so)}</td><td>{formatNumber(totals.actual)}</td>
                    <td className={totals.actual - totals.so >= 0 ? 'diff-pos' : 'diff-neg'}>{totals.actual - totals.so > 0 ? '+' : ''}{formatNumber(totals.actual - totals.so)}</td>
                </tr></tfoot>
            </table></div>
        </article>
    );
}

export default function OperatorTables({
    data = {},
    dailySummary,
    monthlySummary,
    summaryMonth,
    summaryError = '',
    summaryLoading = false,
    onEditManualFob,
    onDeleteManualFob,
}) {
    const khtTableRef = useRef(null);
    const [tableHeight, setTableHeight] = useState(maxTableHeight);

    useLayoutEffect(() => {
        const table = khtTableRef.current?.querySelector('table');
        if (!table) {
            setTableHeight(maxTableHeight);
            return undefined;
        }

        const updateHeight = () => {
            setTableHeight(Math.min(maxTableHeight, Math.ceil(table.getBoundingClientRect().height)));
        };

        updateHeight();
        const observer = new ResizeObserver(updateHeight);
        observer.observe(table);
        return () => observer.disconnect();
    }, [data]);

    return (
        <>
            <section className="operator-grid" id="detail-harian">
                <div className="operator-column">
                    <OperatorCard
                        operator="SETU"
                        rows={data.SETU ?? []}
                        tableHeight={tableHeight}
                        onEditManualFob={onEditManualFob}
                        onDeleteManualFob={onDeleteManualFob}
                    />
                </div>
                <div className="operator-column">
                    <OperatorCard
                        operator="KHT"
                        rows={data.KHT ?? []}
                        tableHeight={tableHeight}
                        tableRef={khtTableRef}
                        onEditManualFob={onEditManualFob}
                        onDeleteManualFob={onDeleteManualFob}
                    />
                    <article className="operator-summary-card daily-summary-card">
                        <SummaryTable
                            title={`Penyerapan Harian ${formatDate(dailySummary?.report_date)}`}
                            totals={{ so: dailySummary?.total_so, actual: dailySummary?.total_actual, diff: dailySummary?.diff }}
                        />
                        <SummaryTable
                            title={`Summary ${summaryMonth ? new Date(`${summaryMonth}-01T00:00:00`).toLocaleDateString('id-ID', { month: 'long', year: 'numeric' }) : 'Bulanan'}`}
                            totals={monthlySummary}
                            target={monthlySummary?.manual_so}
                            loading={summaryLoading}
                            error={summaryError}
                        />
                    </article>
                    <OperatorCard
                        operator="OFF"
                        rows={data.OFF ?? []}
                        tableHeight={tableHeight}
                        onEditManualFob={onEditManualFob}
                        onDeleteManualFob={onDeleteManualFob}
                    />
                </div>
                <div className="operator-column">
                    <OperatorCard
                        operator="BLORA"
                        rows={data.BLORA ?? []}
                        tableHeight={tableHeight}
                        onEditManualFob={onEditManualFob}
                        onDeleteManualFob={onDeleteManualFob}
                    />
                </div>
                <div className="operator-column">
                    <OperatorCard
                        operator="WUNUT"
                        rows={data.WUNUT ?? []}
                        tableHeight={tableHeight}
                        onEditManualFob={onEditManualFob}
                        onDeleteManualFob={onDeleteManualFob}
                    />
                </div>
            </section>
        </>
    );
}