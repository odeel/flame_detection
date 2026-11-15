import { useEffect, useState } from 'react';
import LoginPage from './loginpage.jsx';
import SignupPage from './signuppage.jsx';
import HomePage from './homepage.jsx';
import ChatPage from './chatpage.jsx';
import Backdrop from './Backdrop.jsx';
import { useChats } from './chatstore.js';
import './style.css';

// DEMO accounts, in memory only. Real accounts and password hashing belong on the backend.
const SEED = ['researcher', 'engineer', 'student'].map((r) => ({ email: `${r}@nasa.gov`, password: 'space123', role: r }));

function Shell({ user, onLogout, common }) {
  const chats = useChats(user);
  const [page, setPage] = useState('home');
  const [homeKey, setHomeKey] = useState(0);   // bumping it remounts HomePage: resets tabs, detail view and "view as"
  const goHome = () => { setPage('home'); setHomeKey((k) => k + 1); scrollTo({ top: 0, behavior: 'smooth' }); };
  const ask = (text, habitat) => { chats.ask(text, { habitat }); setPage('chat'); };
  return page === 'chat'
    ? <ChatPage {...common} user={user} chats={chats} onBack={() => setPage('home')} onHome={goHome} />
    : <HomePage key={homeKey} {...common} user={user} onLogout={onLogout} onAsk={ask} onHome={goHome} onOpenChats={() => { chats.setActive(null); setPage('chat'); }} />;
}

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  const [page, setPage] = useState('login');
  const [users, setUsers] = useState(SEED);
  const [user, setUser] = useState(null);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('theme', theme); }, [theme]);
  const common = { theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) };
  return (
    <>
      <Backdrop satellite={!user} />
      <div className="layer">
        {user ? <Shell user={user} common={common} onLogout={() => { setUser(null); setPage('login'); }} />
          : page === 'signup' ? <SignupPage {...common} users={users} onSignup={(u) => { setUsers([...users, u]); setUser(u); }} goLogin={() => setPage('login')} />
          : <LoginPage {...common} users={users} onLogin={setUser} goSignup={() => setPage('signup')} />}
      </div>
    </>
  );
}
