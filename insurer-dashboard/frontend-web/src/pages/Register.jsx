import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { register } from '../services/api';

export default function Register() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('INSURER');
  const [hospitalName, setHospitalName] = useState('');
  const [hospitalAddress, setHospitalAddress] = useState('');
  const [hospitalPhone, setHospitalPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    if (!fullName || !email || !phone || !password) {
      setError('Please fill in all the fields.');
      return;
    }
    if (role === 'HOSPITAL_REP' && (!hospitalName || !hospitalAddress || !hospitalPhone)) {
      setError('Please fill in all hospital details.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const hospitalInfo = role === 'HOSPITAL_REP' ? { hospitalName, hospitalAddress, hospitalPhone } : null;
      await register(fullName, email, phone, password, role, hospitalInfo);
      setSuccess(true);
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err) {
      setError(err.message || 'Registration failed.');
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
            <h1 className="text-2xl lg:text-3xl font-bold text-slate-900">Create Account</h1>
            <p className="mt-2 text-sm text-slate-600">Register as an Insurer Admin or Hospital Representative.</p>
          </header>

          {error && (
            <div className="w-full mb-6 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm font-medium px-4 py-3 rounded-lg">
              <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
              </svg>
              {error}
            </div>
          )}

          {success && (
            <div className="w-full mb-6 flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-medium px-4 py-3 rounded-lg">
              <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
              </svg>
              Registration successful! Redirecting to login...
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-700">Registration Role</label>
              <select
                value={role}
                onChange={e => setRole(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-slate-300 py-2.5 px-3.5 text-slate-900 shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
              >
                <option value="INSURER">Insurer Admin</option>
                <option value="HOSPITAL_REP">Hospital Representative</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">Full Name</label>
              <input
                type="text"
                required
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Admin Name"
                className="mt-1 block w-full rounded-lg border border-slate-300 py-2.5 px-3.5 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">Work Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="name@organization.com"
                className="mt-1 block w-full rounded-lg border border-slate-300 py-2.5 px-3.5 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">Phone Number</label>
              <input
                type="tel"
                required
                value={phone}
                onChange={e => setPhone(e.target.value)}
                placeholder="+919876543210"
                className="mt-1 block w-full rounded-lg border border-slate-300 py-2.5 px-3.5 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-1 block w-full rounded-lg border border-slate-300 py-2.5 px-3.5 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
              />
            </div>

            {role === 'HOSPITAL_REP' && (
              <div className="space-y-4 border-t border-slate-200 pt-5 mt-5 animate-fade-in">
                <h3 className="text-sm font-semibold text-slate-800">Hospital Facility Details</h3>
                
                <div>
                  <label className="block text-xs font-medium text-slate-600">Hospital Name</label>
                  <input
                    type="text"
                    required
                    value={hospitalName}
                    onChange={e => setHospitalName(e.target.value)}
                    placeholder="e.g. City General Hospital"
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600">Hospital Address (for geocoding)</label>
                  <input
                    type="text"
                    required
                    value={hospitalAddress}
                    onChange={e => setHospitalAddress(e.target.value)}
                    placeholder="e.g. Andheri East, Mumbai"
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600">Hospital Contact Phone</label>
                  <input
                    type="tel"
                    required
                    value={hospitalPhone}
                    onChange={e => setHospitalPhone(e.target.value)}
                    placeholder="+912224567890"
                    className="mt-1 block w-full rounded-lg border border-slate-300 py-2 px-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 sm:text-sm bg-white outline-none transition"
                  />
                </div>
              </div>
            )}

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading || success}
                className="flex w-full justify-center items-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 disabled:opacity-60 bg-blue-600 hover:bg-blue-700 active:scale-[0.99] cursor-pointer"
              >
                {loading ? 'Creating Account…' : 'Register'}
              </button>
            </div>
          </form>

          <div className="mt-8 flex flex-col items-center space-y-2 w-full border-t border-slate-200 pt-6 text-sm">
            <span className="text-slate-500">Already have an account?</span>
            <button
              onClick={() => navigate('/login')}
              className="font-semibold text-blue-600 hover:text-blue-700 transition-colors cursor-pointer"
            >
              Back to Login
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

