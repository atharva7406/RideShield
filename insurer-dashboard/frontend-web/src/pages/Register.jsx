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
    <div className="h-screen overflow-hidden relative flex items-center justify-center md:justify-end md:pr-12 lg:pr-32 xl:pr-48 font-sans antialiased">
      <div className="fixed inset-0 z-0">
        <img
          src="/stitch-login-bg-highres.jpg"
          alt="Modern Indian city street with delivery rider"
          className="w-full h-full object-cover object-left"
        />
        <div className="absolute inset-0 bg-white/[0.18]" />
      </div>

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
          <header className="w-full flex flex-col items-center mb-6">
            <div className="flex items-center gap-2 mb-2 text-gray-900">
              <svg className="w-8 h-8" style={{ color: '#0066ff' }} fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-3zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-2.33v8.02z" />
              </svg>
              <span className="text-2xl font-bold tracking-tight text-gray-900">RideShield</span>
            </div>
            <h1 className="text-xl font-semibold text-gray-800 text-center">Insurer Registration</h1>
            <p className="mt-1 text-sm text-gray-600 text-center">Create a new Insurer Admin account.</p>
          </header>

          {error && (
            <div className="w-full mb-4 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm font-medium px-4 py-2.5 rounded-lg">
              {error}
            </div>
          )}

          {success && (
            <div className="w-full mb-4 flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 text-sm font-medium px-4 py-2.5 rounded-lg">
              Registration successful! Redirecting to login...
            </div>
          )}

          <form onSubmit={handleSubmit} className="w-full space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-900">Registration Role</label>
              <select
                value={role}
                onChange={e => setRole(e.target.value)}
                className="mt-1 block w-full rounded-md border-0 py-2 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset sm:text-sm bg-white/70 outline-none"
              >
                <option value="INSURER">Insurer Admin</option>
                <option value="HOSPITAL_REP">Hospital Representative</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900">Full Name</label>
              <input
                type="text"
                required
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Admin Name"
                className="mt-1 block w-full rounded-md border-0 py-2 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm bg-white/70 outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900">Work Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="name@organization.com"
                className="mt-1 block w-full rounded-md border-0 py-2 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm bg-white/70 outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900">Phone Number</label>
              <input
                type="tel"
                required
                value={phone}
                onChange={e => setPhone(e.target.value)}
                placeholder="+919876543210"
                className="mt-1 block w-full rounded-md border-0 py-2 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm bg-white/70 outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-900">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-1 block w-full rounded-md border-0 py-2 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm bg-white/70 outline-none"
              />
            </div>

            {role === 'HOSPITAL_REP' && (
              <div className="space-y-4 border-t border-gray-200 pt-4 animate-fade-in">
                <h3 className="text-sm font-semibold text-gray-800">Hospital Facility Details</h3>
                
                <div>
                  <label className="block text-xs font-medium text-gray-700">Hospital Name</label>
                  <input
                    type="text"
                    required
                    value={hospitalName}
                    onChange={e => setHospitalName(e.target.value)}
                    placeholder="e.g. City General Hospital"
                    className="mt-1 block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm bg-white/70 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700">Hospital Address (for geocoding)</label>
                  <input
                    type="text"
                    required
                    value={hospitalAddress}
                    onChange={e => setHospitalAddress(e.target.value)}
                    placeholder="e.g. Andheri East, Mumbai"
                    className="mt-1 block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm bg-white/70 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700">Hospital Contact Phone</label>
                  <input
                    type="tel"
                    required
                    value={hospitalPhone}
                    onChange={e => setHospitalPhone(e.target.value)}
                    placeholder="+912224567890"
                    className="mt-1 block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset sm:text-sm bg-white/70 outline-none"
                  />
                </div>
              </div>
            )}

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading || success}
                className="flex w-full justify-center items-center gap-2 rounded-md px-3 py-2.5 text-sm font-semibold text-white shadow-sm transition-all duration-200 disabled:opacity-60 bg-blue-600 hover:bg-blue-700"
                style={{ backgroundColor: '#0066ff' }}
              >
                {loading ? 'Creating Account…' : 'Register'}
              </button>
            </div>
          </form>

          <div className="mt-6 flex flex-col items-center space-y-2 w-full border-t border-gray-200 pt-4 text-sm">
            <span className="text-gray-500">Already have an account?</span>
            <button
              onClick={() => navigate('/login')}
              className="font-medium text-blue-600 hover:text-blue-700 transition-colors"
            >
              Back to Login
            </button>
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
