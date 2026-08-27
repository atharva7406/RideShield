import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../services/api';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email || !password) { setError('Please enter your work email and password.'); return; }
    setLoading(true);
    setError('');
    try {
      const res = await login(email, password);
      localStorage.setItem('rs_auth', JSON.stringify({ email, name: res.user.name, role: res.user.role }));
      if (res.user.role === 'HOSPITAL_REP') {
        navigate('/hospital');
      } else {
        navigate('/dashboard');
      }
    } catch (err) {
      setError(err.message || 'Incorrect email or password.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-50 font-sans antialiased">
      
      {/* Left: Premium Hero Image Section (visible on desktop/tablet) */}
      <div className="hidden md:flex md:w-1/2 lg:w-3/5 relative overflow-hidden bg-slate-900 select-none">
        <img
          src="/stitch-login-bg-highres.jpg"
          alt="Modern Indian city street with delivery rider"
          className="absolute inset-0 w-full h-full object-cover object-left"
        />
        {/* Gradient overlay for contrast */}
        <div className="absolute inset-0 bg-gradient-to-tr from-slate-950 via-slate-900/40 to-transparent" />
        
        {/* Brand / Tagline Content */}
        <div className="relative z-10 flex flex-col justify-between p-12 lg:p-16 h-full text-white">
          <div className="flex items-center gap-3">
            <svg className="w-10 h-10 text-blue-500 fill-current" viewBox="0 0 24 24">
              <path d="M12 2L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-3zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-2.33v8.02z" />
            </svg>
            <span className="text-3xl font-extrabold tracking-tight">RideShield</span>
          </div>
          
          <div className="max-w-md">
            <h2 className="text-4xl lg:text-5xl font-extrabold leading-tight mb-6">
              Smart IoT Insurance for Gig Workers
            </h2>
            <p className="text-lg text-slate-300 font-medium leading-relaxed">
              Protecting every rider, every shift, with automated instant claims and real-time crash detection.
            </p>
          </div>
          
          <div className="text-sm text-slate-400">
            © 2026 RideShield Technologies. All rights reserved.
          </div>
        </div>
      </div>

      {/* Right: Scrollable Form Panel */}
      <div className="flex-1 flex flex-col justify-center items-center p-8 sm:p-12 md:p-16 bg-white overflow-y-auto min-h-screen">
        <div className="w-full max-w-md my-auto">
          
          {/* Brand header for mobile */}
          <div className="flex md:hidden items-center gap-2 mb-8 text-slate-900 justify-center">
            <svg className="w-8 h-8 text-blue-600 fill-current" viewBox="0 0 24 24">
              <path d="M12 2L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-3zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-2.33v8.02z" />
            </svg>
            <span className="text-2xl font-bold tracking-tight">RideShield</span>
          </div>

          <header className="mb-8">
            <h1 className="text-2xl lg:text-3xl font-bold text-slate-900">Welcome Back</h1>
            <p className="mt-2 text-sm text-slate-600">Please sign in to your insurer or representative account.</p>
          </header>

          {error && (
            <div className="w-full mb-6 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm font-medium px-4 py-3 rounded-lg">
              <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
              </svg>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                Work Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="name@insurer.com"
                className="mt-1 block w-full rounded-lg border border-slate-300 py-2.5 px-3.5 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
              />
            </div>

            <div>
              <div className="flex justify-between items-center">
                <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                  Password
                </label>
                <a href="#" className="text-xs font-semibold text-blue-600 hover:text-blue-700 transition">
                  Forgot password?
                </a>
              </div>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-1 block w-full rounded-lg border border-slate-300 py-2.5 px-3.5 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="flex w-full justify-center items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 active:scale-[0.99] px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 disabled:opacity-60 cursor-pointer"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                    Signing in…
                  </>
                ) : 'Sign In'}
              </button>
            </div>
          </form>

          <div className="mt-8 flex flex-col items-center space-y-2 w-full border-t border-slate-200 pt-6 text-sm">
            <span className="text-slate-500">Need an account?</span>
            <button
              onClick={() => navigate('/register')}
              className="font-semibold text-blue-600 hover:text-blue-700 transition-colors cursor-pointer"
            >
              Register here
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
