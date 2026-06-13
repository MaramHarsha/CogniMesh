import { useMemo, type ReactNode } from 'react';
import { Activity, Boxes, Database, ShieldCheck } from 'lucide-react';
import { getAnalytics } from '../api';

function BarChart({ data, color }: { data: { label: string; value: number }[]; color: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {data.map((d) => (
        <div key={d.label}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '6px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>{d.label}</span>
            <span style={{ fontWeight: 600 }}>{d.value}</span>
          </div>
          <div style={{ height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden' }}>
            <div style={{ width: `${(d.value / max) * 100}%`, height: '100%', background: color, borderRadius: '6px', transition: 'width 0.5s ease' }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function MetricTile({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) {
  return (
    <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
      <div style={{ background: 'rgba(99, 102, 241, 0.1)', padding: '12px', borderRadius: '12px' }}>{icon}</div>
      <div>
        <div style={{ fontSize: '28px', fontWeight: 700, lineHeight: 1.1 }}>{value}</div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{label}</div>
      </div>
    </div>
  );
}

export function Analytics() {
  const summary = useMemo(() => getAnalytics(), []);

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-subtitle">Aggregated metrics and saved analyses across the object layer.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '24px', marginBottom: '24px' }}>
        <MetricTile icon={<Boxes size={24} color="var(--accent-primary)" />} label="Object Types" value={summary.totalObjectTypes} />
        <MetricTile icon={<Database size={24} color="var(--accent-primary)" />} label="Object Instances" value={summary.totalInstances} />
        <MetricTile icon={<ShieldCheck size={24} color="var(--accent-primary)" />} label="Contracts Passing" value="98%" />
        <MetricTile icon={<Activity size={24} color="var(--accent-primary)" />} label="Active Pipelines" value={3} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '24px' }}>
        <div className="glass-card">
          <h3 style={{ fontSize: '16px', marginBottom: '20px' }}>Employees by Department</h3>
          <BarChart data={summary.employeesByDepartment} color="var(--accent-primary)" />
        </div>
        <div className="glass-card">
          <h3 style={{ fontSize: '16px', marginBottom: '20px' }}>Employee Status Breakdown</h3>
          <BarChart data={summary.statusBreakdown} color="var(--accent-secondary)" />
        </div>
      </div>
    </div>
  );
}
