import { useState, useEffect, useMemo } from 'react';
import { Search, Filter, Download, FileText } from 'lucide-react';
import { useSearchParams, Link } from 'react-router-dom';
import { queryObjects, statusBadge, type ObjectRecord, type ObjectColumn } from '../api';

export function ObjectExplorer() {
  const [searchParams] = useSearchParams();
  const initialType = searchParams.get('type') || 'Employee';

  const [query, setQuery] = useState('');
  const [columns, setColumns] = useState<ObjectColumn[]>([]);
  const [results, setResults] = useState<ObjectRecord[]>([]);
  const [loading, setLoading] = useState(true);

  // Reset the search box whenever the object type changes.
  useEffect(() => {
    setQuery('');
  }, [initialType]);

  useEffect(() => {
    setLoading(true);
    // Simulate the governed query round-trip, then filter via the data layer.
    const timer = setTimeout(() => {
      const data = queryObjects(initialType, query);
      setColumns(data.columns);
      setResults(data.records);
      setLoading(false);
    }, 250);
    return () => clearTimeout(timer);
  }, [initialType, query]);

  const headers = useMemo(() => [...columns, { key: '__actions', label: 'Actions' }], [columns]);

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Object Explorer</h1>
          <p className="page-subtitle">Search, filter, and analyze {initialType} objects.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-outline">
            <Filter size={16} /> Filter
          </button>
          <button className="btn btn-outline">
            <Download size={16} /> Export
          </button>
        </div>
      </div>

      <div className="glass-card" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--card-border)', display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input
              type="text"
              className="input-field"
              placeholder={`Search across ${initialType}s...`}
              style={{ paddingLeft: '44px' }}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Executing governed query...
          </div>
        ) : results.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            No {initialType} objects match “{query}”.
          </div>
        ) : (
          <div className="data-table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  {headers.map((col) => (
                    <th key={col.key}>{col.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.map((row, i) => (
                  <tr key={row.id} className={`animate-fade-in delay-${(i % 3) * 100}`}>
                    {columns.map((col) => {
                      const value = col.key === 'id' ? row.id : row.summary[col.key] ?? '';
                      if (col.key === 'status') {
                        return (
                          <td key={col.key}>
                            <span className={`badge badge-${statusBadge(value)}`}>{value}</span>
                          </td>
                        );
                      }
                      return (
                        <td
                          key={col.key}
                          style={col.mono
                            ? { fontFamily: 'monospace', color: 'var(--text-secondary)' }
                            : col.key === Object.keys(row.summary)[0]
                              ? { fontWeight: 500, color: 'white' }
                              : undefined}
                        >
                          {value}
                        </td>
                      );
                    })}
                    <td>
                      <Link to={`/object/${initialType}/${row.id}`} style={{ textDecoration: 'none' }}>
                        <button className="btn btn-outline" style={{ padding: '4px 8px' }}>
                          <FileText size={14} /> View
                        </button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
