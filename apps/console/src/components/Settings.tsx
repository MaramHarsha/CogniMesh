import { Server, User, Plug } from 'lucide-react';

const SERVICE_ENDPOINTS: { name: string; url: string }[] = [
  { name: 'Object Registry', url: 'http://localhost:8000' },
  { name: 'Object Query Service', url: 'http://localhost:8060' },
  { name: 'Quality Control', url: 'http://localhost:8070' },
  { name: 'App Control', url: 'http://localhost:8090' },
];

export function Settings() {
  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Console configuration and connected control-plane services.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '24px' }}>
        <div className="glass-card">
          <h3 style={{ fontSize: '16px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <User size={18} color="var(--accent-primary)" /> Development Identity
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Actor</span>
              <span style={{ fontFamily: 'monospace' }}>console</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Roles</span>
              <span className="badge badge-purple">platform_admin</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Purpose</span>
              <span style={{ fontFamily: 'monospace' }}>metadata_administration</span>
            </div>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '16px' }}>
            Dev auth headers are injected by the Vite proxy and never shipped in the browser bundle.
          </p>
        </div>

        <div className="glass-card">
          <h3 style={{ fontSize: '16px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={18} color="var(--accent-primary)" /> Connected Services
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {SERVICE_ENDPOINTS.map((svc) => (
              <div key={svc.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '14px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Plug size={14} color="var(--text-secondary)" /> {svc.name}
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: '12px', color: 'var(--text-secondary)' }}>{svc.url}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
