import { features } from '../services/features'
import type { FormEvent } from 'react'
import { ArrowRight, ScanLine, Dumbbell, UsersRound } from 'lucide-react'
import { Button } from '../design-system/components'
type Props = { email: string; password: string; firstName: string; lastName: string; authMode: 'signin' | 'signup'; error: string; isSubmitting: boolean; onEmailChange: (value: string) => void; onPasswordChange: (value: string) => void; onFirstNameChange: (value: string) => void; onLastNameChange: (value: string) => void; onModeChange: (mode: 'signin' | 'signup') => void; onForgotPassword: () => void; onSubmit: (e: FormEvent<HTMLFormElement>) => void }
export default function LoginPage(props: Props) {
  return <main className="login-page"><section className="login-brand"><div className="side-brand"><span className="brand-symbol" aria-hidden="true">V</span><strong>Vectra<span>PERFORMANCE OS</span></strong></div><div className="login-statement"><p className="eyebrow">Built for the work. Built for progress.</p><h1>Every client.<br />Every session.<br /><span>Forward.</span></h1><p>A focused workspace for the people behind every performance.</p></div><div className="login-pillars"><span><UsersRound size={18} /> Client context</span><span><Dumbbell size={18} /> Training plans</span>{features.formAnalysis && <span><ScanLine size={18} /> Movement analysis</span>}</div></section>
    <section className="login-form-panel"><div className="login-form-wrap"><p className="eyebrow">Your workspace awaits</p><h2>Welcome back.</h2><p>Sign in to continue your work.</p><form onSubmit={props.onSubmit}>
      <label htmlFor="login-email">Email address</label><input id="login-email" type="email" autoComplete="email" required value={props.email} onChange={e => props.onEmailChange(e.target.value)} />
      <div className="login-password-label"><label htmlFor="login-password">Password</label><button type="button" onClick={props.onForgotPassword}>Forgot password?</button></div><input id="login-password" type="password" required maxLength={256} autoComplete="current-password" value={props.password} onChange={e => props.onPasswordChange(e.target.value)} />
      {props.error && <p role="alert" className="error-notice">{props.error}</p>}<Button type="submit" disabled={props.isSubmitting}>{props.isSubmitting ? 'Signing in…' : 'Sign in'}<ArrowRight size={16} /></Button>
    </form><div className="login-register"><span>New to Vectra?</span><Button variant="tertiary" onClick={() => props.onModeChange('signup')}>Create a business workspace<ArrowRight size={16} /></Button></div></div></section>
  </main>
}
