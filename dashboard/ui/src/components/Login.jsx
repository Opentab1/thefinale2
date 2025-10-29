import React, { useState } from 'react'
import { signIn, signUp, confirmSignUp, signOut } from 'aws-amplify/auth'
import { Activity, LogIn, UserPlus } from 'lucide-react'

export default function Login({ onAuthSuccess }) {
  const [mode, setMode] = useState('signin') // signin, signup, confirm
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmationCode, setConfirmationCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSignIn = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    
    try {
      await signIn({
        username: email,
        password: password
      })
      onAuthSuccess()
    } catch (err) {
      setError(err.message || 'Failed to sign in')
    } finally {
      setLoading(false)
    }
  }

  const handleSignUp = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    
    try {
      await signUp({
        username: email,
        password: password,
        options: {
          userAttributes: {
            email: email
          }
        }
      })
      setMode('confirm')
    } catch (err) {
      setError(err.message || 'Failed to sign up')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    
    try {
      await confirmSignUp({
        username: email,
        confirmationCode: confirmationCode
      })
      setMode('signin')
      setError('Account confirmed! Please sign in.')
    } catch (err) {
      setError(err.message || 'Failed to confirm account')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Logo & Title */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <Activity className="w-16 h-16 text-blue-500" />
          </div>
          <h1 className="text-4xl font-bold mb-2">Pulse 1.0</h1>
          <p className="text-gray-400">Venue Control Dashboard</p>
        </div>

        {/* Auth Card */}
        <div className="bg-gray-800 rounded-2xl shadow-2xl p-8 border border-gray-700">
          {mode === 'signin' && (
            <form onSubmit={handleSignIn} className="space-y-6">
              <h2 className="text-2xl font-bold flex items-center">
                <LogIn className="w-6 h-6 mr-2" />
                Sign In
              </h2>
              
              <div>
                <label className="block text-sm font-medium mb-2">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                  placeholder="your@email.com"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                  placeholder="••••••••"
                  required
                />
              </div>

              {error && (
                <div className={`text-sm p-3 rounded-lg ${error.includes('confirmed') ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition-colors disabled:opacity-50"
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setMode('signup')}
                  className="text-blue-400 hover:text-blue-300 text-sm"
                >
                  Don't have an account? Sign up
                </button>
              </div>
            </form>
          )}

          {mode === 'signup' && (
            <form onSubmit={handleSignUp} className="space-y-6">
              <h2 className="text-2xl font-bold flex items-center">
                <UserPlus className="w-6 h-6 mr-2" />
                Sign Up
              </h2>
              
              <div>
                <label className="block text-sm font-medium mb-2">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                  placeholder="your@email.com"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                  placeholder="••••••••"
                  required
                  minLength={8}
                />
                <p className="text-xs text-gray-500 mt-1">At least 8 characters</p>
              </div>

              {error && (
                <div className="text-sm p-3 rounded-lg bg-red-900/30 text-red-400">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition-colors disabled:opacity-50"
              >
                {loading ? 'Signing up...' : 'Sign Up'}
              </button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setMode('signin')}
                  className="text-blue-400 hover:text-blue-300 text-sm"
                >
                  Already have an account? Sign in
                </button>
              </div>
            </form>
          )}

          {mode === 'confirm' && (
            <form onSubmit={handleConfirm} className="space-y-6">
              <h2 className="text-2xl font-bold">Confirm Account</h2>
              
              <p className="text-gray-400 text-sm">
                We sent a confirmation code to <strong>{email}</strong>
              </p>

              <div>
                <label className="block text-sm font-medium mb-2">Confirmation Code</label>
                <input
                  type="text"
                  value={confirmationCode}
                  onChange={(e) => setConfirmationCode(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                  placeholder="123456"
                  required
                />
              </div>

              {error && (
                <div className="text-sm p-3 rounded-lg bg-red-900/30 text-red-400">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition-colors disabled:opacity-50"
              >
                {loading ? 'Confirming...' : 'Confirm Account'}
              </button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setMode('signin')}
                  className="text-blue-400 hover:text-blue-300 text-sm"
                >
                  Back to sign in
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Footer */}
        <div className="text-center mt-8 text-sm text-gray-500">
          <p>Powered by AWS Cognito</p>
        </div>
      </div>
    </div>
  )
}
