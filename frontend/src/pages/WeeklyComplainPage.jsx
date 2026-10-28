import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../api";

const STORAGE_KEY = "daily-sales-weekly-complaints-v1";
const COMPLAINT_TYPES = [
  "Keterlambatan Pekerjaan",
  "Keterlambatan Pengiriman",
  "Perilaku Pekerja",
  "Keselamatan Kerja",
  "Kualitas Suplai Gas CNG",
  "Lainnya",
];

const emptyComplaint = {
  date: "2026-09-25",
  customer: "",
  summary: "",
  followUp: "",
  type: COMPLAINT_TYPES[0],
  priority: "Normal",
  status: "Open",
  statusChangedAt: "",
  resolution: "",
};

function readLegacyComplaints() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return [];

  const parsed = JSON.parse(saved);
  if (!Array.isArray(parsed)) {
    throw new Error("Format complain lama di browser tidak valid.");
  }
  return parsed;
}

function formatDate(date) {
  if (!date) return "-";
  const d = new Date(`${date}T00:00:00`);
  return d.toLocaleDateString("id-ID", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function formatClosedDate(value) {
  if (!value) return "Belum ditutup";
  return formatDate(String(value).slice(0, 10));
}

function Icon({ name }) {
  const paths = {
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    message: <><path d="M21 11.5a8.5 8.5 0 0 1-12.9 7.3L3 20l1.2-4.3A8.5 8.5 0 1 1 21 11.5Z"/><path d="M8 10h8M8 14h6"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    edit: <><path d="m15 5 4 4M4 20l4-.8L19 8a2.1 2.1 0 0 0-3-3L5 16l-1 4Z"/></>,
  };

  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

function ComplaintField({ label, value, onChange, multiline = false }) {
  return (
    <label className="complaint-field">
      <span>{label}</span>
      {multiline ? (
        <textarea value={value} onChange={onChange} rows={3} />
      ) : (
        <input value={value} onChange={onChange} />
      )}
    </label>
  );
}

export default function WeeklyComplainPage() {
  const { rangeStartDate, rangeEndDate } = useOutletContext();
  const [complaints, setComplaints] = useState([]);
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeBad, setNoticeBad] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadComplaints() {
      setLoading(true);
      try {
        let result = await api("/api/complaints");
        if (!Array.isArray(result)) {
          throw new Error("Format data complain dari server tidak valid.");
        }

        const legacy = readLegacyComplaints();
        if (legacy.length > 0) {
          const migration = await api("/api/complaints/legacy-import", {
            method: "POST",
            body: { complaints: legacy },
          });
          localStorage.removeItem(STORAGE_KEY);
          result = await api("/api/complaints");
          if (active && migration.imported > 0) {
            setNotice(`${migration.imported} complain lama berhasil dipindahkan ke server.`);
          }
        }

        if (active) {
          setComplaints(result);
          setNoticeBad(false);
        }
      } catch (error) {
        if (active) {
          setNotice(error.message || "Data complain gagal dimuat.");
          setNoticeBad(true);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadComplaints();
    return () => { active = false; };
  }, []);

  const visibleComplaints = useMemo(
    () => complaints.filter((item) =>
      item.date >= rangeStartDate && item.date <= rangeEndDate
    ),
    [complaints, rangeStartDate, rangeEndDate]
  );

  const total = visibleComplaints.length;
  const openCount = visibleComplaints.filter(
    (item) => item.status === "Open"
  ).length;
  const closedCount = visibleComplaints.filter(
    (item) => item.status === "Closed"
  ).length;
  const monitoringCount = visibleComplaints.filter(
    (item) => item.status === "Monitoring"
  ).length;

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 3000);
    return () => clearTimeout(timer);
  }, [notice]);

  function addComplaint() {
    setEditing({ ...emptyComplaint, id: null, date: rangeStartDate || emptyComplaint.date });
    setShowForm(true);
  }

  function editComplaint(item) {
    setEditing({
      ...item,
      statusChangedAt: String(item.statusChangedAt || "").slice(0, 10),
    });
    setShowForm(true);
  }

  function updateField(field, value) {
    setEditing((current) => ({ ...current, [field]: value }));
  }

  async function submitComplaint(event) {
    event.preventDefault();

    if (!editing.customer.trim() || !editing.summary.trim()) {
      setNotice("Nama customer dan ringkasan keluhan wajib diisi.");
      setNoticeBad(true);
      return;
    }

    setSaving(true);
    try {
      const isEditing = Number.isInteger(editing.id);
      const saved = await api(
        isEditing ? `/api/complaints/${editing.id}` : "/api/complaints",
        {
          method: isEditing ? "PUT" : "POST",
          body: editing,
        }
      );
      setComplaints((current) => isEditing
        ? current.map((item) => item.id === saved.id ? saved : item)
        : [saved, ...current]);
      setShowForm(false);
      setEditing(null);
      setNotice("Complain berhasil disimpan ke server.");
      setNoticeBad(false);
    } catch (error) {
      setNotice(error.message || "Complain gagal disimpan.");
      setNoticeBad(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="complain-page">
      <div className="complain-toolbar">
        <div className="complain-heading">
        </div>

        
      </div>

      {notice && <div className={`complain-notice${noticeBad ? " bad" : ""}`} role={noticeBad ? "alert" : "status"}>{notice}</div>}

      <section className="complain-kpis">
        <div className="complain-kpi">
          <div className="complain-kpi-icon green"><Icon name="message" /></div>
          <div><span>Total Complain</span><strong>{total}</strong></div>
        </div>
        <div className="complain-kpi">
          <div className="complain-kpi-icon yellow"><Icon name="clock" /></div>
          <div><span>Open</span><strong>{openCount}</strong></div>
        </div>
        <div className="complain-kpi">
          <div className="complain-kpi-icon mint"><Icon name="check" /></div>
          <div><span>Closed</span><strong>{closedCount}</strong></div>
        </div>
        <div className="complain-kpi">
          <div className="complain-kpi-icon monitoring"><Icon name="clock" /></div>
          <div><span>Monitoring</span><strong>{monitoringCount}</strong></div>
        </div>
      </section>
<div className="complain-actions">
  <button className="complain-btn complain-btn-green" onClick={addComplaint}>
            <Icon name="plus" /> Tambah Complain
          </button>
        </div>
      {showForm && editing && (
        <form className="complain-form" onSubmit={submitComplaint}>
          <div className="complain-form-header">
            <h2>{editing.id ? "Edit Complain" : "Tambah Complain"}</h2>
            <button type="button" className="complain-close" onClick={() => setShowForm(false)}>×</button>
          </div>

          <div className="complain-form-grid">
            <label className="complaint-field">
              <span>Tanggal</span>
              <input type="date" value={editing.date} onChange={(e) => updateField("date", e.target.value)} required />
            </label>
            <ComplaintField label="Nama Customer" value={editing.customer} onChange={(e) => updateField("customer", e.target.value)} />
            <label className="complaint-field">
              <span>Jenis Keluhan</span>
              <select value={editing.type} onChange={(e) => updateField("type", e.target.value)}>
                {[...new Set([editing.type, ...COMPLAINT_TYPES])].map((type) => <option key={type}>{type}</option>)}
              </select>
            </label>
            <label className="complaint-field">
              <span>Prioritas</span>
              <select value={editing.priority} onChange={(e) => updateField("priority", e.target.value)}>
                <option>Normal</option><option>Tinggi</option><option>Rendah</option>
              </select>
            </label>
            <label className="complaint-field">
              <span>Status</span>
              <select value={editing.status} onChange={(e) => updateField("status", e.target.value)}>
                <option>Open</option><option>Closed</option><option>Monitoring</option>
              </select>
            </label>
            {editing.status === "Closed" && (
              <label className="complaint-field">
                <span>Tanggal Closed</span>
                <input
                  type="date"
                  value={editing.statusChangedAt || ""}
                  onChange={(e) => updateField("statusChangedAt", e.target.value)}
                  required
                />
              </label>
            )}
            <ComplaintField label="Ringkasan Keluhan" value={editing.summary} multiline onChange={(e) => updateField("summary", e.target.value)} />
            <ComplaintField label="Tindak Lanjut" value={editing.followUp} multiline onChange={(e) => updateField("followUp", e.target.value)} />
            <ComplaintField label="Catatan Penyelesaian" value={editing.resolution} multiline onChange={(e) => updateField("resolution", e.target.value)} />
          </div>

          <div className="complain-form-actions">
            <button type="button" className="complain-btn complain-btn-light" onClick={() => setShowForm(false)}>Batal</button>
            <button type="submit" className="complain-btn complain-btn-blue" disabled={saving}>{saving ? "Menyimpan..." : "Simpan Data"}</button>
          </div>
        </form>
      )}

      <section className="complain-list">
        {loading ? (
          <div className="complain-empty"><p>Memuat data complain...</p></div>
        ) : visibleComplaints.length === 0 ? (
          <div className="complain-empty">
            <Icon name="message" />
            <h3>Belum ada complain</h3>
            <p>Tidak ada keluhan pada rentang tanggal yang dipilih.</p>
          </div>
        ) : visibleComplaints.map((item, index) => (
          <article className="complaint-card" key={item.id}>
            <div className="complaint-timeline">
              <div className="complaint-number">{index + 1}</div>
              <div className="complaint-timeline-line" />
            </div>

            <div className="complaint-meta">
              <div className="complaint-date"><Icon name="calendar" /> {formatDate(item.date)}</div>
              <span className={`complaint-status ${item.status.toLowerCase()}`}>{item.status}</span>
              <div className="complaint-customer"><Icon name="user" /><div><small>Customer</small><strong>{item.customer}</strong></div></div>
            </div>

            <div className="complaint-detail">
              <div className="complaint-detail-grid">
                <div className="complaint-detail-section">
                  <div className="complaint-section-title">Ringkasan Keluhan</div>
                  <p>{item.summary || "-"}</p>
                </div>
                <div className="complaint-detail-section">
                  <div className="complaint-section-title">Tindak Lanjut / Status</div>
                  <p>{item.followUp || "-"}</p>
                </div>
              </div>

              <div className="complaint-bottom-grid">
                <div><small>Jenis Keluhan</small><span className="complaint-tag">{item.type}</span></div>
                <div><small>Prioritas</small><span className={`complaint-tag priority-${item.priority.toLowerCase()}`}>{item.priority}</span></div>
                <div><small>Status</small><span className={`complaint-status ${item.status.toLowerCase()}`}>{item.status}</span></div>
                <div className="complaint-status-date"><small>Tanggal Closed</small><span>{formatClosedDate(item.statusChangedAt)}</span></div>
                <div className="complaint-resolution"><small>Catatan Penyelesaian</small><p>{item.resolution || "-"}</p></div>
                <button className="complaint-edit" type="button" title="Edit complain" onClick={() => editComplaint(item)}><Icon name="edit" /></button>
              </div>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
