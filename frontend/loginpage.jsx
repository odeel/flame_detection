import { useState } from 'react';
import { AuthHero, Corner } from './components.jsx';
import { Icon } from './ui.jsx';

const DEMO = ['researcher@nasa.gov', 'engineer@nasa.gov', 'student@nasa.gov'];

// Login does not ask for a role: the account's role (chosen at signup) decides the dashboard.
export default function LoginPage({ users, onLogin, goSignup, theme, toggle }) {
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');
  const submit = (e) => {
    e.preventDefault();
    const u = users.find((x) => x.email === email.trim().toLowerCase() && x.password === pw);
    if (!u) return setErr('Wrong email or password.');
    onLogin(u);
  };
  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle} onHome={() => scrollTo({ top: 0, behavior: 'smooth' })}>
        <button type="button" className="navbtn" onClick={goSignup}>Create account</button>
      </Corner>
      <main className="container auth-page">
        <AuthHero />
        <form className="auth card fade-in" onSubmit={submit} noValidate>
          <div className="stack-xs">
            <p className="eyebrow">Mission access</p>
            <h2>Welcome back to the fire lab</h2>
            <p className="muted text-sm">Your dashboard opens with the profile you chose when you signed up.</p>
          </div>
          <label className="field">Email address<input type="email" value={email} onChange={(e) => { setEmail(e.target.value); setErr(''); }} placeholder="astronaut@nasa.gov" autoComplete="email" required /></label>
          <label className="field">Password<input type="password" value={pw} onChange={(e) => { setPw(e.target.value); setErr(''); }} placeholder="••••••••" autoComplete="current-password" required /></label>
          {err && <p className="field-err" role="alert"><Icon name="alert" />{err}</p>}
          <button className="cta" type="submit">Log in <Icon name="arrowRight" /></button>
          <div className="demo">
            <span>Demo accounts (password <code>space123</code>), click to fill:</span>
            {DEMO.map((d) => <button type="button" key={d} onClick={() => { setEmail(d); setPw('space123'); setErr(''); }}>{d}</button>)}
          </div>
          <p className="foot">No account? <button type="button" className="link" onClick={goSignup}>Sign up</button></p>
        </form>
      </main>
    </div>
  );
}
