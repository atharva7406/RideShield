import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

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
    await new Promise(r => setTimeout(r, 700));
    localStorage.setItem('rs_auth', JSON.stringify({ email, name: 'Sunita Rao' }));
    navigate('/dashboard');
    setLoading(false);
  }

  return (
    <div className="h-screen overflow-hidden relative flex items-center justify-center md:justify-end md:pr-12 lg:pr-32 xl:pr-48 font-sans antialiased">

      {/* ── Full-bleed background: city street with delivery rider ── */}
      <div className="fixed inset-0 z-0">
        <img
          src="/stitch-login-bg-highres.jpg"
          alt="Modern Indian city street with delivery rider"
          className="w-full h-full object-cover object-left"
        />
        {/* Subtle white overlay for card readability */}
        <div className="absolute inset-0 bg-white/[0.18]" />
      </div>

      {/* ── Glassmorphism Login Card ── */}
      <main className="relative z-10 w-full max-w-md px-6 py-6 lg:px-8">
        <div
          className="rounded-[2rem] shadow-2xl p-8 sm:p-10 flex flex-col items-center w-full"
          style={{
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            border: '1px solid rgba(255,255,255,0.3)',
            animation: 'fadeIn 0.8s ease-in',
          }}
        >

          {/* ── Header ── */}
          <header className="w-full flex flex-col items-center mb-8">
            {/* Logo */}
            <div className="flex items-center gap-2 mb-4 text-gray-900">
              <svg className="w-8 h-8" style={{ color: '#0066ff' }} fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 2L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-3zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-2.33v8.02z" />
              </svg>
              <span className="text-2xl font-bold tracking-tight text-gray-900">RideShield</span>
            </div>
            {/* Title */}
            <h1 className="text-xl font-semibold text-gray-800 text-center">Insurer Portal</h1>
            {/* Subtitle */}
            <p className="mt-2 text-sm text-gray-600 text-center">Welcome back. Please sign in to your account.</p>
          </header>

          {/* ── Error ── */}
          {error && (
            <div className="w-full mb-4 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm font-medium px-4 py-3 rounded-lg">
              <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
              </svg>
              {error}
            </div>
          )}

          {/* ── Form ── */}
          <form onSubmit={handleSubmit} className="w-full space-y-6">

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium leading-6 text-gray-900">
                Work Email
              </label>
              <div className="mt-2">
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="name@insurer.com"
                  className="block w-full rounded-md border-0 py-2.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm sm:leading-6 bg-white/70 backdrop-blur-sm transition-all outline-none"
                  style={{ '--tw-ring-color': '#0066ff' }}
                  onFocus={e => e.target.style.boxShadow = '0 0 0 2px #0066ff'}
                  onBlur={e => e.target.style.boxShadow = ''}
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium leading-6 text-gray-900">
                Password
              </label>
              <div className="mt-2">
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="block w-full rounded-md border-0 py-2.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm sm:leading-6 bg-white/70 backdrop-blur-sm transition-all outline-none"
                  onFocus={e => e.target.style.boxShadow = '0 0 0 2px #0066ff'}
                  onBlur={e => e.target.style.boxShadow = ''}
                />
              </div>
            </div>

            {/* Sign In button */}
            <div>
              <button
                type="submit"
                disabled={loading}
                className="flex w-full justify-center items-center gap-2 rounded-md px-3 py-3 text-sm font-semibold leading-6 text-white shadow-sm transition-all duration-200 disabled:opacity-60"
                style={{ backgroundColor: loading ? '#0052cc' : '#0066ff' }}
                onMouseEnter={e => { if (!loading) e.currentTarget.style.backgroundColor = '#0052cc'; e.currentTarget.style.transform = 'scale(1.02)'; }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#0066ff'; e.currentTarget.style.transform = 'scale(1)'; }}
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

          {/* ── Footer links ── */}
          <div className="mt-8 flex flex-col items-center space-y-4 w-full border-t border-gray-200 pt-6">
            <div className="text-sm">
              <a href="#" className="font-medium transition-colors" style={{ color: '#0066ff' }}
                onMouseEnter={e => e.currentTarget.style.color = '#0052cc'}
                onMouseLeave={e => e.currentTarget.style.color = '#0066ff'}
              >
                Forgot password?
              </a>
            </div>
            <div className="text-sm text-center">
              <span className="text-gray-500">Need an account?</span>
              <a href="#" className="font-medium ml-1 transition-colors" style={{ color: '#0066ff' }}
                onMouseEnter={e => e.currentTarget.style.color = '#0052cc'}
                onMouseLeave={e => e.currentTarget.style.color = '#0066ff'}
              >
                Contact your administrator for access
              </a>
            </div>
          </div>

        </div>
      </main>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
