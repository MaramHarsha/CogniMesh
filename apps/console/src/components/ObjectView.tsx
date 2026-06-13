import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, GitMerge, Activity, Link as LinkIcon, Shield, FileText } from 'lucide-react';
import { getObject, namespaceForType, type ObjectRecord } from '../api';

export function ObjectView() {
  const { objectType, id } = useParams();
  const [loading, setLoading] = useState(true);
  const [record, setRecord] = useState<ObjectRecord | undefined>(undefined);

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      setRecord(getObject(objectType ?? '', id ?? ''));
      setLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [objectType, id]);

  if (loading) {
    return <div style={{ padding: '40px', color: 'var(--text-secondary)' }}>Loading object details...</div>;
  }

  if (!record) {
    return (
      <div className="animate-fade-in">
        <div style={{ marginBottom: '24px' }}>
          <Link to="/explorer" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}>
            <ArrowLeft size={16} /> Back to Explorer
          </Link>
        </div>
        <div className="glass-card" style={{ textAlign: 'center', padding: '60px' }}>
          <h2 style={{ marginBottom: '8px' }}>Object not found</h2>
          <p style={{ color: 'var(--text-secondary)' }}>
            No {objectType} object with id <span style={{ fontFamily: 'monospace' }}>{id}</span> exists.
          </p>
        </div>
      </div>
    );
  }

  const namespace = namespaceForType(objectType ?? '');

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '24px' }}>
        <Link to={`/explorer?type=${objectType}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}>
          <ArrowLeft size={16} /> Back to Explorer
        </Link>
      </div>

      <div className="page-header" style={{ marginBottom: '24px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <span className="badge badge-purple" style={{ textTransform: 'uppercase', fontSize: '11px', letterSpacing: '0.05em' }}>
              {namespace} • {objectType}
            </span>
          </div>
          <h1 className="page-title" style={{ fontSize: '36px' }}>{record.title}</h1>
          <p className="page-subtitle" style={{ fontFamily: 'monospace', fontSize: '14px' }}>{record.id}</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-outline">
            <GitMerge size={16} /> View Lineage
          </button>
          <button className="btn btn-primary">
            Actions
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        {/* Main Details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="glass-card">
            <h3 style={{ fontSize: '16px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileText size={18} color="var(--accent-primary)" />
              Properties
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              {record.properties.map((prop) => (
                <div key={prop.name}>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '4px' }}>{prop.name}</div>
                  <div style={{ fontWeight: 500 }}>
                    {prop.badge ? <span className={`badge badge-${prop.badge}`}>{prop.value}</span> : prop.value}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card">
            <h3 style={{ fontSize: '16px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <LinkIcon size={18} color="var(--accent-secondary)" />
              Relationships
            </h3>
            {record.relationships.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>No relationships.</p>
            ) : (
              <div className="data-table-container" style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.05)' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Link Type</th>
                      <th>Target Object</th>
                    </tr>
                  </thead>
                  <tbody>
                    {record.relationships.map((rel, i) => (
                      <tr key={`${rel.link_type}-${i}`}>
                        <td style={{ color: 'var(--text-secondary)' }}>{rel.link_type}</td>
                        <td style={{ color: 'var(--accent-primary)', fontWeight: 500 }}>{rel.target}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="glass-card" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '14px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
              <Shield size={16} /> Governance & Policy
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Classification</span>
                <span className="badge badge-gray">{record.governance.classification}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Purpose</span>
                <span>{record.governance.purpose}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Data Quality</span>
                <span style={{ color: '#4ade80' }}>{record.governance.quality}</span>
              </div>
            </div>
          </div>

          <div className="glass-card" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '14px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
              <Activity size={16} /> Recent Activity
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', fontSize: '13px' }}>
              <div>
                <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>Today, 09:41 AM</div>
                <div>Updated via <span style={{ color: 'var(--accent-primary)' }}>HR Sync Pipeline</span></div>
              </div>
              <div>
                <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>Yesterday, 14:22 PM</div>
                <div>Created by <span style={{ color: 'var(--accent-primary)' }}>Debezium CDC</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
