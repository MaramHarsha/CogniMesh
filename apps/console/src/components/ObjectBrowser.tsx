import { useState, useEffect } from 'react';
import { Box, ChevronRight, Layers } from 'lucide-react';
import { Link } from 'react-router-dom';
import { fetchObjectTypes, statusBadge, type ObjectTypeSummary } from '../api';

export function ObjectBrowser() {
  const [objectTypes, setObjectTypes] = useState<ObjectTypeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let active = true;
    fetchObjectTypes().then(({ data, live }) => {
      if (!active) return;
      setObjectTypes(data);
      setLive(live);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Object Types</h1>
          <p className="page-subtitle">Browse and manage the semantic object models across namespaces.</p>
        </div>
        <button className="btn btn-primary">
          <Layers size={16} />
          Register Object Type
        </button>
      </div>

      {!loading && (
        <div style={{ marginBottom: '24px' }}>
          <span className={`badge ${live ? 'badge-green' : 'badge-gray'}`}>
            {live ? 'Live · Object Registry' : 'Demo data · registry offline'}
          </span>
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
          <div style={{ color: 'var(--accent-primary)' }}>Loading object types...</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '24px' }}>
          {objectTypes.map((obj, i) => (
            <div key={obj.object_type_id} className={`glass-card animate-fade-in delay-${(i % 3 + 1) * 100}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ background: 'rgba(99, 102, 241, 0.1)', padding: '10px', borderRadius: '10px' }}>
                    <Box size={24} color="var(--accent-primary)" />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '18px', marginBottom: '4px' }}>{obj.display_name}</h3>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {obj.namespace} • {obj.api_name}
                    </div>
                  </div>
                </div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: '1.5', marginBottom: '24px', minHeight: '42px' }}>
                {obj.description}
              </p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className={`badge badge-${statusBadge(obj.status)}`}>
                  {obj.status.toUpperCase()}
                </span>
                <Link to={`/explorer?type=${obj.api_name}`} style={{ textDecoration: 'none' }}>
                  <button className="btn btn-outline" style={{ padding: '6px 12px', fontSize: '13px' }}>
                    Explore <ChevronRight size={14} />
                  </button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
