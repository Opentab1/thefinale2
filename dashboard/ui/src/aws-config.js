/**
 * AWS Amplify Configuration
 * 
 * This file configures AWS Cognito authentication for the Pulse dashboard.
 * 
 * To enable authentication:
 * 1. Create a Cognito User Pool in AWS Console
 * 2. Create an App Client (disable client secret for browser apps)
 * 3. Fill in the values below with your pool details
 * 4. Optional: Create an Identity Pool for IoT access
 * 
 * Environment variables can override these settings:
 * - VITE_COGNITO_REGION
 * - VITE_COGNITO_USER_POOL_ID  
 * - VITE_COGNITO_USER_POOL_CLIENT_ID
 * - VITE_COGNITO_IDENTITY_POOL_ID
 */

export const awsConfig = {
  Auth: {
    Cognito: {
      region: import.meta.env.VITE_COGNITO_REGION || 'us-east-1',
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || 'us-east-1_XXXXXXXXX',
      userPoolClientId: import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID || 'xxxxxxxxxxxxxxxxxxxx',
      identityPoolId: import.meta.env.VITE_COGNITO_IDENTITY_POOL_ID || '',
      
      // Optional: Domain for hosted UI
      loginWith: {
        oauth: {
          domain: import.meta.env.VITE_COGNITO_DOMAIN || '',
          scopes: ['openid', 'email', 'profile'],
          redirectSignIn: [window.location.origin],
          redirectSignOut: [window.location.origin],
          responseType: 'code',
        },
      },
    },
  },
}

// Development mode: Check if Cognito is configured
const isConfigured = 
  awsConfig.Auth.Cognito.userPoolId !== 'us-east-1_XXXXXXXXX' &&
  awsConfig.Auth.Cognito.userPoolClientId !== 'xxxxxxxxxxxxxxxxxxxx'

if (!isConfigured && import.meta.env.DEV) {
  console.warn('⚠️  AWS Cognito is not configured. Authentication will not work.')
  console.warn('To enable authentication, edit dashboard/ui/src/aws-config.js or set environment variables.')
  console.warn('For local development without auth, you can bypass the login screen.')
}

export const isAuthConfigured = isConfigured
