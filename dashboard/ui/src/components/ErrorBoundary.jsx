import React from 'react'
import { AlertCircle } from 'lucide-react'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo)
    this.state = { hasError: true, error, errorInfo }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
          <div className="max-w-2xl w-full bg-gray-800 border border-gray-700 rounded-lg p-8">
            <div className="flex items-center space-x-4 mb-6">
              <AlertCircle className="w-12 h-12 text-red-500" />
              <div>
                <h1 className="text-2xl font-bold text-white">Dashboard Error</h1>
                <p className="text-gray-400">Something went wrong loading the dashboard</p>
              </div>
            </div>
            
            <div className="bg-gray-900 rounded p-4 mb-6">
              <p className="text-sm text-gray-300 font-mono">
                {this.state.error?.toString()}
              </p>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-blue-900/20 border border-blue-700 rounded">
                <h3 className="font-semibold text-blue-400 mb-2">Troubleshooting Steps:</h3>
                <ul className="text-sm text-gray-300 space-y-1 list-disc list-inside">
                  <li>Check if AWS Cognito is properly configured in <code className="bg-gray-800 px-1 rounded">src/aws-config.js</code></li>
                  <li>Ensure all required environment variables are set</li>
                  <li>Try clearing your browser cache and reloading</li>
                  <li>Check the browser console for additional error details</li>
                </ul>
              </div>

              <button
                onClick={() => window.location.reload()}
                className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
              >
                Reload Dashboard
              </button>

              <a
                href="/api/status"
                className="block text-center text-sm text-blue-400 hover:text-blue-300"
              >
                Check API Status →
              </a>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
