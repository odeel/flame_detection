import { useState } from 'react';
import { AuthHero, Corner, RoleCards } from './components.jsx';
import { Icon } from './ui.jsx';

// The role is chosen once, here. Login never asks for it again.
export default function SignupPage({ users, onSignup, goLogin, theme, toggle }) {
  const [role, setRole] = useState(null);
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');
  const submit = (e) => {
    e.preventDefault();
    const em = email.trim().toLowerCase();
    if (!role) return setErr('Pick a mission profile first.');
    if (!/^\S+@\S+\.\S+$/.test(em)) return setErr('Enter a valid email address.');
    if (users.some((u) => u.email === em)) return setErr('That email is already registered.');
    if (pw.length < 8) return setErr('Use at least 8 characters for the password.');
    onSignup({ email: em, password: pw, role });
  };
  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle} onHome={goLogin}>
        <button type="button" className="navbtn" onClick={goLogin}>Log in</button>
      </Corner>
      <main className="container auth-page">
        <AuthHero />
        <form className="auth card fade-in" onSubmit={submit} noValidate>
          <div className="stack-xs">
            <p className="eyebrow">Join the mission</p>
            <h2>Create your account</h2>
          </div>
          <div className="stack-sm">
            <span className="field">Choose your mission profile</span>
            <RoleCards value={role} onChange={(r) => { setRole(r); setErr(''); }} />
          </div>
          <label className="field">Email address<input type="email" value={email} onChange={(e) => { setEmail(e.target.value); setErr(''); }} placeholder="astronaut@nasa.gov" autoComplete="email" required /></label>
          <label className="field">Password<input type="password" value={pw} onChange={(e) => { setPw(e.target.value); setErr(''); }} placeholder="At least 8 characters" autoComplete="new-password" required /></label>
          {err && <p className="field-err" role="alert"><Icon name="alert" />{err}</p>}
          <button className="cta" type="submit">Create account <Icon name="arrowRight" /></button>
          <p className="muted text-xs center-text">Demo only: accounts live in memory and are lost on reload.</p>
          <p className="foot">Already registered? <button type="button" className="link" onClick={goLogin}>Log in</button></p>
        </form>
      </main>
    </div>
  );
}
