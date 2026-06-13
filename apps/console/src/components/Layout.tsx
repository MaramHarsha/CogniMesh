import { Outlet, NavLink } from 'react-router-dom';
import { Database, Search, Activity, Settings, Hexagon } from 'lucide-react';

export function Layout() {
  return (
    <div className="app-container">
      <aside className="sidebar">
        <div style={{ padding: '0 24px', marginBottom: '40px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ background: 'var(--accent-primary)', padding: '8px', borderRadius: '8px' }}>
            <Hexagon size={24} color="white" />
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 600, letterSpacing: '-0.03em' }}>CogniMesh</h2>
        </div>
        
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <NavLink to="/" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} end>
            <Database size={18} />
            Object Types
          </NavLink>
          <NavLink to="/explorer" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <Search size={18} />
            Object Explorer
          </NavLink>
          <NavLink to="/analytics" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <Activity size={18} />
            Analytics
          </NavLink>
          <div style={{ flex: 1 }}></div>
          <NavLink to="/settings" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} style={{ marginTop: 'auto' }}>
            <Settings size={18} />
            Settings
          </NavLink>
        </nav>
      </aside>
      
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
