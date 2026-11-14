import { useState } from 'react';
import { Corner, RoleChips } from './components.jsx';

export default function SignupPage({ users, onSignup, goLogin, theme, toggle }) {
  const [role, setRole] = useState('researcher');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');
  const submit = (e) => {
    e.preventDefault();
    const em = email.trim().toLowerCase();
    if (users.some((u) => u.email === em)) return setErr('That email is already registered.');
    if (pw.length < 8) return setErr('Use at least 8 characters for the password.');
    onSignup({ email: em, password: pw, role });
  };
  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle} />
      <main className="center">
        <form className="auth card" onSubmit={submit}>
          <h1>Nasa flame smart detection</h1>
          <p className="mu">Select your mission profile</p>
          <RoleChips value={role} onChange={setRole} />
          <h2>Register &amp; join the mission</h2>
          <label>Email address<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="astronaut@nasa.gov" autoComplete="email" required /></label>
          <label>Password<input type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="At least 8 characters" autoComplete="new-password" required /></label>
          {err && <p className="err" role="alert">{err}</p>}
          <button className="btn" type="submit">Sign up</button>
        </form>
        <p className="foot mu">Already registered? <button className="link" onClick={goLogin}>Login</button></p>
      </main>
    </div>
  );
}