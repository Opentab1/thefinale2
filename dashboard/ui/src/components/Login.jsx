import React, { useState } from 'react'
import { Activity, Lock, User, AlertCircle } from 'lucide-react'
import { signIn } from 'aws-amplify/auth'
import { isAuthConfigured } from '../aws-config'

export default function Login({ onAuthSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [devMode, setDevMode] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // If auth is not configured, allow dev mode bypass
      if (!isAuthConfigured && devMode) {
        console.log('🔓 Development mode: Bypassing authentication')
        onAuthSuccess()
        return
      }

      // Attempt Cognito sign in
      const { isSignedIn } = await signIn({ username, password })
      
      if (isSignedIn) {
        onAuthSuccess()
      } else {
        setError('Authentication failed. Please try again.')
      }
    } catch (err) {
      console.error('Sign in error:', err)
      
      // Provide helpful error messages
      if (err.name === 'UserNotFoundException') {
        setError('User not found. Please check your username.')
      } else if (err.name === 'NotAuthorizedException') {
        setError('Incorrect username or password.')
      } else if (err.name === 'NetworkError') {
        setError('Network error. Please check your connection.')
      } else {
        setError(err.message || 'An error occurred during sign in.')
      }
    } finally {
      setLoading(false)
    }
  }

  // Show dev mode option if auth is not configured
  const showDevMode = !isAuthConfigured

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Logo & Title */}
        <div className="text-center mb-8">
          <Activity className="w-20 h-20 text-blue-500 mx-auto mb-4 animate-pulse" />
          <h1 className="text-4xl font-bold text-white mb-2">Pulse 1.0</h1>
          <p className="text-gray-400">Smart Venue Automation System</p>
        </div>

        {/* Login Card */}
        <div className="bg-gray-800 rounded-lg shadow-2xl p-8 border border-gray-700">
          <h2 className="text-2xl font-bold text-white mb-6 text-center">Sign In</h2>

          {/* Auth Not Configured Warning */}
          {showDevMode && (
            <div className="mb-6 p-4 bg-yellow-900/30 border border-yellow-700 rounded-lg">
              <div className="flex items-start space-x-3">
                <AlertCircle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-yellow-200">
                  <p className="font-semibold mb-1">AWS Cognito Not Configured</p>
                  <p className="text-yellow-300/80">
                    Authentication is disabled. Configure AWS Cognito in <code className="text-yellow-100">aws-config.js</code> to enable secure login.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg">
              <div className="flex items-center space-x-2 text-red-300">
                <AlertCircle className="w-5 h-5" />
                <span className="text-sm">{error}</span>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Username */}
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-2">
                Username
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500" />
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={showDevMode && devMode}
                  className="w-full pl-10 pr-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
                  placeholder="Enter your username"
                  required={!devMode}
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500" />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={showDevMode && devMode}
                  className="w-full pl-10 pr-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
                  placeholder="Enter your password"
                  required={!devMode}
                />
              </div>
            </div>

            {/* Dev Mode Toggle */}
            {showDevMode && (
              <div className="flex items-center space-x-2">
                <input
                  id="devMode"
                  type="checkbox"
                  checked={devMode}
                  onChange={(e) => setDevMode(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <label htmlFor="devMode" className="text-sm text-gray-300">
                  Development Mode (Skip Authentication)
                </label>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Signing In...</span>
                </>
              ) : (
                <span>Sign In</span>
              )}
            </button>
          </form>

          {/* Help Text */}
          <div className="mt-6 text-center text-sm text-gray-400">
            <p>Need help? Contact your system administrator.</p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Pulse 1.0 Smart Venue Automation System</p>
          <p className="mt-1">© {new Date().getFullYear()} All rights reserved.</p>
        </div>
      </div>
    </div>
  )
}
