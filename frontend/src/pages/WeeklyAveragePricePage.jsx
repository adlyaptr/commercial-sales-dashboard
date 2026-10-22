import React, { useEffect, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from 'chart.js';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT'];
const regions = ['JAWA BARAT', 'JAWA TENGAH', 'JAWA TIMUR', 'JAWA TENGAH DAN TIMUR'];
const comparisonAreas = [
    { key: 'JAWA BARAT', label: 'Jawa Barat', regions: ['JAWA BARAT'] },
    { key: 'JAWA TENGAH', label: 'Jawa Tengah', regions: ['JAWA TENGAH'] },
    { key: 'JAWA TIMUR', label: 'Jawa Timur', regions: ['JAWA TIMUR'] },
    { key: 'JAWA_TENGAH_DAN_TIMUR', label: 'Jawa Tengah dan Timur', regions: ['JAWA TENGAH DAN TIMUR'] },
    { key: 'ALL_EXCEPT_JATIM', label: 'All Area', regions: [] },
];
const workbookCustomerOrder = [
    'clin', 'mkg', 'oaj', 'shb', 'gtl', 'twk', 'bem', 'tomimoto',
    'niagagaram', 'pcimengger', 'adp', 'bisurcharge', 'stm', 'sma', 'ip',
    'ka', 'ktn', 'hci', 'nni', 'gfrsurcharge', 'gfranca', 'byc', 'hli',
    'dic', 'ksn', 'ami', 'abckogen', 'umi', 'ceres', 'pci84surcharge',
    'pci84', 'indofood', 'asahimassurcharge', 'asahimas', 'fjiksosalmah',
    'altksomasami', 'winglokksoebm', 'psdwira', 'abpsbi', 'kgmksorrs',
    'bdplemb', 'toyoboksoineko', 'citymallwira', 'cisfksorrs',
    'pujlubricant', 'tongjiksogas', 'torabikahf', 'torabikaic', 'swsace',
    'idpksoaae', 'hskksogas', 'spglobal', 'torabikacikupaekajaya',
    'calbeeksobmi', 'spksojes', 'pa', 'gfkulit', 'rb', 'gfatom',
];
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
    'Concord Industry', 'Pentawira (KSO REN)',
];
const pdfCustomerAliases = {
    ptciptalestariideanusa: 'CLIN',
    ptmitrakayagalvanize: 'MKG',
    ptoptimaadhijaya: 'OPTIMA',
    oaj: 'OPTIMA',
    greenpulse: 'GreenPulse',
    concordindustry: 'Concord',
    jiuqitecnologykonjac: 'JIUQI',
    pentawiraksoren: 'Pentawira / REN',
};
const customerOrderAliases = {
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
    ptoptimaadhijaya: 'OPTIMA',
    pentawiraksoren: 'pentawira / ren',
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
const normalizeCustomerIdentity = (value) => {
    const normalizedName = normalizeCustomerOrder(value);
    return normalizeCustomerOrder(pdfCustomerAliases[normalizedName] || value);
};
const canonicalCustomerName = (value) => {
    const normalizedName = normalizeCustomerOrder(value);
    return pdfCustomerAliases[normalizedName] || value;
};
const customerDisplayIdentity = (row) => [
    normalizeCustomerIdentity(row.customer),
    String(row.operator ?? '').trim().toUpperCase(),
].join('|');
function workbookCustomerOrderForMonth(month) {
    const order = [...workbookCustomerOrder];
    if (month >= '2026-03') {
        order.splice(order.indexOf('spksojes'), 1);
        order.push('spksojes');
    }
    const insertAfter = (customer, previousCustomer) => {
        const previousIndex = order.indexOf(previousCustomer);
        if (previousIndex !== -1 && !order.includes(customer)) {
            order.splice(previousIndex + 1, 0, customer);
        }
    };
    if (month >= '2026-06') insertAfter('ksnranca', 'abckogen');
    if (month >= '2026-08') insertAfter('greenpulse', 'adp');
    if (month >= '2026-09') {
        insertAfter('concord', 'asahimas');
        insertAfter('kimiafarmaksoineko', 'swsace');
    }
    return new Map(order.map((customerKey, index) => [customerKey, index]));
}
const workbookCustomerGroups = [
    {
        label: 'DIRECT · Customer <50.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['CLIN', 'MKG', 'OPTIMA', 'SHB', 'GTL', 'TWK', 'BEM', 'TOMIMOTO', 'NIAGA GARAM', 'PCI MENGGER', 'Alia Digital'],
            'JAWA TENGAH': ['CV PA', 'GF KULIT', 'RPI'],
            'JAWA TIMUR': ['Djarum'],
        },
    },
    {
        label: 'DIRECT · Customer 50.001 - 100.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['BI Surcharge', 'BI', 'STM', 'SMA', 'IP', 'KARISMA', 'KTN', 'Honchuan'],
            'JAWA TENGAH': ['RB', 'GF ATOM'],
            'JAWA TIMUR': ['Surya Pamenang (Global)'],
        },
    },
    {
        label: 'DIRECT · Customer 100.001 - 200.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['NNI', 'GFR Surcharge', 'GF RANCAEKEK', 'BYC', 'HLI Green Power', 'Dic Grapichs', 'KSN Maja', 'ATEJA', 'ABC Kogen'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'DIRECT · Customer >200.001 Sm³/bln',
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
            'JAWA TIMUR': ['Pentawira / REN'],
        },
    },
];
const workbookCustomerGroupByRegion = new Map();
const workbookCustomerGroupByCustomer = new Map();
workbookCustomerGroups.forEach((group, groupIndex) => {
    Object.entries(group.regions).forEach(([region, customers]) => {
        if (!workbookCustomerGroupByRegion.has(region)) {
            workbookCustomerGroupByRegion.set(region, new Map());
        }
        customers.forEach((customer) => {
            const customerKey = normalizeCustomerOrder(customer);
            workbookCustomerGroupByRegion.get(region).set(customerKey, groupIndex);
            if (!workbookCustomerGroupByCustomer.has(customerKey)) {
                workbookCustomerGroupByCustomer.set(customerKey, groupIndex);
            }
        });
    });
});
const laterWorkbookCustomerGroups = [
    { region: 'JAWA BARAT', customer: 'greenpulse', fromMonth: '2026-08', groupIndex: 0 },
    { region: 'JAWA BARAT', customer: 'ksnranca', fromMonth: '2026-06', groupIndex: 2 },
    { region: 'JAWA BARAT', customer: 'concord', fromMonth: '2026-09', groupIndex: 3 },
    { region: 'JAWA BARAT', customer: 'kimiafarmaima', fromMonth: '2026-09', groupIndex: 5 },
    { region: 'JAWA TENGAH', customer: 'jiuqi', fromMonth: '2026-04', groupIndex: 6 },
];
const workbookGroupRegionOrder = {
    'JAWA BARAT': 0,
    'JAWA TENGAH': 1,
    'JAWA TIMUR': 2,
    'JAWA TENGAH DAN TIMUR': 3,
};
function workbookGroupForCustomer(row, month) {
    const region = String(row.region ?? '').trim().toUpperCase();
    const customerKey = normalizeCustomerOrder(row.customer);
    let groupIndex;
    if (region === 'JAWA TENGAH DAN TIMUR') {
        groupIndex = {
            cvpa: 0,
            gfkulit: 0,
            rpi: 0,
            rb: 1,
            gfatom: 1,
            hskksogas: 6,
            suryapamenangjes: 6,
            jiuqi: 6,
            suryapamenangglobal: 7,
        }[customerKey];
    }
    const laterGroup = groupIndex == null && laterWorkbookCustomerGroups.find((group) =>
        group.region === region
        && group.customer === customerKey
        && month >= group.fromMonth);
    if (groupIndex == null && laterGroup) groupIndex = laterGroup.groupIndex;
    if (groupIndex == null && region === 'JAWA TENGAH'
        && ['suryapamenangglobal', 'suryapamenangjes'].includes(customerKey)) {
        const isMayOrLater = month >= '2026-05';
        groupIndex = customerKey === 'suryapamenangglobal'
            ? isMayOrLater ? 7 : 6
            : isMayOrLater ? 6 : 7;
    }
    groupIndex ??= workbookCustomerGroupByRegion.get(region)?.get(customerKey)
        ?? (!region ? workbookCustomerGroupByCustomer.get(customerKey) : undefined);
    if (groupIndex == null) {
        const index = 4 * workbookCustomerGroups.length;
        return { index, label: 'Tidak tercantum di file pengguna' };
    }
    const regionIndex = workbookGroupRegionOrder[region] ?? 4;
    const index = regionIndex * workbookCustomerGroups.length + groupIndex;
    const regionLabel = region || 'Wilayah belum ditentukan';
    return {
        index,
        label: `${regionLabel} · ${workbookCustomerGroups[groupIndex].label}`,
    };
}
const formatInteger = (value) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(Number(value ?? 0));
const formatDecimal = (value, digits = 2) => new Intl.NumberFormat('id-ID', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value ?? 0));
const formatDifference = (value) => value < 0
    ? `(${formatInteger(Math.abs(value))})`
    : formatInteger(value);

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
    const { averagePriceMonth, rangeStartDate } = useOutletContext();
    const selectedMonth = averagePriceMonth || rangeStartDate?.slice(0, 7) || '';
    const workbookOrderIndex = workbookCustomerOrderForMonth(selectedMonth);
    const activeComparisonAreas = comparisonAreas
        .filter((area) => {
            if (selectedMonth === '2026-07'
                && ['JAWA TIMUR', 'JAWA_TENGAH_DAN_TIMUR'].includes(area.key)) {
                return false;
            }
            if (selectedMonth === '2026-06'
                && ['JAWA TENGAH', 'JAWA TIMUR'].includes(area.key)) {
                return false;
            }
            if (selectedMonth === '2026-06'
                && area.key === 'JAWA_TENGAH_DAN_TIMUR') {
                return true;
            }
            if (area.key === 'JAWA_TENGAH_DAN_TIMUR'
                && !['2026-06', '2026-07'].includes(selectedMonth)) {
                return false;
            }
            return true;
        })
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
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [customerCatalog, setCustomerCatalog] = useState([]);
    const [selectedCustomerKey, setSelectedCustomerKey] = useState('');
    const [customerEntry, setCustomerEntry] = useState({
        customer: '',
        operator: '',
        region: '',
        price_unit: 'USD_MMBTU',
        price: '',
    });

    useEffect(() => {
        if (!selectedMonth) return undefined;
        let active = true;
        setLoading(true);
        setError('');
        setSelectedCustomerKey('');
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
                setReport(data);
            })
            .catch((requestError) => active && setError(requestError.message))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, [selectedMonth]);

    useEffect(() => {
        let active = true;
        api('/api/customers')
            .then((data) => {
                if (!Array.isArray(data)) {
                    throw new Error('Format daftar customer dari server tidak valid.');
                }
                if (active) setCustomerCatalog(data);
            })
            .catch((requestError) => active && setError(requestError.message));
        return () => { active = false; };
    }, []);

    function selectCustomer(customerKey) {
        const row = report.rows.find((item) => item.customer_key === customerKey);
        setSelectedCustomerKey(row?.customer_key || '');
        setCustomerEntry({
            customer: row ? canonicalCustomerName(row.customer) : '',
            operator: row?.operator || '',
            region: row?.region || '',
            price_unit: row?.price_unit || 'USD_MMBTU',
            price: row?.price_unit === 'IDR_SM3'
                ? row.price_rp_per_sm3 || ''
                : row?.price_usd_per_mmbtu || '',
        });
    }

    function updateCustomerName(value) {
        const normalizedName = normalizeCustomerIdentity(value.trim());
        const matchingRow = report.rows.find((row) =>
            normalizeCustomerIdentity(row.customer) === normalizedName
            || normalizeCustomerIdentity(row.customer_key) === normalizedName);
        if (matchingRow) {
            selectCustomer(matchingRow.customer_key);
            return;
        }
        const matchingCustomer = customerCatalog.find((customer) =>
            normalizeCustomerIdentity(customer.customer_name) === normalizedName
            || normalizeCustomerIdentity(customer.customer_key) === normalizedName);
        setSelectedCustomerKey(matchingCustomer?.customer_key || '');
        setCustomerEntry((current) => ({
            ...current,
            customer: value,
            operator: matchingCustomer?.operator || '',
            region: '',
            price: '',
        }));
    }

    function updateFactor(operator, value) {
        setReport((current) => ({
            ...current,
            operator_factors: { ...current.operator_factors, [operator]: value },
        }));
    }

    function updateExchangeRate(value) {
        setReport((current) => ({
            ...current,
            exchange_rate: value,
        }));
    }

    function updateTarget(area, value) {
        setReport((current) => ({
            ...current,
            targets: { ...current.targets, [area]: value },
        }));
    }

    async function persistReport(nextReport, successMessage) {
        if (!selectedMonth) return;
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
                    exchange_rate: Number(nextReport.exchange_rate || 0),
                    targets: Object.fromEntries(activeComparisonAreas.map(({ key }) => [
                        key,
                        nextReport.targets[key] === '' || nextReport.targets[key] == null
                            ? null
                            : Number(nextReport.targets[key]),
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
            setNotice(successMessage);
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSaving(false);
        }
    }

    async function saveCustomerEntry(event) {
        event.preventDefault();
        const customerName = canonicalCustomerName(customerEntry.customer.trim());
        const selectedRow = report.rows.find((item) => item.customer_key === selectedCustomerKey);
        const normalizedCustomerName = normalizeCustomerIdentity(customerName);
        const namedRows = report.rows.filter((item) =>
            normalizeCustomerIdentity(item.customer) === normalizedCustomerName
            || normalizeCustomerIdentity(item.customer_key) === normalizedCustomerName);
        const row = selectedRow || namedRows.find((item) =>
            !customerEntry.operator || item.operator === customerEntry.operator);
        const catalogCustomer = customerCatalog.find((customer) =>
            customer.customer_key === selectedCustomerKey
            || (normalizeCustomerIdentity(customer.customer_name) === normalizedCustomerName
                && (!row || customer.operator === row.operator)));
        const price = Number(customerEntry.price);
        const operator = row?.operator || catalogCustomer?.operator || customerEntry.operator;
        if (!customerName) {
            setError('Nama customer wajib diisi.');
            return;
        }
        if (!operator || (!row && !catalogCustomer && !operators.includes(operator))) {
            setError('Pilih operator untuk customer baru.');
            return;
        }
        if (!customerEntry.region) {
            setError('Pilih wilayah customer.');
            return;
        }
        if (!Number.isFinite(price) || price <= 0) {
            setError('Harga harus berupa angka lebih besar dari nol.');
            return;
        }

        const customerKey = row?.customer_key
            || catalogCustomer?.customer_key
            || normalizeCustomerOrder(customerName);
        const keyConflict = customerCatalog.find((customer) =>
            customer.customer_key === customerKey
            && normalizeCustomerIdentity(customer.customer_name) !== normalizeCustomerIdentity(customerName));
        if (keyConflict) {
            setError(`Nama customer bertabrakan dengan data master ${keyConflict.customer_name}.`);
            return;
        }
        if (!row && !catalogCustomer) {
            setSaving(true);
            setError('');
            setNotice('');
            try {
                await api('/api/customer-mapping', {
                    method: 'POST',
                    body: { customer: customerName, operator },
                });
                setCustomerCatalog((current) => [
                    ...current,
                    { customer_key: customerKey, customer_name: customerName, operator },
                ]);
            } catch (requestError) {
                setError(requestError.message);
                setSaving(false);
                return;
            }
            setSaving(false);
        }

        const currentRow = row || {
            customer_key: customerKey,
            customer: customerName,
            operator,
            region: '',
            price_unit: 'USD_MMBTU',
            so_sm3: 0,
            actual_sm3: 0,
            sm3: 0,
            sm3_per_mmbtu: Number(report.operator_factors[operator] || 0),
            volume_mmbtu: 0,
            price_usd_per_mmbtu: 0,
            price_rp_per_sm3: 0,
            sm3_override: null,
            mmbtu_override: null,
            total_usd_override: null,
            rupiah_override: null,
            total_usd: 0,
            exchange_rate: Number(report.exchange_rate || 0),
            has_valid_price: false,
            include_in_summary: true,
            rupiah: 0,
        };
        const matchingRows = row
            ? report.rows.filter((item) => customerDisplayIdentity(item) === customerDisplayIdentity(row))
            : [];
        const updatePrice = (item) => {
            const itemPriceChanged = item.price_unit !== customerEntry.price_unit
                || (customerEntry.price_unit === 'IDR_SM3'
                    ? Number(item.price_rp_per_sm3 || 0) !== price
                    : Number(item.price_usd_per_mmbtu || 0) !== price);
            return {
                ...item,
                customer: customerName,
                operator,
                region: customerEntry.region,
                price_unit: customerEntry.price_unit,
                price_usd_per_mmbtu: customerEntry.price_unit === 'USD_MMBTU' ? price : 0,
                price_rp_per_sm3: customerEntry.price_unit === 'IDR_SM3' ? price : 0,
                total_usd_override: itemPriceChanged ? null : item.total_usd_override,
                rupiah_override: itemPriceChanged ? null : item.rupiah_override,
            };
        };
        const updatedRow = updatePrice(currentRow);
        setSelectedCustomerKey(customerKey);
        const nextReport = {
            ...report,
            rows: row
                ? report.rows.map((item) => matchingRows.some((match) => match.customer_key === item.customer_key)
                    ? updatePrice(item)
                    : item)
                : [...report.rows, updatedRow],
        };
        await persistReport(
            nextReport,
            `Data Average Price ${customerName} berhasil disimpan untuk ${monthLabel(selectedMonth)}.`,
        );
    }

    async function saveReport(event) {
        event.preventDefault();
        await persistReport(
            report,
            `Pengaturan Average Price ${monthLabel(selectedMonth)} berhasil disimpan.`,
        );
    }

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
        return {
            ...row,
            customer,
            price_unit: priceUnit,
            sm3,
            volume_mmbtu: volumeMmbtu,
            total_usd: totalUsd,
            rupiah: totalRp,
            workbook_group: workbookGroupForCustomer({ customer, region: row.region }, selectedMonth),
        };
    }).filter((row) => row.sm3_override != null
        || row.has_valid_price
        || (row.price_unit === 'IDR_SM3'
            ? Number(row.price_rp_per_sm3) > 0
            : Number(row.price_usd_per_mmbtu) > 0))
        .map((row, index) => ({ row, index }))
        .sort((left, right) => {
            const groupOrder = left.row.workbook_group.index - right.row.workbook_group.index;
            if (groupOrder !== 0) return groupOrder;
            const leftOrder = workbookOrderIndex.get(normalizeCustomerOrder(left.row.customer_key)) ?? Infinity;
            const rightOrder = workbookOrderIndex.get(normalizeCustomerOrder(right.row.customer_key)) ?? Infinity;
            return leftOrder - rightOrder || left.index - right.index;
        })
        .map(({ row }) => row);
    const displayRows = calculatedRows.reduce((rows, row) => {
        const identity = customerDisplayIdentity(row);
        const matchingRow = rows.find((item) => item.displayIdentity === identity);
        if (!matchingRow) {
            rows.push({
                ...row,
                displayIdentity: identity,
                sourceRows: [row],
            });
            return rows;
        }
        matchingRow.sourceRows.push(row);
        if (!matchingRow.region && row.region) {
            matchingRow.region = row.region;
            matchingRow.workbook_group = row.workbook_group;
        }
        matchingRow.sm3 += row.sm3;
        matchingRow.volume_mmbtu += row.volume_mmbtu;
        matchingRow.total_usd += row.total_usd;
        matchingRow.rupiah += row.rupiah;
        matchingRow.has_valid_price = matchingRow.sourceRows.every((item) => item.has_valid_price);
        matchingRow.include_in_summary = matchingRow.sourceRows.every(
            (item) => item.include_in_summary !== false,
        );
        if (matchingRow.price_unit !== row.price_unit) {
            matchingRow.price_unit = 'MIXED';
        }
        if (matchingRow.price_unit === 'USD_MMBTU') {
            matchingRow.price_usd_per_mmbtu = matchingRow.volume_mmbtu > 0
                ? matchingRow.total_usd / matchingRow.volume_mmbtu
                : 0;
        } else if (matchingRow.price_unit === 'IDR_SM3') {
            matchingRow.price_rp_per_sm3 = matchingRow.sm3 > 0
                ? matchingRow.rupiah / matchingRow.sm3
                : 0;
        }
        return rows;
    }, []).map(({ displayIdentity, ...row }) => row);
    const displayGroups = displayRows.reduce((groups, row) => {
        const currentGroup = groups[groups.length - 1];
        if (!currentGroup || currentGroup.group.index !== row.workbook_group.index) {
            groups.push({ group: row.workbook_group, rows: [row] });
        } else {
            currentGroup.rows.push(row);
        }
        return groups;
    }, []);
    const displayRowNumbers = new Map(displayRows.map((row, index) => [row.customer_key, index + 1]));
    const totals = calculatedRows.filter((row) =>
        row.has_valid_price && row.include_in_summary !== false,
    ).reduce((sum, row) => ({
        sm3: sum.sm3 + row.sm3,
        mmbtu: sum.mmbtu + row.volume_mmbtu,
        usd: sum.usd + row.total_usd,
        rupiah: sum.rupiah + row.rupiah,
    }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
    const averagePriceRpSm3 = totals.sm3 > 0 ? totals.rupiah / totals.sm3 : 0;
    const hasUncalculatedPriceRows = calculatedRows.some((row) =>
        !row.has_valid_price
        && (row.price_unit === 'IDR_SM3'
            ? Number(row.price_rp_per_sm3) > 0
            : Number(row.price_usd_per_mmbtu) > 0),
    );
    const comparisonRows = activeComparisonAreas.map((area) => {
        const eligibleRows = calculatedRows.filter((row) =>
            (area.key === 'ALL_EXCEPT_JATIM'
                ? row.include_in_summary !== false
                : area.regions.includes(row.region))
            && Number(row.actual_sm3 || 0) + Number(row.so_sm3 || 0) > 0
            && (row.price_unit === 'IDR_SM3'
                ? Number(row.price_rp_per_sm3) > 0
                : Number(row.sm3_per_mmbtu) > 0
                    && Number(row.price_usd_per_mmbtu) > 0
                    && Number(report.exchange_rate) > 0));
        const volume = eligibleRows.reduce(
            (sum, row) => sum + Number(row.actual_sm3 || 0) + Number(row.so_sm3 || 0),
            0,
        );
        const rupiah = eligibleRows.reduce((sum, row) => {
            const calculationSm3 = row.sm3;
            const actualSm3 = Number(row.actual_sm3 || 0);
            const prognosisSm3 = actualSm3 + Number(row.so_sm3 || 0);
            const rupiahPerSm3 = calculationSm3 > 0
                ? row.rupiah / calculationSm3
                : row.price_unit === 'IDR_SM3'
                    ? Number(row.price_rp_per_sm3)
                    : Number(row.price_usd_per_mmbtu)
                        / Number(row.sm3_per_mmbtu)
                        * Number(report.exchange_rate);
            return sum + prognosisSm3 * rupiahPerSm3;
        }, 0);
        const targetValue = report.targets[area.key];
        const target = targetValue == null || targetValue === '' ? null : Number(targetValue);
        const prognosis = volume > 0 ? rupiah / volume : null;
        const hasRegionalRows = area.key === 'ALL_EXCEPT_JATIM'
            ? calculatedRows.some((row) => row.include_in_summary !== false)
            : calculatedRows.some((row) => area.regions.includes(row.region));
        return {
            ...area,
            target,
            prognosis,
            hasRegionalRows,
            difference: target != null && prognosis != null ? prognosis - target : null,
        };
    });
    const selectedCustomer = report.rows.find((row) => row.customer_key === selectedCustomerKey);
    const selectedCustomerCatalog = customerCatalog.find((customer) => customer.customer_key === selectedCustomerKey);
    const selectedCustomerOperator = selectedCustomer?.operator || selectedCustomerCatalog?.operator || '';
    const customerNameSuggestions = [...new Map([
        ...pdfCustomerNames,
        ...customerCatalog
            .filter((customer) => !customer.customer_key.startsWith('manualfob-'))
            .map((customer) => customer.customer_name),
        ...report.rows.map((row) => row.customer),
    ].map((name) => {
        const canonicalName = canonicalCustomerName(name);
        return [normalizeCustomerIdentity(canonicalName), canonicalName];
    })).values()];
    const hasUnassignedWorkbookRegions = calculatedRows.some(
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
        <div className="weekly-average-page">
            {error && <div className="notice bad" role="alert">{error}</div>}
            {notice && <div className="notice good" role="status">{notice}</div>}
            {hasUncalculatedPriceRows && (
                <div className="notice" role="status">
                    Beberapa harga sudah tercatat, tetapi belum dapat dihitung karena kurs atau faktor konversi belum tersedia. Baris tersebut tidak masuk total.
                </div>
            )}

            <section className="average-kpi-grid">
                <article className="average-kpi average-kpi-blue"><span className="average-kpi-icon">▤</span><div><small>TOTAL SM³</small><strong>{formatInteger(totals.sm3)}</strong><span>Volume sumber perhitungan</span></div></article>
                <article className="average-kpi average-kpi-green"><span className="average-kpi-icon">◆</span><div><small>TOTAL MMBTU</small><strong>{formatDecimal(totals.mmbtu, 3)}</strong><span>Sm³ ÷ faktor operator</span></div></article>
                <article className="average-kpi average-kpi-blue"><span className="average-kpi-icon">AVG</span><div><small>AVERAGE Rp/Sm³</small><strong>{formatDecimal(averagePriceRpSm3, 2)}</strong><span>Total Rupiah ÷ volume sumber</span></div></article>
            </section>

            <section className="average-data-panel">
                <div className="average-workspace-grid">
                    <div className="average-workspace-column average-workspace-left">
                <div className="average-data-heading">
                    <div className="average-panel-heading">
                        <b>Hasil Perhitungan Average Price</b>
                        <small>{monthLabel(selectedMonth)} · Customer DIRECT tetap masuk total. Baris * dikecualikan dari total Summary.</small>
                    </div>
                </div>
                <form onSubmit={saveReport}>
                    <div className="average-table-wrap average-customer-table-wrap" role="region" aria-label="Tabel data Average Price Customer" tabIndex="0">
                        <table className="average-data-table">
                            <thead><tr><th>No</th><th>Customer</th><th>Operator</th><th>Sm³</th><th>MMBTU</th><th>Harga Efektif</th><th>Total (USD)</th><th>Total (Rp)</th></tr></thead>
                            <tbody>
                                {displayRows.length === 0
                                    ? (
                                        <tr>
                                            <td colSpan="8" className="empty-row">
                                                {loading
                                                    ? 'Memuat data...'
                                                    : report.rows.length === 0
                                                        ? 'Belum ada data sales untuk bulan ini.'
                                                        : 'Belum ada hasil. Pilih customer, isi harga, lalu simpan.'}
                                            </td>
                                        </tr>
                                    )
                                    : displayGroups.map((group) => {
                                        const groupTotals = group.rows
                                            .flatMap((row) => row.sourceRows || [row])
                                            .filter((row) => row.has_valid_price)
                                            .reduce((sum, row) => ({
                                                sm3: sum.sm3 + row.sm3,
                                                mmbtu: sum.mmbtu + row.volume_mmbtu,
                                                usd: sum.usd + row.total_usd,
                                                rupiah: sum.rupiah + row.rupiah,
                                            }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
                                        return <React.Fragment key={group.group.index}>
                                                <tr className="average-workbook-group">
                                                    <th colSpan="8">{group.group.label}</th>
                                                </tr>
                                                {group.rows.map((row) => {
                                                    return <tr key={row.customer_key}>
                                                    <td>{displayRowNumbers.get(row.customer_key)}</td>
                                                    <td>{row.customer}{row.include_in_summary === false ? ' *' : ''}</td>
                                                    <td>{row.operator}</td>
                                                    <td>{formatInteger(row.sm3)}</td>
                                                    <td>{formatDecimal(row.volume_mmbtu, 3)}</td>
                                                    <td>{row.price_unit === 'MIXED'
                                                        ? '—'
                                                        : row.price_unit === 'IDR_SM3'
                                                        ? `Rp ${formatDecimal(row.price_rp_per_sm3, 2)}`
                                                        : `$ ${formatDecimal(row.price_usd_per_mmbtu, 4)}`}</td>
                                                    <td>$ {formatDecimal(row.total_usd, 2)}</td>
                                                    <td>Rp {formatDecimal(row.rupiah, 2)}</td>
                                                </tr>;
                                            })}
                                            <tr className="average-workbook-subtotal">
                                                <th colSpan="3">JUMLAH</th>
                                                <th>{formatInteger(groupTotals.sm3)}</th>
                                                <th>{formatDecimal(groupTotals.mmbtu, 3)}</th>
                                                <th>—</th>
                                                <th>$ {formatDecimal(groupTotals.usd, 2)}</th>
                                                <th>Rp {formatDecimal(groupTotals.rupiah, 2)}</th>
                                            </tr>
                                            <tr className="average-workbook-average">
                                                <th colSpan="3">AVG</th>
                                                <th>—</th>
                                                <th>—</th>
                                                <th>$ {formatDecimal(
                                                    groupTotals.mmbtu > 0
                                                        ? groupTotals.usd / groupTotals.mmbtu
                                                        : 0,
                                                    2,
                                                )}</th>
                                                <th>—</th>
                                                <th>Rp {formatDecimal(
                                                    groupTotals.sm3 > 0
                                                        ? groupTotals.rupiah / groupTotals.sm3
                                                        : 0,
                                                    2,
                                                )}</th>
                                            </tr>
                                        </React.Fragment>;
                                    })}
                            </tbody>
                            {displayRows.length > 0 && <tfoot><tr>
                                <th colSpan="3">TOTAL</th>
                                <th>{formatInteger(totals.sm3)}</th>
                                <th>{formatDecimal(totals.mmbtu, 3)}</th>
                                <th>—</th>
                                <th>$ {formatDecimal(totals.usd, 2)}</th>
                                <th>Rp {formatDecimal(totals.rupiah, 2)}</th>
                            </tr></tfoot>}
                        </table>
                    </div>
                </form>
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
                            placeholder="Ketik nama customer"
                            value={customerEntry.customer}
                            onChange={(event) => updateCustomerName(event.target.value)}
                        />
                        <datalist id="average-customer-options">
                            {customerNameSuggestions.map((customerName) => (
                                <option key={normalizeCustomerOrder(customerName)} value={customerName} />
                            ))}
                        </datalist>
                    </label>
                    <label>
                        Operator
                        {selectedCustomerOperator
                            ? <input readOnly value={selectedCustomerOperator} />
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
                        <select
                            required
                            value={customerEntry.region}
                            onChange={(event) => setCustomerEntry((current) => ({
                                ...current,
                                region: event.target.value,
                            }))}
                        >
                            <option value="">Pilih wilayah</option>
                            {regions.map((region) => <option key={region} value={region}>{region}</option>)}
                        </select>
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
                        <button className="primary" type="submit" disabled={saving || loading || !selectedMonth}>
                            {saving ? 'Menyimpan...' : 'Simpan Harga'}
                        </button>
                    </div>
                </form>
                <form onSubmit={saveReport}>
                    <div className="average-data-heading average-conversion-heading">
                        <div className="average-panel-heading">
                            <b>Faktor Konversi Operator dan Kurs</b>
                            <small>Faktor dan kurs berlaku untuk seluruh customer pada {monthLabel(selectedMonth)}.</small>
                        </div>
                        <label className="average-filter-field">
                            <span>Kurs Rp/USD</span>
                            <input aria-label="Kurs Rupiah per USD" type="number" min="0" step="1" value={report.exchange_rate || ''} onChange={(event) => updateExchangeRate(event.target.value)} />
                        </label>
                    </div>
                    <div className="average-table-wrap average-conversion-wrap">
                        <table className="average-data-table average-conversion-table">
                            <thead><tr><th>No</th><th>Operator</th><th>Faktor Sm³ per MMBTU</th><th>Contoh</th></tr></thead>
                            <tbody>{operators.map((operator, index) => <tr key={operator}>
                                <td>{index + 1}</td>
                                <td>{operator}</td>
                                <td><input aria-label={`Faktor konversi ${operator}`} type="number" min="0" step="any" value={report.operator_factors[operator] || ''} onChange={(event) => updateFactor(operator, event.target.value)} /></td>
                                <td>MMBTU = Sm³ ÷ faktor</td>
                            </tr>)}</tbody>
                        </table>
                    </div>
                </form>
                    </div>

                    <div className="average-workspace-column average-workspace-right">
                    <form onSubmit={saveReport}>
                    <div className="average-data-heading average-comparison-heading">
                        <div className="average-panel-heading">
                            <b>Target Harga dan Prognosa (Rp/Sm³)</b>
                            <small>{monthLabel(selectedMonth)} · Prognosa menggunakan (Sm³ actual customer + SO) · Selisih = Prognosa − Target</small>
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
                                        <input
                                            aria-label={`Target harga ${row.label}`}
                                            type="number"
                                            min="0"
                                            step="1"
                                            placeholder="Input target"
                                            value={report.targets[row.key] ?? ''}
                                            onChange={(event) => updateTarget(row.key, event.target.value)}
                                        />
                                    </td>
                                    <td>{row.prognosis == null
                                        ? hasUnassignedWorkbookRegions && !row.hasRegionalRows
                                            ? 'Tidak ada data wilayah'
                                            : '—'
                                        : formatInteger(row.prognosis)}</td>
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
                    <div className="average-toolbar average-monthly-save">
                        <button className="average-add-button" type="submit" disabled={saving || loading || !selectedMonth}>
                            {saving ? 'Menyimpan...' : 'Simpan Data Bulan Ini'}
                        </button>
                    </div>
                    </form>
                    </div>
                </div>
            </section>
        </div>
    );
}
