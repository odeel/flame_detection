import { useState } from 'react';
import { ROLES } from './roles.js';
import { Corner, RoleChips } from './components.jsx';

export default function LoginPage({ users, onLogin, goSignup, theme, toggle }) {
  const [role, setRole] = useState('researcher');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');
  const submit = (e) => {
    e.preventDefault();
    const u = users.find((x) => x.email === email.trim().toLowerCase() && x.password === pw);
    if (!u) return setErr('Wrong email or password.');
    if (u.role !== role) return setErr(`This account is a ${ROLES[u.role].label} account. Pick that profile.`);
    onLogin(u);
  };
  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle} />
      <main className="center">
        <form className="auth card" onSubmit={submit}>
          <h1>Nasa flame smart detection</h1>
          <p className="mu">Select your mission profile</p>
          <RoleChips value={role} onChange={setRole} />
          <h2>Welcome back to the fire lab</h2>
          <label>Email address<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="astronaut@nasa.gov" autoComplete="email" required /></label>
          <label>Password<input type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="••••••••" autoComplete="current-password" required /></label>
          {err && <p className="err" role="alert">{err}</p>}
          <button className="btn" type="submit">Login</button>
          <p className="mu sm">Demo: researcher@nasa.gov, engineer@nasa.gov or student@nasa.gov, password space123</p>
        </form>
        <p className="foot mu">No account? <button className="link" onClick={goSignup}>Sign up</button></p>
      </main>
    </div>
  );
}