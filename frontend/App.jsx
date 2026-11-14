import ChatPage from './Chatpage.jsx';
import { useChats } from './Chatstore.js';
import { useEffect, useState } from 'react';
import LoginPage from './loginpage.jsx';
import SignupPage from './signuppage.jsx';
import HomePage from './homepage.jsx';
import './style.css';

// DEMO accounts, in memory only. Real accounts and password hashing belong on the backend.
const SEED = ['researcher', 'engineer', 'student'].map((r) => ({ email: `${r}@nasa.gov`, password: 'space123', role: r }));

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  const [page, setPage] = useState('login');
  const [users, setUsers] = useState(SEED);
  const [user, setUser] = useState(null);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('theme', theme); }, [theme]);
  const common = { theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) };
  if (user) return <Shell user={user} {...common} onLogout={() => { setUser(null); setPage('login'); }} />;
  return page === 'signup'
    ? <SignupPage {...common} users={users} onSignup={(u) => { setUsers([...users, u]); setUser(u); }} goLogin={() => setPage('login')} />
    : <LoginPage {...common} users={users} onLogin={setUser} goSignup={() => setPage('signup')} />;
}

