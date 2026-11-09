import React, { useEffect, useRef, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from 'chart.js';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT'];
const excludedAveragePriceCustomerKeys = new Set(['pentawira', 'pentawiraren']);
const regions = ['JAWA BARAT', 'JAWA TENGAH', 'JAWA TIMUR', 'JAWA TENGAH DAN TIMUR'];
const isExcludedAveragePriceCustomer = (value) => (
    normalizeCustomerOrder(value).startsWith('pentawira')
);
const aggregateDuplicateCustomers = (rows) => {
    const groups = new Map();
    rows.forEach((row) => {
        const key = normalizeCustomerOrder(row.customer);
        const group = groups.get(key);
        if (group) {
            group.rows.push(row);
        } else {
            groups.set(key, { rows: [row] });
        }
    });
    return Array.from(groups.values(), ({ rows: customerRows }) => {
        const primaryRow = [...customerRows].sort((left, right) => (
            Number(right.sm3 > 0) - Number(left.sm3 > 0)
            || Number(right.has_valid_price) - Number(left.has_valid_price)
        ))[0];
        const sm3 = customerRows.reduce((total, row) => total + row.sm3, 0);
        const mmbtu = customerRows.reduce((total, row) => total + row.volume_mmbtu, 0);
        const usd = customerRows.reduce((total, row) => total + row.total_usd, 0);
        const rupiah = customerRows.reduce((total, row) => total + row.rupiah, 0);
        const pricedRows = customerRows.filter((row) => row.has_valid_price);
        const pricedSm3 = pricedRows.reduce((total, row) => total + row.sm3, 0);
        const pricedMmbtu = pricedRows.reduce((total, row) => total + row.volume_mmbtu, 0);
        const pricedUsd = pricedRows.reduce((total, row) => total + row.total_usd, 0);
        const pricedRupiah = pricedRows.reduce((total, row) => total + row.rupiah, 0);
        const samePriceUnit = customerRows.every(
            (row) => row.price_unit === primaryRow.price_unit,
        );
        const price = primaryRow.price_unit === 'IDR_SM3'
            ? (pricedSm3 > 0
                ? pricedRupiah / pricedSm3
                : Number(primaryRow.price_rp_per_sm3 || 0))
            : (pricedMmbtu > 0
                ? pricedUsd / pricedMmbtu
                : Number(primaryRow.price_usd_per_mmbtu || 0));
        return {
            ...primaryRow,
            sm3,
            volume_mmbtu: mmbtu,
            total_usd: usd,
            rupiah,
            has_valid_price: pricedRows.length > 0,
            price_usd_per_mmbtu: samePriceUnit && primaryRow.price_unit === 'USD_MMBTU'
                ? price
                : primaryRow.price_usd_per_mmbtu,
            price_rp_per_sm3: samePriceUnit && primaryRow.price_unit === 'IDR_SM3'
                ? price
                : primaryRow.price_rp_per_sm3,
            include_in_summary: customerRows.every(
                (row) => row.include_in_summary !== false,
            ),
            source_rows: customerRows,
        };
    });
};
const pdfCustomerNames = [
    'PT Cipta Lestari Idea Nusa', 'PT Mitra Kaya Galvanize', 'PT Optima Adhi Jaya',
    'SHB', 'GTL', 'TWK', 'BEM', 'TOMIMOTO', 'NIAGA GARAM', 'PCI MENGGER',
    'Alia Digital', 'BI Surcharge', 'BI', 'STM', 'SMA', 'IP', 'KARISMA', 'KTN',
    'Honchuan', 'NNI', 'GFR Surcharge', 'GF RANCAEKEK', 'BYC', 'HLI Green Power',
    'Dic Grapichs', 'KSN Maja', 'KSN Ranca', 'ATEJA', 'ABC Kogen', 'UMI', 'Ceres',
    'PCI 84 Surcharge', 'PCI 84', 'INDOFOOD NSF', 'Asahimas Surcharge', 'Asahimas',
    'FJI / SBI', 'ALTINEX /Masami', 'Winglok / EBM', 'KGM / RRS', 'CISF / RRS',
    'PUJ - Lubricant', 'Tong Tji / GAS', 'INDONEPTUNE /AAE', 'Calbee/ACE', 'CV PA',
    'GF KULIT', 'RB', 'GF ATOM', 'HSK / GAS', 'Surya Pamenang (Global)',
    'Surya Pamenang (JES)', 'Jiuqi Tecnology Konjac', 'Djarum', 'Green Pulse',
    'Concord Industry',
];
const comparisonAreas = [
    { key: 'JAWA BARAT', label: 'Jawa Barat', regions: ['JAWA BARAT'] },
    { key: 'JAWA TENGAH', label: 'Jawa Tengah', regions: ['JAWA TENGAH'] },
    { key: 'JAWA TIMUR', label: 'Jawa Timur', regions: ['JAWA TIMUR'] },
    { key: 'JAWA_TENGAH_DAN_TIMUR', label: 'Jawa Tengah dan Timur', regions: ['JAWA TENGAH DAN TIMUR'] },
    { key: 'ALL_EXCEPT_JATIM', label: 'All Area', regions: [] },
];
const templateCustomerOrder = [
    'CLIN', 'MKG', 'OPTIMA', 'SHB', 'GTL', 'TWK', 'BEM', 'TOMIMOTO',
    'NIAGA GARAM', 'PCI MENGGER', 'Alia Digital', 'GreenPulse',
    'BI Surcharge', 'BI', 'STM', 'SMA', 'IP', 'KARISMA', 'KTN', 'Honchuan',
    'NNI', 'GFR Surcharge', 'GF RANCAEKEK', 'BYC', 'HLI Green Power',
    'Dic Grapichs', 'KSN Maja', 'ATEJA', 'ABC Kogen', 'KSN Ranca',
    'UMI', 'Ceres', 'PCI 84 Surcharge', 'PCI 84', 'INDOFOOD NSF',
    'Asahimas Surcharge', 'Asahimas', 'Concord',
    'FJI / SBI', 'ALTINEX /Masami', 'Winglok / EBM', 'PSD / WIRA',
    'ABP / SBI', 'KGM / RRS', 'BDP / LEMB', 'Toyobo (KSO Ineko)',
    'Citymall/Wira', 'CISF / RRS', 'PUJ - Lubricant', 'Tong Tji / GAS',
    'Torabika HF', 'Torabika IC', 'SWS / ACE', 'Kimia Farma / IMA',
    'INDONEPTUNE /AAE', 'HSK / GAS', 'Surya Pamenang (Global)',
    'Torabika Cikupa/Ekajaya', 'Calbee/ACE',
    'CV PA', 'GF KULIT', 'RPI', 'RB', 'GF ATOM', 'HSK / GAS',
    'Surya Pamenang (JES)', 'JIUQI', 'Surya Pamenang (Global)',
    'Djarum', 'Surya Pamenang (Global)',
];
const customerOrderAliases = {
    ptciptalestariideanusa: 'CLIN',
    ptmitrakayagalvanize: 'MKG',
    ptoptimadhijaya: 'OPTIMA',
    adp: 'Alia Digital',
    ami: 'ATEJA',
    altksomasami: 'altinex /masami',
    calbeeksobmi: 'Calbee/ACE',
    cisfksorrs: 'cisf / rrs',
    dic: 'dic grapichs',
    gfranca: 'gf rancaekek',
    gfrsurcharge: 'GFR Surcharge',
    gfatom: 'GF ATOM',
    gfkulit: 'GF KULIT',
    hci: 'Honchuan',
    hli: 'HLI Green Power',
    idpksoaae: 'indoneptune /aae',
    hskksogas: 'hsk / gas',
    indofood: 'INDOFOOD NSF',
    ka: 'KARISMA',
    kgmksorrs: 'KGM / RRS',
    niagagaram: 'NIAGA GARAM',
    pcimengger: 'PCI MENGGER',
    pa: 'CV PA',
    spglobal: 'Surya Pamenang (Global)',
    spksojes: 'Surya Pamenang (JES)',
    greenpulse: 'GreenPulse',
    jiuqi: 'JIUQI',
    djarum: 'Djarum',
    kimiafarmaksoineko: 'Kimia Farma / IMA',
    ksn: 'KSN Maja',
    oaj: 'OPTIMA',
    fjiksosalmah: 'FJI / SBI',
    tongjiksogas: 'Tong Tji / GAS',
    winglokksoebm: 'winglok / ebm',
};
const januaryCustomerAliases = {
    adp: 'Alia Digital',
    calbeeksobmi: 'Calbee/ACE',
    fjiksosalmah: 'FJI / SBI',
    gfatom: 'GF ATOM',
    gfkulit: 'GF KULIT',
    gfranca: 'GF RANCAEKEK',
    gfrsurcharge: 'GFR Surcharge',
    hli: 'HLI Green Power',
    hskksogas: 'HSK / GAS',
    idpksoaae: 'INDONEPTUNE /AAE',
    indofood: 'INDOFOOD NSF',
    ka: 'KARISMA',
    kgmksorrs: 'KGM / RRS',
    niagagaram: 'NIAGA GARAM',
    pcimengger: 'PCI MENGGER',
    pa: 'CV PA',
    spglobal: 'Surya Pamenang (Global)',
    spksojes: 'Surya Pamenang (JES)',
    tongjiksogas: 'Tong Tji / GAS',
};
const normalizeCustomerOrder = (value) => String(value ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');
const averagePriceCustomerIdentity = (value, month) => {
    const key = normalizeCustomerOrder(value);
    const alias = (month === '2026-01' && januaryCustomerAliases[key])
        || customerOrderAliases[key];
    return normalizeCustomerOrder(alias || value);
};
const customerOrderIndex = new Map();
templateCustomerOrder.forEach((customer, index) => {
    const key = normalizeCustomerOrder(customer);
    if (!customerOrderIndex.has(key)) customerOrderIndex.set(key, index);
});
const workbookCustomerGroups = [
    {
        label: 'Customer <50.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['CLIN', 'MKG', 'OPTIMA', 'SHB', 'GTL', 'TWK', 'BEM', 'TOMIMOTO', 'NIAGA GARAM', 'PCI MENGGER', 'Alia Digital'],
            'JAWA TENGAH': ['CV PA', 'GF KULIT', 'RPI'],
            'JAWA TIMUR': ['Djarum'],
        },
    },
    {
        label: 'Customer 50.001 - 100.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['BI Surcharge', 'BI', 'STM', 'SMA', 'IP', 'KARISMA', 'KTN', 'Honchuan'],
            'JAWA TENGAH': ['RB', 'GF ATOM'],
            'JAWA TIMUR': ['Surya Pamenang (Global)'],
        },
    },
    {
        label: 'Customer 100.001 - 200.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['NNI', 'GFR Surcharge', 'GF RANCAEKEK', 'BYC', 'HLI Green Power', 'Dic Grapichs', 'KSN Maja', 'ATEJA', 'ABC Kogen'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'Customer >200.001 Sm³/bln',
        regions: {
            'JAWA BARAT': ['UMI', 'Ceres', 'PCI 84 Surcharge', 'PCI 84', 'INDOFOOD NSF', 'Asahimas Surcharge', 'Asahimas'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'KSO · Customer <50.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['FJI / SBI', 'ALTINEX /Masami', 'Winglok / EBM', 'PSD / WIRA', 'ABP / SBI', 'KGM / RRS', 'BDP / LEMB', 'Toyobo (KSO Ineko)', 'Citymall/Wira'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'KSO · Customer 50.001 - 100.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['CISF / RRS', 'PUJ - Lubricant', 'Tong Tji / GAS', 'Torabika HF', 'Torabika IC', 'SWS / ACE'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'KSO · Customer 100.001 - 200.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['INDONEPTUNE /AAE', 'HSK / GAS', 'Surya Pamenang (Global)'],
            'JAWA TENGAH': ['HSK / GAS', 'Surya Pamenang (Global)'],
        },
    },
    {
        label: 'KSO · Customer >200.001 Sm³/bln',
        regions: {
            'JAWA BARAT': ['Torabika Cikupa/Ekajaya', 'Calbee/ACE', 'Surya Pamenang (JES)'],
            'JAWA TENGAH': ['Surya Pamenang (JES)'],
            'JAWA TIMUR': [],
        },
    },
];
const workbookCustomerGroupByRegion = new Map();
const workbookRegionsByCustomer = new Map();
const januaryCentralEastCustomers = new Set(
    workbookCustomerGroups.flatMap((group) => [
        ...(group.regions['JAWA TENGAH'] || []),
        ...(group.regions['JAWA TIMUR'] || []),
    ]).map(normalizeCustomerOrder),
);
workbookCustomerGroups.forEach((group, groupIndex) => {
    Object.entries(group.regions).forEach(([region, customers]) => {
        if (!workbookCustomerGroupByRegion.has(region)) {
            workbookCustomerGroupByRegion.set(region, new Map());
        }
        customers.forEach((customer) => {
            const customerKey = normalizeCustomerOrder(customer);
            workbookCustomerGroupByRegion.get(region).set(customerKey, groupIndex);
            if (!workbookRegionsByCustomer.has(customerKey)) {
                workbookRegionsByCustomer.set(customerKey, new Set());
            }
            workbookRegionsByCustomer.get(customerKey).add(region);
        });
    });
});
function workbookRegionForCustomer(customer) {
    const regionsForCustomer = workbookRegionsByCustomer.get(normalizeCustomerOrder(customer));
    return regionsForCustomer?.size === 1 ? [...regionsForCustomer][0] : '';
}
function workbookAreaForCustomer(region, customer, month) {
    if (
        month === '2026-01'
        && januaryCentralEastCustomers.has(normalizeCustomerOrder(customer))
    ) {
        return 'JAWA TENGAH DAN TIMUR';
    }
    const normalizedRegion = String(region ?? '').trim().toUpperCase()
        || workbookRegionForCustomer(customer);
    if (
        month >= '2026-01'
        && month < '2026-08'
        && ['JAWA TENGAH', 'JAWA TIMUR', 'JAWA TENGAH DAN TIMUR'].includes(normalizedRegion)
    ) {
        return 'JAWA TENGAH DAN TIMUR';
    }
    return normalizedRegion || 'WILAYAH BELUM DIPETAKAN';
}
const laterWorkbookCustomerGroups = [
    { region: 'JAWA BARAT', customer: 'greenpulse', fromMonth: '2026-08', groupIndex: 0 },
    { region: 'JAWA BARAT', customer: 'ksnranca', fromMonth: '2026-06', groupIndex: 2 },
    { region: 'JAWA BARAT', customer: 'concord', fromMonth: '2026-09', groupIndex: 3 },
    { region: 'JAWA BARAT', customer: 'kimiafarmaima', fromMonth: '2026-09', groupIndex: 5 },
    { region: 'JAWA TENGAH', customer: 'jiuqi', fromMonth: '2026-04', groupIndex: 6 },
];
function workbookGroupForCustomer(row, month) {
    const region = workbookAreaForCustomer(row.region, row.customer, month);
    const customerKey = normalizeCustomerOrder(row.customer);
    if (region === 'JAWA TENGAH DAN TIMUR') {
        const groupIndex = {
            cvpa: 0,
            gfkulit: 0,
            rpi: 0,
            rb: 1,
            gfatom: 1,
            hskksogas: 6,
            jiuqi: 6,
        }[customerKey];
        if (groupIndex != null) {
            return { index: groupIndex, label: workbookCustomerGroups[groupIndex].label };
        }
        if (['suryapamenangglobal', 'suryapamenangjes'].includes(customerKey)) {
            const isMayOrLater = month >= '2026-05';
            const groupIndex = customerKey === 'suryapamenangglobal'
                ? isMayOrLater ? 7 : 6
                : isMayOrLater ? 6 : 7;
            return { index: groupIndex, label: workbookCustomerGroups[groupIndex].label };
        }
    }
    const laterGroup = laterWorkbookCustomerGroups.find((group) =>
        group.region === region
        && group.customer === customerKey
        && month >= group.fromMonth);
    if (laterGroup) {
        return { index: laterGroup.groupIndex, label: workbookCustomerGroups[laterGroup.groupIndex].label };
    }
    if (region === 'JAWA TENGAH' && ['suryapamenangglobal', 'suryapamenangjes'].includes(customerKey)) {
        const isMayOrLater = month >= '2026-05';
        const groupIndex = customerKey === 'suryapamenangglobal'
            ? isMayOrLater ? 7 : 6
            : isMayOrLater ? 6 : 7;
        return { index: groupIndex, label: workbookCustomerGroups[groupIndex].label };
    }
    const groupIndex = workbookCustomerGroupByRegion.get(region)?.get(customerKey);
    return groupIndex == null
        ? { index: workbookCustomerGroups.length, label: 'Tidak tercantum di file pengguna' }
        : { index: groupIndex, label: workbookCustomerGroups[groupIndex].label };
}
const formatInteger = (value) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(Number(value ?? 0));
const formatDecimal = (value, digits = 2) => new Intl.NumberFormat('id-ID', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value ?? 0));
const formatDifference = (value) => value < 0
    ? `(${formatInteger(Math.abs(value))})`
    : formatInteger(value);
const parseExchangeRate = (value) => {
    const normalized = String(value ?? '').trim().replace(/[.\s]/g, '');
    if (!normalized) return 0;
    if (!/^\d+$/.test(normalized)) return null;
    const parsed = Number(normalized);
    return Number.isSafeInteger(parsed) ? parsed : null;
};

const comparisonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 9, boxHeight: 9, font: { size: 10 } } },
        tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatInteger(context.raw)} Rp/Sm³` } },
    },
    scales: {
        x: { grid: { display: false }, ticks: { font: { size: 9 } } },
        y: { beginAtZero: true, ticks: { font: { size: 9 }, callback: formatInteger } },
    },
};

function monthLabel(value) {
    if (!value) return 'Pilih bulan';
    const [year, month] = value.split('-').map(Number);
    return new Date(year, month - 1, 1).toLocaleDateString('id-ID', { month: 'long', year: 'numeric' });
}

export default function WeeklyAveragePricePage() {
    const { averagePriceMonth, rangeStartDate, canEdit } = useOutletContext();
    const canViewCustomerResults = canEdit;
    const selectedMonth = averagePriceMonth || rangeStartDate?.slice(0, 7) || '';
    const activeComparisonAreas = comparisonAreas
        .filter((area) => area.key !== 'JAWA_TENGAH_DAN_TIMUR'
            || (selectedMonth >= '2026-01' && selectedMonth < '2026-08'))
        .map((area) => {
        if (area.key !== 'ALL_EXCEPT_JATIM') return area;
        const excludesEastJava = selectedMonth >= '2026-09';
        return {
            ...area,
            label: excludesEastJava ? 'All Area (exc. Jatim)' : 'All Area',
        };
        });
    const [report, setReport] = useState({ rows: [], operator_factors: {}, exchange_rate: 0, targets: {}, totals: {} });
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [importingSheet, setImportingSheet] = useState(false);
    const [pendingSheetCustomers, setPendingSheetCustomers] = useState([]);
    const [sheetCustomerKeys, setSheetCustomerKeys] = useState([]);
    const [sheetSyncStatus, setSheetSyncStatus] = useState('');
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [exchangeRateInput, setExchangeRateInput] = useState('');
    const [exchangeRateInputError, setExchangeRateInputError] = useState(false);
    const [exchangeRateInputDirty, setExchangeRateInputDirty] = useState(false);
    const [selectedCustomerKey, setSelectedCustomerKey] = useState('');
    const [customerCatalog, setCustomerCatalog] = useState([]);
    const [customersLoading, setCustomersLoading] = useState(true);
    const sheetSyncInFlight = useRef(false);
    const [customerEntry, setCustomerEntry] = useState({
        customer: '',
        operator: '',
        region: '',
        price_unit: 'USD_MMBTU',
        price: '',
    });

    useEffect(() => {
        let active = true;
        api('/api/customers')
            .then((data) => {
                if (!Array.isArray(data) || data.some((customer) => (
                    typeof customer.customer_key !== 'string'
                    || typeof customer.customer_name !== 'string'
                    || typeof customer.operator !== 'string'
                ))) {
                    throw new Error('Format daftar customer dari server tidak valid.');
                }
                if (active) {
                    setCustomerCatalog(data.filter((customer) => (
                        !isExcludedAveragePriceCustomer(customer.customer_key)
                    )));
                }
            })
            .catch((requestError) => {
                if (active) setError(requestError.message);
            })
            .finally(() => {
                if (active) setCustomersLoading(false);
            });
        return () => { active = false; };
    }, []);

    useEffect(() => {
        if (!selectedMonth) return undefined;
        let active = true;
        setLoading(true);
        setError('');
        setSelectedCustomerKey('');
        setPendingSheetCustomers([]);
        setSheetCustomerKeys([]);
        setSheetSyncStatus('');
        setExchangeRateInput('');
        setExchangeRateInputError(false);
        setExchangeRateInputDirty(false);
        setCustomerEntry({
            customer: '',
            operator: '',
            region: '',
            price_unit: 'USD_MMBTU',
            price: '',
        });
        setReport({ rows: [], operator_factors: {}, exchange_rate: 0, targets: {}, totals: {} });
        api(`/api/monthly-average-price?month=${encodeURIComponent(selectedMonth)}`)
            .then((data) => {
                if (!active) return;
                setSelectedCustomerKey('');
                setReport({
                    ...data,
                    targets: Object.fromEntries(
                        Object.entries(data.targets || {}).map(([key, value]) => [
                            key,
                            value == null ? null : Math.round(Number(value)),
                        ]),
                    ),
                });
                setExchangeRateInput(data.exchange_rate
                    ? Number.isInteger(Number(data.exchange_rate))
                        ? formatInteger(data.exchange_rate)
                        : String(data.exchange_rate)
                    : '');
                setExchangeRateInputDirty(false);
            })
            .catch((requestError) => active && setError(requestError.message))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, [selectedMonth]);

    useEffect(() => {
        if (
            !selectedMonth
            || !canEdit
            || loading
            || customersLoading
            || report.source === 'workbook'
        ) return undefined;
        let active = true;
        const sync = () => {
            if (active) syncPricesFromSheet();
        };
        sync();
        const interval = window.setInterval(sync, 5 * 60 * 1000);
        return () => {
            active = false;
            window.clearInterval(interval);
        };
    }, [selectedMonth, canEdit, loading, customersLoading, report.source]);

    function selectCustomer(customerKey) {
        const row = report.rows.find((item) => item.customer_key === customerKey);
        const masterCustomer = customerCatalog.find((item) => item.customer_key === customerKey);
        const customer = row || masterCustomer;
        setSelectedCustomerKey(customer?.customer_key || '');
        setCustomerEntry({
            customer: row?.customer || masterCustomer?.customer_name || '',
            operator: row?.operator || masterCustomer?.operator || '',
            region: row?.region || '',
            price_unit: row?.price_unit || 'USD_MMBTU',
            price: row?.price_unit === 'IDR_SM3'
                ? row.price_rp_per_sm3 || ''
                : row?.price_usd_per_mmbtu || '',
        });
    }

    function updateCustomerName(value) {
        const identity = averagePriceCustomerIdentity(value.trim(), selectedMonth);
        const matchingRows = report.rows
            .filter((row) => averagePriceCustomerIdentity(row.customer, selectedMonth) === identity)
            .sort((left, right) => (
                Number(right.sm3 > 0) - Number(left.sm3 > 0)
                || Number(right.has_valid_price) - Number(left.has_valid_price)
            ));
        if (matchingRows.length > 0) {
            selectCustomer(matchingRows[0].customer_key);
            return;
        }
        const matchingCustomer = customerCatalog.find(
            (customer) => averagePriceCustomerIdentity(customer.customer_name, selectedMonth) === identity,
        );
        if (matchingCustomer) {
            selectCustomer(matchingCustomer.customer_key);
            return;
        }
        setSelectedCustomerKey('');
        setCustomerEntry((current) => ({
            ...current,
            customer: value,
            operator: '',
            region: '',
            price_unit: 'USD_MMBTU',
            price: '',
        }));
    }

    function updateFactor(operator, value) {
        setReport((current) => ({
            ...current,
            operator_factors: { ...current.operator_factors, [operator]: value },
            rows: current.rows.map((row) => row.operator === operator
                ? {
                    ...row,
                    mmbtu_override: null,
                    total_usd_override: null,
                    rupiah_override: null,
                }
                : row),
        }));
    }

    function updateExchangeRate(value) {
        setExchangeRateInput(value);
        setExchangeRateInputDirty(true);
        const parsedRate = parseExchangeRate(value);
        setExchangeRateInputError(parsedRate == null);
        if (parsedRate == null) return;
        setReport((current) => ({
            ...current,
            exchange_rate: parsedRate,
            rows: current.rows.map((row) => ({
                ...row,
                total_usd_override: null,
                rupiah_override: row.price_unit === 'IDR_SM3'
                    ? row.rupiah_override
                    : null,
            })),
        }));
    }

    function updateTarget(area, value) {
        const numericValue = value === '' ? '' : Number(value);
        const roundedValue = value === '' || !Number.isFinite(numericValue)
            ? value
            : Math.round(numericValue);
        setReport((current) => ({
            ...current,
            targets: { ...current.targets, [area]: roundedValue },
        }));
    }

    async function persistReport(nextReport, successMessage) {
        if (!selectedMonth) return;
        const exchangeRate = exchangeRateInputDirty
            ? parseExchangeRate(exchangeRateInput)
            : Number(nextReport.exchange_rate || 0);
        if (exchangeRate == null) {
            setExchangeRateInputError(true);
            setError('Kurs harus berupa angka bulat. Contoh: 18.069 berarti Rp18.069 per USD.');
            return;
        }
        setSaving(true);
        setError('');
        setNotice('');
        try {
            await api('/api/monthly-average-price', {
                method: 'POST',
                body: {
                    month: selectedMonth,
                    operator_factors: Object.fromEntries(operators.map((operator) => [
                        operator,
                        Number(nextReport.operator_factors[operator] || 0),
                    ])),
                    exchange_rate: exchangeRate,
                    targets: Object.fromEntries(activeComparisonAreas.map(({ key }) => [
                        key,
                        nextReport.targets[key] === '' || nextReport.targets[key] == null
                            ? null
                            : Math.round(Number(nextReport.targets[key])),
                    ])),
                    entries: nextReport.rows.map((row) => ({
                        customer_key: row.customer_key,
                        region: row.region || '',
                        price_unit: row.price_unit || 'USD_MMBTU',
                        price_usd_per_mmbtu: row.price_unit === 'IDR_SM3'
                            ? 0
                            : Number(row.price_usd_per_mmbtu || 0),
                        price_rp_per_sm3: row.price_unit === 'IDR_SM3'
                            ? Number(row.price_rp_per_sm3 || 0)
                            : 0,
                        sm3_override: row.sm3_override ?? null,
                        mmbtu_override: row.mmbtu_override ?? null,
                        total_usd_override: row.total_usd_override ?? null,
                        rupiah_override: row.rupiah_override ?? null,
                        include_in_summary: row.include_in_summary !== false,
                    })),
                },
            });
            const refreshed = await api(`/api/monthly-average-price?month=${encodeURIComponent(selectedMonth)}`);
            setReport(refreshed);
            setExchangeRateInput(refreshed.exchange_rate
                ? Number.isInteger(Number(refreshed.exchange_rate))
                    ? formatInteger(refreshed.exchange_rate)
                    : String(refreshed.exchange_rate)
                : '');
            setExchangeRateInputError(false);
            setExchangeRateInputDirty(false);
            setNotice(successMessage);
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSaving(false);
        }
    }

    async function saveCustomerEntry(event) {
        event.preventDefault();
        const customerName = customerEntry.customer.trim();
        const price = Number(customerEntry.price);
        if (!customerName) {
            setError('Nama customer wajib diisi.');
            return;
        }
        if (isExcludedAveragePriceCustomer(customerName)) {
            setError('Pentawira tidak termasuk dalam Average Price.');
            return;
        }
        const identity = averagePriceCustomerIdentity(customerName, selectedMonth);
        const selectedRow = report.rows.find((item) => item.customer_key === selectedCustomerKey);
        const matchingRows = report.rows
            .filter((item) => (
                averagePriceCustomerIdentity(item.customer, selectedMonth) === identity
                && (!selectedRow || item.operator === selectedRow.operator)
            ))
            .sort((left, right) => (
                Number(right.sm3 > 0) - Number(left.sm3 > 0)
                || Number(right.has_valid_price) - Number(left.has_valid_price)
            ));
        const row = selectedRow || matchingRows[0];
        const matchingMasterCustomer = customerCatalog.find((customer) => (
            averagePriceCustomerIdentity(customer.customer_name, selectedMonth) === identity
            && (!row || customer.operator === row.operator)
        ));
        const existingCustomer = row || matchingMasterCustomer;
        const hasWorkbookData = selectedCustomerHasWorkbookData
            || (Number(row?.sm3_override) > 0 && !row?.region);
        if (!existingCustomer && !customerEntry.operator) {
            setError('Pilih operator untuk customer baru.');
            return;
        }
        if (!hasWorkbookData && !customerEntry.region) {
            setError('Pilih wilayah untuk customer ini.');
            return;
        }
        if (!Number.isFinite(price) || price <= 0) {
            setError('Harga harus berupa angka lebih besar dari nol.');
            return;
        }

        setError('');
        setSaving(true);
        try {
            let customerKey = existingCustomer?.customer_key || '';
            const operator = row?.operator || matchingMasterCustomer?.operator || customerEntry.operator;
            if (!customerKey) {
                const createdCustomer = await api('/api/customer-mapping', {
                    method: 'POST',
                    body: { customer: customerName, operator },
                });
                if (typeof createdCustomer.customer_key !== 'string' || !createdCustomer.customer_key) {
                    throw new Error('Server tidak mengembalikan identitas customer baru.');
                }
                customerKey = createdCustomer.customer_key;
                setCustomerCatalog((current) => (
                    current.some((customer) => customer.customer_key === customerKey)
                        ? current
                        : [...current, {
                            customer_key: customerKey,
                            customer_name: customerName,
                            operator,
                        }]
                ));
            }

            const existingRow = row || {
                customer_key: customerKey,
                customer: matchingMasterCustomer?.customer_name || customerName,
                operator,
                region: customerEntry.region,
                so_sm3: 0,
                actual_sm3: 0,
                sm3: 0,
                price_unit: customerEntry.price_unit,
                price_usd_per_mmbtu: 0,
                price_rp_per_sm3: 0,
                sm3_override: null,
                mmbtu_override: null,
                total_usd_override: null,
                rupiah_override: null,
                total_usd: 0,
                rupiah: 0,
                include_in_summary: true,
            };
            const priceChanged = existingRow.price_unit !== customerEntry.price_unit
                || (customerEntry.price_unit === 'IDR_SM3'
                    ? Number(existingRow.price_rp_per_sm3 || 0) !== price
                    : Number(existingRow.price_usd_per_mmbtu || 0) !== price);
            const updatedRow = {
                ...existingRow,
                region: customerEntry.region || existingRow.region || '',
                price_unit: customerEntry.price_unit,
                price_usd_per_mmbtu: customerEntry.price_unit === 'USD_MMBTU' ? price : 0,
                price_rp_per_sm3: customerEntry.price_unit === 'IDR_SM3' ? price : 0,
                total_usd_override: priceChanged ? null : existingRow.total_usd_override,
                rupiah_override: priceChanged ? null : existingRow.rupiah_override,
            };
            const keysToUpdate = new Set(
                matchingRows
                    .filter((item) => item.operator === operator)
                    .map((item) => item.customer_key),
            );
            if (row) keysToUpdate.add(row.customer_key);
            const nextRows = report.rows.some((item) => keysToUpdate.has(item.customer_key))
                ? report.rows.map((item) => (
                    keysToUpdate.has(item.customer_key)
                        ? {
                            ...item,
                            region: item.customer_key === row?.customer_key
                                ? customerEntry.region || item.region || ''
                                : item.region || '',
                            price_unit: updatedRow.price_unit,
                            price_usd_per_mmbtu: updatedRow.price_usd_per_mmbtu,
                            price_rp_per_sm3: updatedRow.price_rp_per_sm3,
                            total_usd_override: null,
                            rupiah_override: null,
                        }
                        : item
                ))
                : [...report.rows, updatedRow];
            const nextReport = { ...report, rows: nextRows };
            setSelectedCustomerKey(customerKey);
            await persistReport(
                nextReport,
                `Data Average Price ${customerName} berhasil disimpan untuk ${monthLabel(selectedMonth)}.`,
            );
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSaving(false);
        }
    }

    async function saveReport(event) {
        event.preventDefault();
        await persistReport(
            report,
            `Pengaturan Average Price ${monthLabel(selectedMonth)} berhasil disimpan.`,
        );
    }

    function updatePendingSheetCustomer(customer, field, value) {
        setPendingSheetCustomers((current) => current.map((item) => (
            item.customer === customer ? { ...item, [field]: value } : item
        )));
    }

    async function syncPricesFromSheet(customerMappings = []) {
        if (!selectedMonth || sheetSyncInFlight.current) return;
        const syncMonth = selectedMonth;
        sheetSyncInFlight.current = true;
        setImportingSheet(true);
        setError('');
        try {
            const result = await api('/api/monthly-average-price/sheet-sync', {
                method: 'POST',
                body: {
                    month: syncMonth,
                    customer_mappings: customerMappings,
                },
                signal: AbortSignal.timeout(30000),
            });
            if (selectedMonth !== syncMonth) return;
            setSheetCustomerKeys(result.sheet_customer_keys || []);
            setPendingSheetCustomers((current) => result.unmatched_customers.map((customer) => (
                current.find((item) => item.customer === customer)
                || { customer, operator: '', region: '' }
            )));
            if (customerMappings.length > 0) {
                const refreshedCustomers = await api('/api/customers');
                setCustomerCatalog(refreshedCustomers.filter((customer) => (
                    !isExcludedAveragePriceCustomer(customer.customer_key)
                )));
            }
            const refreshedReport = await api(
                `/api/monthly-average-price?month=${encodeURIComponent(syncMonth)}`,
            );
            if (selectedMonth !== syncMonth) return;
            setReport(refreshedReport);
            setExchangeRateInput(refreshedReport.exchange_rate
                ? Number.isInteger(Number(refreshedReport.exchange_rate))
                    ? formatInteger(refreshedReport.exchange_rate)
                    : String(refreshedReport.exchange_rate)
                : '');
            setExchangeRateInputError(false);
            setExchangeRateInputDirty(false);
            setError('');
            setSheetSyncStatus(
                `Terakhir tersinkron ${new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}. ${result.imported} harga diperbarui dari ${result.source} untuk ${monthLabel(syncMonth)}.`,
            );
            if (result.created_customers.length > 0) {
                setNotice(`${result.created_customers.length} customer baru ditambahkan ke master.`);
            }
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            sheetSyncInFlight.current = false;
            setImportingSheet(false);
        }
    }

    async function addSheetCustomers() {
        const incompleteCustomer = pendingSheetCustomers.find((item) => !item.operator || !item.region);
        if (incompleteCustomer) {
            setError(`Pilih operator dan wilayah untuk customer ${incompleteCustomer.customer}.`);
            return;
        }
        await syncPricesFromSheet(pendingSheetCustomers);
    }

    const workbookAreaOrder = selectedMonth >= '2026-01' && selectedMonth < '2026-08'
        ? ['JAWA BARAT', 'JAWA TENGAH DAN TIMUR', 'WILAYAH BELUM DIPETAKAN']
        : ['JAWA BARAT', 'JAWA TENGAH', 'JAWA TIMUR', 'WILAYAH BELUM DIPETAKAN'];
    const workbookAreaOrderByName = new Map(
        workbookAreaOrder.map((area, index) => [area, index]),
    );
    const calculatedRows = report.rows.map((row) => {
        const sm3 = Number(row.sm3 ?? row.actual_sm3 ?? 0);
        const factor = Number(report.operator_factors[row.operator] || 0);
        const volumeMmbtu = row.mmbtu_override != null
            ? Number(row.mmbtu_override)
            : factor > 0 ? sm3 / factor : 0;
        const priceUnit = row.price_unit || 'USD_MMBTU';
        const priceUsd = Number(row.price_usd_per_mmbtu || 0);
        const priceRp = Number(row.price_rp_per_sm3 || 0);
        const exchangeRate = Number(report.exchange_rate || 0);
        const calculatedRp = priceUnit === 'IDR_SM3'
            ? sm3 * priceRp
            : volumeMmbtu * priceUsd * exchangeRate;
        const totalRp = row.rupiah_override != null
            ? Number(row.rupiah_override)
            : calculatedRp;
        const calculatedUsd = priceUnit === 'IDR_SM3'
            ? (exchangeRate > 0 ? totalRp / exchangeRate : 0)
            : volumeMmbtu * priceUsd;
        const totalUsd = row.total_usd_override != null
            ? Number(row.total_usd_override)
            : calculatedUsd;
        const customerKey = normalizeCustomerOrder(row.customer_key);
        const customer = selectedMonth === '2026-01'
            ? januaryCustomerAliases[customerKey] || customerOrderAliases[customerKey] || row.customer
            : customerOrderAliases[customerKey] || row.customer;
        const workbookArea = workbookAreaForCustomer(row.region, customer, selectedMonth);
        const workbookGroup = workbookGroupForCustomer({ customer, region: workbookArea }, selectedMonth);
        return {
            ...row,
            customer,
            price_unit: priceUnit,
            sm3,
            volume_mmbtu: volumeMmbtu,
            total_usd: totalUsd,
            rupiah: totalRp,
            workbook_group: workbookGroup,
            workbook_area: workbookArea,
        };
    }).map((row, index) => ({ row, index }))
        .sort((left, right) => {
            const leftAreaOrder = workbookAreaOrderByName.get(left.row.workbook_area) ?? Infinity;
            const rightAreaOrder = workbookAreaOrderByName.get(right.row.workbook_area) ?? Infinity;
            if (leftAreaOrder !== rightAreaOrder) return leftAreaOrder - rightAreaOrder;
            const groupOrder = left.row.workbook_group.index - right.row.workbook_group.index;
            if (groupOrder !== 0) return groupOrder;
            const leftOrder = customerOrderIndex.get(normalizeCustomerOrder(left.row.customer)) ?? Infinity;
            const rightOrder = customerOrderIndex.get(normalizeCustomerOrder(right.row.customer)) ?? Infinity;
            return leftOrder - rightOrder || left.index - right.index;
        })
        .map(({ row }) => row);
    const sheetCustomerKeySet = new Set(sheetCustomerKeys.map(normalizeCustomerOrder));
    const inSheetUnmappedCustomers = calculatedRows.filter((row) =>
        row.workbook_group.index >= workbookCustomerGroups.length
        && sheetCustomerKeySet.has(normalizeCustomerOrder(row.customer_key)),
    );
    const calculationRows = calculatedRows.filter((row) =>
        row.workbook_group.index < workbookCustomerGroups.length
        || sheetCustomerKeySet.has(normalizeCustomerOrder(row.customer_key)),
    );
    const sourceDisplayRows = calculationRows.filter((row) =>
        row.sm3 > 0
        || Number(row.price_usd_per_mmbtu) > 0
        || Number(row.price_rp_per_sm3) > 0
        || Number(row.total_usd_override) > 0
        || Number(row.rupiah_override) > 0,
    );
    const displayRows = aggregateDuplicateCustomers(sourceDisplayRows);
    const displayGroups = displayRows.reduce((groups, row) => {
        const currentGroup = groups[groups.length - 1];
        if (
            !currentGroup
            || currentGroup.group.index !== row.workbook_group.index
            || currentGroup.area !== row.workbook_area
        ) {
            groups.push({ area: row.workbook_area, group: row.workbook_group, rows: [row] });
        } else {
            currentGroup.rows.push(row);
        }
        return groups;
    }, []);
    const displayRowNumbers = new Map();
    displayGroups.forEach((group) => {
        group.rows.forEach((row, index) => {
            displayRowNumbers.set(normalizeCustomerOrder(row.customer), index + 1);
        });
    });
    const calculatedTotals = calculationRows.filter((row) =>
        row.has_valid_price && row.include_in_summary !== false,
    ).reduce((sum, row) => ({
        sm3: sum.sm3 + row.sm3,
        mmbtu: sum.mmbtu + row.volume_mmbtu,
        usd: sum.usd + row.total_usd,
        rupiah: sum.rupiah + row.rupiah,
    }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
    const totals = calculatedTotals;
    const validRowsByArea = calculationRows
        .filter((row) => row.has_valid_price && row.sm3 > 0)
        .reduce((areas, row) => {
            const areaRows = areas.get(row.workbook_area) || [];
            areaRows.push(row);
            areas.set(row.workbook_area, areaRows);
            return areas;
        }, new Map());
    const standaloneAreas = new Set(
        Array.from(validRowsByArea.entries())
            .filter(([, rows]) => !rows.some((row) => row.include_in_summary !== false))
            .map(([area]) => area),
    );
    const regionalTotalsByName = new Map([
        ['JAWA BARAT', { region: 'JAWA BARAT', sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 }],
        ['JAWA TENGAH', { region: 'JAWA TENGAH', sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 }],
        ['JAWA TIMUR', { region: 'JAWA TIMUR', sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 }],
    ]);
    calculationRows.filter((row) =>
        row.has_valid_price
        && (row.include_in_summary !== false || standaloneAreas.has(row.workbook_area)),
    ).forEach((row) => {
        const region = row.workbook_area || 'WILAYAH BELUM DIPETAKAN';
        if (!regionalTotalsByName.has(region)) {
            regionalTotalsByName.set(region, { region, sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
        }
        const regionTotals = regionalTotalsByName.get(region);
        regionTotals.sm3 += row.sm3;
        regionTotals.mmbtu += row.volume_mmbtu;
        regionTotals.usd += row.total_usd;
        regionTotals.rupiah += row.rupiah;
    });
    const regionalTotals = Array.from(regionalTotalsByName.values());
    const regionalAspByName = new Map(
        regionalTotals
            .filter((area) => area.sm3 > 0)
            .map((area) => [area.region, area.rupiah / area.sm3]),
    );
    const averagePriceRpSm3 = totals.sm3 > 0 ? totals.rupiah / totals.sm3 : 0;
    const hasUncalculatedPriceRows = calculationRows.some((row) =>
        !row.has_valid_price
        && (row.price_unit === 'IDR_SM3'
            ? Number(row.price_rp_per_sm3) > 0
            : Number(row.price_usd_per_mmbtu) > 0),
    );
    const customerSuggestions = Array.from(new Map(
        [
            ...pdfCustomerNames,
            ...customerCatalog.map((customer) => customer.customer_name),
            ...report.rows.map((row) => row.customer),
        ]
            .map((customerName) => [normalizeCustomerOrder(customerName), customerName])
            .filter(([customerKey]) => customerKey),
    ).values());
    const comparisonRows = activeComparisonAreas.map((area) => {
        let prognosis = null;
        if (area.key === 'ALL_EXCEPT_JATIM') {
            prognosis = totals.sm3 > 0 ? averagePriceRpSm3 : null;
        } else if (area.regions.length === 1) {
            prognosis = regionalAspByName.get(area.regions[0]) ?? null;
        } else {
            const areaTotals = area.regions.reduce((sum, region) => {
                const regionTotals = regionalTotalsByName.get(region);
                return regionTotals
                    ? {
                        sm3: sum.sm3 + regionTotals.sm3,
                        rupiah: sum.rupiah + regionTotals.rupiah,
                    }
                    : sum;
            }, { sm3: 0, rupiah: 0 });
            prognosis = areaTotals.sm3 > 0
                ? areaTotals.rupiah / areaTotals.sm3
                : null;
        }
        const targetValue = report.targets[area.key];
        const target = targetValue == null || targetValue === '' ? null : Number(targetValue);
        const hasRegionalRows = area.key === 'ALL_EXCEPT_JATIM'
            ? calculationRows.some((row) => row.include_in_summary !== false)
            : calculationRows.some((row) => area.regions.includes(row.workbook_area));
        return {
            ...area,
            target,
            prognosis,
            hasRegionalRows,
            difference: target != null && prognosis != null ? prognosis - target : null,
        };
    });
    const selectedCustomer = report.rows.find((row) => row.customer_key === selectedCustomerKey);
    const selectedCustomerHasWorkbookData = Number(selectedCustomer?.sm3_override) > 0
        && !selectedCustomer?.region;
    const hasUnassignedWorkbookRegions = inSheetUnmappedCustomers.some(
        (row) => Number(row.sm3_override) > 0 && !row.region,
    );
    const comparisonChartData = {
        labels: comparisonRows.map((row) => row.label),
        datasets: [
            {
                label: 'Target',
                data: comparisonRows.map((row) => row.target),
                backgroundColor: '#56843d',
                borderRadius: 2,
                maxBarThickness: 28,
            },
            {
                label: 'Prognosa',
                data: comparisonRows.map((row) => row.prognosis),
                backgroundColor: '#a8d184',
                borderRadius: 2,
                maxBarThickness: 28,
            },
        ],
    };

    return (
        <div className={`weekly-average-page${canViewCustomerResults ? '' : ' average-price-user-page'}`}>
            {error && <div className="notice bad" role="alert">{error}</div>}
            {notice && <div className="notice good" role="status">{notice}</div>}
            {canEdit && sheetSyncStatus && (
                <div className="notice" role="status">{sheetSyncStatus} Sinkron otomatis setiap 5 menit selama halaman terbuka.</div>
            )}
            {hasUncalculatedPriceRows && (
                <div className="notice" role="status">
                    Beberapa harga sudah tercatat, tetapi belum dapat dihitung karena kurs atau faktor konversi belum tersedia. Baris tersebut tidak masuk total.
                </div>
            )}

            <section className="average-kpi-grid">
                <article className="average-kpi average-kpi-blue"><span className="average-kpi-icon">▤</span><div><small>TOTAL SM³</small><strong>{formatInteger(totals.sm3)}</strong><span>Volume sumber perhitungan</span></div></article>
                <article className="average-kpi average-kpi-green"><span className="average-kpi-icon">◆</span><div><small>TOTAL MMBTU</small><strong>{formatInteger(totals.mmbtu)}</strong><span>Sm³ ÷ faktor operator</span></div></article>
                <article className="average-kpi average-kpi-teal"><span className="average-kpi-icon">AVG</span><div><small>AVERAGE Rp/Sm³</small><strong>{formatDecimal(averagePriceRpSm3, 2)}</strong><span>Total Rupiah ÷ volume sumber</span></div></article>
            </section>

            <section className="average-data-panel">
                <div className={`average-workspace-grid${canViewCustomerResults ? '' : ' average-workspace-grid-user'}`}>
                    <div className="average-workspace-column average-workspace-left">
                {canViewCustomerResults && <>
                <div className="average-data-heading">
                    <div className="average-panel-heading">
                        <b>Hasil Perhitungan Average Price</b>
                    </div>
                </div>
                <div>
                    <div className="average-table-wrap average-customer-table-wrap" role="region" aria-label="Tabel data Average Price Customer" tabIndex="0">
                        <table className="average-data-table">
                            <thead><tr><th>No</th><th>Customer</th><th>Sm³</th><th>MMBTU</th><th>Harga / MMBTU</th><th>Total USD</th><th>Total Rupiah</th></tr></thead>
                            <tbody>
                                {displayRows.length === 0
                                    ? (
                                        <tr>
                                            <td colSpan="7" className="empty-row">
                                                {loading
                                                    ? 'Memuat data...'
                                                    : 'Belum ada data volume untuk bulan ini.'}
                                            </td>
                                        </tr>
                                    )
                                    : displayGroups.map((group, groupIndex) => {
                                        const groupTotals = group.rows
                                            .flatMap((row) => row.source_rows)
                                            .filter((row) => row.has_valid_price
                                                && (row.include_in_summary !== false
                                                    || standaloneAreas.has(group.area)))
                                            .reduce((sum, row) => ({
                                                    sm3: sum.sm3 + row.sm3,
                                                    mmbtu: sum.mmbtu + row.volume_mmbtu,
                                                    usd: sum.usd + row.total_usd,
                                                    rupiah: sum.rupiah + row.rupiah,
                                            }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
                                        const isUnmappedGroup = group.group.index >= workbookCustomerGroups.length;
                                        const showAreaHeading = !isUnmappedGroup
                                            && (groupIndex === 0 || displayGroups[groupIndex - 1].area !== group.area);
                                        const isLastGroupInArea = groupIndex === displayGroups.length - 1
                                            || displayGroups[groupIndex + 1].area !== group.area;
                                        const areaTotals = regionalTotalsByName.get(group.area);
                                        return <React.Fragment key={`${group.area}:${group.group.index}`}>
                                                    {showAreaHeading && (
                                                        <tr className="average-workbook-area">
                                                                <th colSpan="7">{group.area}</th>
                                                        </tr>
                                                        )}
                                                        <tr className={`average-workbook-group${isUnmappedGroup ? ' average-unmapped-group' : ''}`}>
                                                            {isUnmappedGroup
                                                                ? <th colSpan="7">BELUM DIPETAKAN</th>
                                                                : <>
                                                                    <th>{group.group.index < 4 ? 'DIRECT' : 'KSO'}</th>
                                                                    <th>{group.group.label.replace(/^KSO · /, '')}</th>
                                                                    <th colSpan="5"></th>
                                                                </>}
                                                        </tr>
                                                        {group.rows.map((row) => {
                                                            return <tr key={row.customer_key}>
                                                            <td>{displayRowNumbers.get(normalizeCustomerOrder(row.customer))}</td>
                                                            <td>
                                                                {row.customer}{row.include_in_summary === false ? ' *' : ''}
                                                            </td>
                                                            <td>{formatInteger(row.sm3)}</td>
                                                            <td>{formatInteger(row.volume_mmbtu)}</td>
                                                            <td>{row.has_valid_price
                                                                ? <>
                                                                    {row.price_unit === 'IDR_SM3' ? 'Rp ' : '$ '}
                                                                    {row.price_unit === 'IDR_SM3'
                                                                        ? formatDecimal(row.price_rp_per_sm3, 2)
                                                                        : formatDecimal(row.price_usd_per_mmbtu, 2)}
                                                                </>
                                                                : '—'}
                                                            </td>
                                                            <td>{row.has_valid_price ? `$ ${formatDecimal(row.total_usd, 2)}` : '—'}</td>
                                                            <td>{row.has_valid_price ? `Rp ${formatDecimal(row.rupiah, 2)}` : '—'}</td>
                                                    </tr>;
                                                })}
                                                <tr className="average-workbook-subtotal">
                                                    <th colSpan="2">{isUnmappedGroup ? 'JUMLAH BELUM DIPETAKAN' : 'JUMLAH'}</th>
                                                    <th>{formatInteger(groupTotals.sm3)}</th>
                                                    <th>{formatInteger(groupTotals.mmbtu)}</th>
                                                    <th>—</th>
                                                    <th>$ {formatDecimal(groupTotals.usd, 2)}</th>
                                                    <th>Rp {formatDecimal(groupTotals.rupiah, 2)}</th>
                                                </tr>
                                                <tr className="average-workbook-average">
                                                    <th colSpan="2">AVG</th>
                                                    <th>—</th>
                                                    <th>—</th>
                                                    <th>
                                                        {groupTotals.mmbtu > 0
                                                            ? `$ ${formatDecimal(groupTotals.usd / groupTotals.mmbtu, 2)}`
                                                            : '—'}
                                                    </th>
                                                    <th>—</th>
                                                    <th>
                                                        {groupTotals.sm3 > 0
                                                            ? `Rp ${formatDecimal(groupTotals.rupiah / groupTotals.sm3, 2)}`
                                                            : '—'}
                                                    </th>
                                                </tr>
                                                {isLastGroupInArea && areaTotals && (
                                                    <>
                                                        <tr className="average-regional-total-row">
                                                            <th colSpan="2">TOTAL {areaTotals.region}{standaloneAreas.has(group.area) ? ' · DI LUAR KONSOLIDASI' : ''}</th>
                                                            <th>{formatInteger(areaTotals.sm3)}</th>
                                                            <th>{formatInteger(areaTotals.mmbtu)}</th>
                                                            <th>—</th>
                                                            <th>$ {formatDecimal(areaTotals.usd, 2)}</th>
                                                            <th>Rp {formatDecimal(areaTotals.rupiah, 2)}</th>
                                                        </tr>
                                                        <tr className="average-regional-average-row">
                                                            <th colSpan="6">ASP {areaTotals.region}{standaloneAreas.has(group.area) ? ' · DI LUAR KONSOLIDASI' : ''}</th>
                                                            <th>
                                                                {regionalAspByName.has(areaTotals.region)
                                                                    ? `Rp ${formatDecimal(regionalAspByName.get(areaTotals.region), 2)}`
                                                                    : '—'}
                                                            </th>
                                                        </tr>
                                                    </>
                                                )}
                                            </React.Fragment>;
                                    })}
                            </tbody>
                            {displayRows.length > 0 && <tfoot>
                                <tr>
                                    <th colSpan="2">TOTAL KESELURUHAN</th>
                                    <th>{formatInteger(totals.sm3)}</th>
                                    <th>{formatInteger(totals.mmbtu)}</th>
                                    <th>—</th>
                                    <th>$ {formatDecimal(totals.usd, 2)}</th>
                                    <th>Rp {formatDecimal(totals.rupiah, 2)}</th>
                                </tr>
                            </tfoot>}
                        </table>
                    </div>
                </div>
                </>}
                {canEdit && <>
                <div className="average-data-heading average-customer-entry-heading">
                    <div className="average-panel-heading">
                        <b>Input Average Price Customer</b>
                    </div>
                    <div className="average-toolbar average-source-actions">
                        <button
                            type="button"
                            onClick={() => syncPricesFromSheet()}
                            disabled={importingSheet || saving || loading || customersLoading || !selectedMonth}
                        >
                            {importingSheet ? 'Menyinkronkan...' : 'Sinkronkan Harga Google'}
                        </button>
                    </div>
                </div>
                {pendingSheetCustomers.length > 0 && (
                    <section className="average-new-customer-panel" aria-label="Pemetaan customer baru dari spreadsheet">
                        <div>
                            <b>Customer baru perlu dipetakan</b>
                            <span>Pilih operator dan wilayah agar customer dapat ditambahkan ke master dan harga disinkronkan.</span>
                        </div>
                        {pendingSheetCustomers.map((item) => (
                            <div className="average-new-customer-row" key={item.customer}>
                                <strong>{item.customer}</strong>
                                <label>
                                    Operator
                                    <select
                                        value={item.operator}
                                        onChange={(event) => updatePendingSheetCustomer(item.customer, 'operator', event.target.value)}
                                    >
                                        <option value="">Pilih operator</option>
                                        {operators.map((operator) => (
                                            <option key={operator} value={operator}>{operator}</option>
                                        ))}
                                    </select>
                                </label>
                                <label>
                                    Wilayah
                                    <select
                                        value={item.region}
                                        onChange={(event) => updatePendingSheetCustomer(item.customer, 'region', event.target.value)}
                                    >
                                        <option value="">Pilih wilayah</option>
                                        {regions.map((region) => (
                                            <option key={region} value={region}>{region}</option>
                                        ))}
                                    </select>
                                </label>
                            </div>
                        ))}
                        <button
                            className="average-add-button"
                            type="button"
                            onClick={addSheetCustomers}
                            disabled={importingSheet || pendingSheetCustomers.some((item) => !item.operator || !item.region)}
                        >
                            {importingSheet ? 'Menyimpan pemetaan...' : 'Tambahkan Customer dan Sinkronkan'}
                        </button>
                    </section>
                )}
                <form className="average-entry-form" onSubmit={saveCustomerEntry}>
                    <label>
                        Periode
                        <input readOnly value={monthLabel(selectedMonth)} />
                    </label>
                    <label>
                        Customer
                        <input
                            type="text"
                            list="average-customer-options"
                            required
                            maxLength="255"
                            placeholder="Ketik nama customer"
                            value={customerEntry.customer}
                            onChange={(event) => updateCustomerName(event.target.value)}
                        />
                        <datalist id="average-customer-options">
                            {customerSuggestions.map((customerName) => (
                                <option key={normalizeCustomerOrder(customerName)} value={customerName} />
                            ))}
                        </datalist>
                        <small className="average-conversion-note">
                            Pilih customer yang sudah ada untuk memperbarui harganya tanpa menambah baris customer baru.
                        </small>
                    </label>
                    <label>
                        Operator
                        {selectedCustomerKey
                            ? <input readOnly value={customerEntry.operator} />
                            : <select
                                required
                                value={customerEntry.operator}
                                onChange={(event) => setCustomerEntry((current) => ({
                                    ...current,
                                    operator: event.target.value,
                                }))}
                            >
                                <option value="">Pilih operator</option>
                                {operators.map((operator) => <option key={operator} value={operator}>{operator}</option>)}
                            </select>}
                    </label>
                    <label>
                        Wilayah
                        {selectedCustomerHasWorkbookData
                            ? <input readOnly value="Tidak tersedia di file" />
                            : <select
                            required
                            value={customerEntry.region}
                            onChange={(event) => setCustomerEntry((current) => ({
                                ...current,
                                region: event.target.value,
                            }))}
                        >
                            <option value="">Pilih wilayah</option>
                            {regions.map((region) => <option key={region} value={region}>{region}</option>)}
                        </select>}
                    </label>
                    <label>
                        Satuan Harga
                        <select
                            value={customerEntry.price_unit}
                            onChange={(event) => setCustomerEntry((current) => ({
                                ...current,
                                price_unit: event.target.value,
                                price: '',
                            }))}
                        >
                            <option value="USD_MMBTU">USD/MMBTU</option>
                            <option value="IDR_SM3">Rp/Sm³</option>
                        </select>
                    </label>
                    <label>
                        Harga {customerEntry.price_unit === 'IDR_SM3' ? '(Rp/Sm³)' : '(USD/MMBTU)'}
                        <input
                            required
                            type="number"
                            min="0"
                            step={customerEntry.price_unit === 'IDR_SM3' ? '1' : '0.0001'}
                            value={customerEntry.price}
                            onChange={(event) => setCustomerEntry((current) => ({
                                ...current,
                                price: event.target.value,
                            }))}
                        />
                    </label>
                    <div className="average-entry-actions">
                        <button className="primary" type="submit" disabled={saving || loading || customersLoading || !selectedMonth}>
                            {saving ? 'Menyimpan...' : selectedCustomerKey ? 'Perbarui Harga' : 'Simpan Harga'}
                        </button>
                    </div>
                </form>
                </>}
                <div className="average-conversion-panel">
                    <div className="average-data-heading average-conversion-heading">
                        <div className="average-panel-heading">
                            <b>Faktor Konversi Operator dan Kurs</b>
                        </div>
                        <label className="average-filter-field">
                            <span>Kurs Rp/USD</span>
                            {canEdit ? (
                                <input
                                    aria-label="Kurs Rupiah per USD"
                                    type="text"
                                    inputMode="decimal"
                                    value={exchangeRateInput}
                                    aria-invalid={exchangeRateInputError}
                                    onChange={(event) => updateExchangeRate(event.target.value)}
                                    onBlur={() => {
                                        if (!exchangeRateInputDirty) return;
                                        const parsedRate = parseExchangeRate(exchangeRateInput);
                                        if (parsedRate != null) {
                                            setExchangeRateInput(parsedRate ? formatInteger(parsedRate) : '');
                                        }
                                    }}
                                />
                            ) : <span>{report.exchange_rate ? formatInteger(report.exchange_rate) : '—'}</span>}
                        </label>
                    </div>
                    <div className="average-table-wrap average-conversion-wrap">
                        <table className="average-data-table average-conversion-table">
                            <thead><tr><th>No</th><th>Operator</th><th>Faktor Sm³ per MMBTU</th><th>Contoh</th></tr></thead>
                            <tbody>{operators.map((operator, index) => <tr key={operator}>
                                <td>{index + 1}</td>
                                <td>{operator}</td>
                                <td>{canEdit
                                    ? <input aria-label={`Faktor konversi ${operator}`} type="number" min="0" step="any" inputMode="decimal" value={report.operator_factors[operator] || ''} onChange={(event) => updateFactor(operator, event.target.value)} />
                                    : report.operator_factors[operator] || '—'}</td>
                                <td>MMBTU = Sm³ ÷ faktor</td>
                            </tr>)}</tbody>
                        </table>
                    </div>
                    {canEdit && <small className="average-conversion-note">Gunakan semua angka desimal faktor dari Excel, lalu klik Simpan Data Bulan Ini.</small>}
                </div>
                    </div>

                    <div className="average-workspace-column average-workspace-right">
                    <div className="average-comparison-content">
                    <div className="average-data-heading average-comparison-heading">
                        <div className="average-panel-heading">
                            <b>Target Harga dan Prognosa (Rp/Sm³)</b>
                        </div>
                    </div>
                    <div className="average-comparison-chart">
                        <Bar data={comparisonChartData} options={comparisonChartOptions} />
                    </div>
                    <div className="average-table-wrap">
                        <table className="average-data-table average-comparison-table">
                            <thead><tr><th>Area</th><th>Target (Rp/Sm³)</th><th>Prognosa (Rp/Sm³)</th><th>Selisih (Rp/Sm³)</th></tr></thead>
                            <tbody>{comparisonRows.map((row) => (
                                <tr key={row.key}>
                                    <td>{row.label}</td>
                                    <td>
                                        {canEdit ? (
                                            <input
                                                aria-label={`Target harga ${row.label}`}
                                                type="number"
                                                min="0"
                                                step="1"
                                                placeholder="Input target"
                                                value={report.targets[row.key] ?? ''}
                                                onChange={(event) => updateTarget(row.key, event.target.value)}
                                            />
                                        ) : report.targets[row.key] == null ? '—' : formatInteger(report.targets[row.key])}
                                    </td>
                                    <td>{row.prognosis == null
                                        ? hasUnassignedWorkbookRegions && !row.hasRegionalRows
                                            ? 'Tidak ada data wilayah'
                                            : '—'
                                        : formatDecimal(row.prognosis, 2)}</td>
                                    <td className={row.difference == null ? '' : row.difference < 0 ? 'diff-neg' : 'diff-pos'}>
                                        {row.difference == null
                                            ? hasUnassignedWorkbookRegions && !row.hasRegionalRows
                                                ? 'Tidak ada data wilayah'
                                                : '—'
                                            : formatDifference(row.difference)}
                                    </td>
                                </tr>
                            ))}</tbody>
                        </table>
                    </div>
                    {canEdit && <div className="average-toolbar average-monthly-save">
                        <button className="average-add-button" type="button" onClick={saveReport} disabled={saving || loading || !selectedMonth}>
                            {saving ? 'Menyimpan...' : 'Simpan Data Bulan Ini'}
                        </button>
                    </div>}
                    </div>
                    </div>
                </div>
            </section>
        </div>
    );
}
