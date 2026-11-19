import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import '../cooperation.css';

const exampleContracts = [
    {
        customer: 'UD Berkah Jaya Abadi',
        region: 'Jateng',
        number: 'PKS-003/2023',
        type: 'Kontrak',
        startDate: '01 Okt 2023',
        endDate: '30 Sep 2026',
        days: -50,
        status: 'ended',
        pic: 'Dewi',
    },
    {
        customer: 'CV Maju Bersama Logistik',
        region: 'Jabar',
        number: 'PKS-002/2024/Amd-2',
        type: 'Amendemen 2',
        startDate: '15 Des 2024',
        endDate: '14 Des 2026',
        days: 25,
        status: 'active',
        pic: 'Budi',
    },
    {
        customer: 'PT Karya Mitra Utama',
        region: 'Jatim',
        number: 'PKS-007/2025/Amd-1',
        type: 'Amendemen 1',
        startDate: '01 Jan 2026',
        endDate: '31 Des 2026',
        days: 42,
        status: 'active',
        pic: 'Sari',
    },
    {
        customer: 'PT Nusantara Retail Sejahtera',
        region: 'Jabar',
        number: 'PKS-014/2025',
        type: 'Kontrak',
        startDate: '01 Feb 2025',
        endDate: '31 Jan 2027',
        days: 73,
        status: 'active',
        pic: 'Budi',
    },
    {
        customer: 'PT Tirta Energi Nusantara',
        region: 'Jatim',
        number: 'PKS-011/2025',
        type: 'Kontrak',
        startDate: '01 Jan 2025',
        endDate: '28 Feb 2027',
        days: 101,
        status: 'active',
        pic: 'Andi',
    },
    {
        customer: 'PT Sinar Teknologi',
        region: 'Jateng',
        number: 'PKS-021/2026',
        type: 'Kontrak',
        startDate: '01 Mar 2026',
        endDate: '28 Feb 2028',
        days: 466,
        status: 'active',
        pic: 'Dewi',
    },
    {
        customer: 'PT Karya Pangan Sejahtera',
        region: 'Jabar',
        number: 'PKS-018/2026',
        type: 'Kontrak',
        startDate: '01 Jun 2026',
        endDate: '31 Mei 2028',
        days: 558,
        status: 'active',
        pic: 'Andi',
    },
];

const statusLabels = {
    active: 'Aktif',
    ended: 'Berakhir',
};

const statusFilters = [
    { key: 'all', label: 'Semua' },
    { key: 'active', label: 'Aktif' },
    { key: 'soon', label: 'Segera berakhir' },
    { key: 'ended', label: 'Berakhir' },
];

const exampleProposals = [
    {
        customer: 'PT Nusantara Retail Sejahtera',
        number: 'PKS-014/2025',
        endDate: '31 Jan 2027',
        region: 'Jabar',
        pic: 'Budi',
    },
    {
        customer: 'CV Maju Bersama Logistik',
        number: 'PKS-002/2024/Amd-2',
        endDate: '14 Des 2026',
        region: 'Jabar',
        pic: 'Budi',
    },
];

function ExampleNotice() {
    return (
        <div className="cooperation-example-note" role="note">
            <span aria-hidden="true">i</span>
            Pratinjau desain — sumber spreadsheet/database belum ditetapkan. Data di halaman ini hanya contoh; sinkronisasi otomatis belum aktif.
        </div>
    );
}

function MetricCard({ label, value, caption, tone }) {
    return (
        <article className={`cooperation-metric ${tone || ''}`}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{caption}</small>
        </article>
    );
}

function PageHeader({ eyebrow, title, description }) {
    return (
        <header className="cooperation-page-heading">
            <div>
                <p className="cooperation-eyebrow">{eyebrow}</p>
                <h1>{title}</h1>
                <p>{description}</p>
            </div>
        </header>
    );
}

function CooperationList({ onShowNotice }) {
    const [activeFilter, setActiveFilter] = useState('all');
    const [search, setSearch] = useState('');
    const [region, setRegion] = useState('all');
    const [kind, setKind] = useState('all');
    const [pic, setPic] = useState('all');
    const [expiry, setExpiry] = useState('all');
    const counts = useMemo(() => exampleContracts.reduce((result, contract) => {
        result[contract.status] += 1;
        if (contract.status === 'active' && contract.days >= 0 && contract.days <= 90) result.soon += 1;
        result.all += 1;
        return result;
    }, { all: 0, active: 0, soon: 0, ended: 0 }), []);
    const rows = useMemo(() => exampleContracts.filter((contract) => {
        const query = search.trim().toLocaleLowerCase('id-ID');
        const matchesText = !query
            || `${contract.customer} ${contract.number}`.toLocaleLowerCase('id-ID').includes(query);
        const matchesStatus = activeFilter === 'all'
            || (activeFilter === 'soon' && contract.status === 'active' && contract.days >= 0 && contract.days <= 90)
            || contract.status === activeFilter;
        const matchesRegion = region === 'all' || contract.region === region;
        const matchesKind = kind === 'all' || contract.type.toLowerCase().includes(kind);
        const matchesPic = pic === 'all' || contract.pic === pic;
        const matchesExpiry = expiry === 'all'
            || (expiry === '30' && contract.days >= 0 && contract.days <= 30)
            || (expiry === '90' && contract.days >= 0 && contract.days <= 90)
            || (expiry === 'expired' && contract.days < 0);
        return matchesText && matchesStatus && matchesRegion && matchesKind && matchesPic && matchesExpiry;
    }), [activeFilter, expiry, kind, pic, region, search]);

    return (
        <section className="cooperation-page">
            <ExampleNotice />

            <section className="cooperation-metrics" aria-label="Ringkasan kerja sama">
                <MetricCard label="TOTAL KONTRAK" value="7" caption="Data contoh" tone="blue" />
                <MetricCard label="AKTIF" value="6" caption="Tanggal berakhir belum lewat" tone="green" />
                <MetricCard label="SEGERA BERAKHIR" value="3" caption="Sisa 90 hari atau kurang" tone="orange" />
                <MetricCard label="BERAKHIR" value="1" caption="Perlu tindak lanjut" tone="red" />
            </section>

            <section className="cooperation-panel cooperation-register">
                <div className="cooperation-status-tabs" aria-label="Filter status kerja sama">
                    {statusFilters.map((filter) => (
                        <button
                            key={filter.key}
                            type="button"
                            className={activeFilter === filter.key ? 'active' : ''}
                            aria-pressed={activeFilter === filter.key}
                            onClick={() => setActiveFilter(filter.key)}
                        >
                            {filter.label} <span>{counts[filter.key]}</span>
                        </button>
                    ))}
                </div>
                <div className="cooperation-filters">
                    <label className="cooperation-search">
                        <span className="sr-only">Cari customer atau nomor dokumen</span>
                        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nama customer atau nomor dokumen" />
                    </label>
                    <label>
                        <span className="sr-only">Wilayah</span>
                        <select value={region} onChange={(event) => setRegion(event.target.value)}>
                            <option value="all">Semua wilayah</option>
                            <option value="Jabar">Jabar</option>
                            <option value="Jateng">Jateng</option>
                            <option value="Jatim">Jatim</option>
                        </select>
                    </label>
                    <label>
                        <span className="sr-only">Jenis dokumen</span>
                        <select value={kind} onChange={(event) => setKind(event.target.value)}>
                            <option value="all">Semua jenis</option>
                            <option value="kontrak">Kontrak</option>
                            <option value="amendemen">Amendemen</option>
                        </select>
                    </label>
                    <label>
                        <span className="sr-only">PIC</span>
                        <select value={pic} onChange={(event) => setPic(event.target.value)}>
                            <option value="all">Semua PIC</option>
                            <option value="Budi">Budi</option>
                            <option value="Dewi">Dewi</option>
                            <option value="Sari">Sari</option>
                            <option value="Andi">Andi</option>
                        </select>
                    </label>
                    <label>
                        <span className="sr-only">Sisa masa berlaku</span>
                        <select value={expiry} onChange={(event) => setExpiry(event.target.value)}>
                            <option value="all">Semua waktu</option>
                            <option value="30">≤ 30 hari</option>
                            <option value="90">≤ 90 hari</option>
                            <option value="expired">Sudah berakhir</option>
                        </select>
                    </label>
                </div>
                <div className="cooperation-table-scroll">
                    <table className="cooperation-table">
                        <thead>
                            <tr>
                                <th>Customer</th>
                                <th>Wilayah</th>
                                <th>No. Dokumen</th>
                                <th>Jenis</th>
                                <th>Masa berlaku</th>
                                <th>Sisa hari</th>
                                <th>Status</th>
                                <th>PIC</th>
                                <th>Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((contract) => (
                                <tr key={contract.number}>
                                    <td><strong>{contract.customer}</strong></td>
                                    <td>{contract.region}</td>
                                    <td>{contract.number}</td>
                                    <td>{contract.type}</td>
                                    <td>{contract.startDate}<br /><span className="cooperation-muted">– {contract.endDate}</span></td>
                                    <td className={contract.days <= 30 ? 'cooperation-days critical' : contract.days <= 90 ? 'cooperation-days soon' : 'cooperation-days'}>
                                        {contract.days < 0 ? `Lewat ${Math.abs(contract.days)} hari` : `${contract.days} hari`}
                                    </td>
                                    <td><span className={`cooperation-status ${contract.status}`}>{statusLabels[contract.status]}</span></td>
                                    <td>{contract.pic}</td>
                                    <td>
                                        <button className="cooperation-link-button" type="button" onClick={() => onShowNotice('Detail kontrak akan tersedia setelah sumber spreadsheet/database ditetapkan.')}>
                                            Detail
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {rows.length === 0 && (
                                <tr><td className="cooperation-empty" colSpan="9">Tidak ada dokumen yang sesuai dengan filter.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="cooperation-table-foot">
                    <span>Menampilkan {rows.length} dari {exampleContracts.length} data contoh</span>
                    <span>Filter dapat digunakan pada pratinjau ini</span>
                </div>
            </section>
        </section>
    );
}

function ExpiryDashboard({ onShowNotice }) {
    const bars = [
        ['Des 2026', 2],
        ['Jan 2027', 1],
        ['Feb 2027', 1],
        ['Mar 2027', 0],
        ['Apr 2027', 0],
        ['Mei 2027', 0],
    ];
    const attention = [
        { customer: 'UD Berkah Jaya Abadi', number: 'PKS-003/2023', info: 'Berakhir · lewat 50 hari', action: 'Lihat detail', tone: 'red' },
        { customer: 'CV Maju Bersama Logistik', number: 'PKS-002/2024/Amd-2', info: 'Aktif · sisa 25 hari', action: 'Lihat detail', tone: 'orange' },
        { customer: 'PT Nusantara Retail Sejahtera', number: 'PKS-014/2025', info: 'Aktif · sisa 73 hari', action: 'Lihat detail', tone: 'yellow' },
    ];

    return (
        <section className="cooperation-page">
            <ExampleNotice />
            <section className="cooperation-metrics" aria-label="Ringkasan masa berlaku">
                <MetricCard label="TOTAL KONTRAK" value="7" caption="Data contoh" tone="blue" />
                <MetricCard label="AKTIF" value="6" caption="Tanggal berakhir belum lewat" tone="green" />
                <MetricCard label="SEGERA BERAKHIR" value="3" caption="Sisa 90 hari atau kurang" tone="orange" />
                <MetricCard label="BERAKHIR" value="1" caption="Perlu tindak lanjut" tone="red" />
            </section>

            <div className="cooperation-expiry-grid">
                <section className="cooperation-panel cooperation-chart-panel">
                    <div className="cooperation-panel-heading"><h2>Dokumen berakhir per bulan</h2><span>7 dokumen contoh</span></div>
                    <div className="cooperation-bars" role="img" aria-label="Grafik jumlah dokumen berakhir per bulan">
                        {bars.map(([month, value]) => (
                            <div className="cooperation-bar-column" key={month}>
                                <strong>{value}</strong>
                                <div className="cooperation-bar-track"><span style={{ height: `${value ? Math.max(value * 46, 22) : 3}px` }} /></div>
                                <small>{month}</small>
                            </div>
                        ))}
                    </div>
                </section>
                <section className="cooperation-panel cooperation-status-panel">
                    <div className="cooperation-panel-heading"><h2>Komposisi status</h2><span>Per 19 Nov 2026</span></div>
                    <div className="cooperation-donut-layout">
                        <div className="cooperation-donut" role="img" aria-label="6 aktif, 1 berakhir">
                            <div><small>Total dokumen</small><strong>7</strong></div>
                        </div>
                        <div className="cooperation-legend">
                            {[
                                ['active', 'Aktif', '6 (85,7%)'],
                                ['ended', 'Berakhir', '1 (14,3%)'],
                            ].map(([tone, label, value]) => (
                                <div key={tone}><i className={tone} /><span>{label}</span><strong>{value}</strong></div>
                            ))}
                        </div>
                    </div>
                </section>
                <section className="cooperation-panel cooperation-attention-panel">
                    <div className="cooperation-panel-heading"><h2>Perlu tindakan</h2><button type="button" onClick={() => onShowNotice('Daftar tindakan akan terhubung ke data kerja sama.')}>Lihat semua</button></div>
                    <div className="cooperation-attention-list">
                        {attention.map((item) => (
                            <article key={item.number}>
                                <div><strong>{item.customer}</strong><small>{item.number} · {item.info}</small></div>
                                <span className={`cooperation-status ${item.tone}`}>{item.info.split(' · ')[0]}</span>
                                <button className="cooperation-link-button" type="button" onClick={() => onShowNotice('Detail kontrak akan tersedia setelah sumber spreadsheet/database ditetapkan.')}>{item.action}</button>
                            </article>
                        ))}
                    </div>
                </section>
                <section className="cooperation-panel cooperation-reminders-panel">
                    <div className="cooperation-panel-heading"><h2>Jadwal notifikasi</h2><span>Dalam aplikasi</span></div>
                    {[
                        ['H-30', 'CV Maju Bersama Logistik', 'PKS-002/2024/Amd-2', 'red'],
                        ['H-60', 'PT Karya Mitra Utama', 'PKS-007/2025/Amd-1', 'orange'],
                        ['H-90', 'PT Nusantara Retail Sejahtera', 'PKS-014/2025', 'green'],
                    ].map(([days, customer, number, tone]) => (
                        <article className={`cooperation-reminder ${tone}`} key={days}>
                            <strong>{days} <span>(1 dokumen)</span></strong>
                            <small>{customer}</small>
                            <em>{number}</em>
                        </article>
                    ))}
                </section>
            </div>
        </section>
    );
}

export default function CooperationPage() {
    const location = useLocation();
    const navigate = useNavigate();
    const [notice, setNotice] = useState('');
    const isExpiry = location.pathname.endsWith('/masa-berlaku');

    function showNotice(message) {
        setNotice(message);
        window.setTimeout(() => setNotice(''), 5000);
    }

    return (
        <div className="cooperation-workspace">
            <nav className="cooperation-tabs" aria-label="Navigasi kerja sama">
                <button type="button" className={!isExpiry ? 'active' : ''} onClick={() => navigate('/kerja-sama')}>Daftar kerja sama</button>
                <button type="button" className={isExpiry ? 'active' : ''} onClick={() => navigate('/kerja-sama/masa-berlaku')}>Masa berlaku</button>
            </nav>
            {notice && <div className="cooperation-demo-notice" role="status">{notice}</div>}
            {isExpiry
                ? <ExpiryDashboard onShowNotice={showNotice} />
                : <CooperationList onShowNotice={showNotice} />}
        </div>
    );
}
