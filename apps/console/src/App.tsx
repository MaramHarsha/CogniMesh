import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ObjectBrowser } from './components/ObjectBrowser';
import { ObjectExplorer } from './components/ObjectExplorer';
import { ObjectView } from './components/ObjectView';
import { Analytics } from './components/Analytics';
import { Settings } from './components/Settings';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<ObjectBrowser />} />
          <Route path="explorer" element={<ObjectExplorer />} />
          <Route path="object/:objectType/:id" element={<ObjectView />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="settings" element={<Settings />} />
          {/* Add a fallback for undefined routes */}
          <Route path="*" element={
            <div className="glass-card animate-fade-in" style={{ textAlign: 'center', padding: '60px' }}>
              <h2 className="text-gradient" style={{ fontSize: '48px', marginBottom: '16px' }}>404</h2>
              <p style={{ color: 'var(--text-secondary)' }}>Page not found.</p>
            </div>
          } />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
