import { useState, useEffect } from 'react'
import { awsConfig, isAuthConfigured } from '../aws-config'

// Exact IoT values provided
const IOT_ENDPOINT = 'a1h5tm3jvbz8cg-ats.iot.us-east-2.amazonaws.com'
const IOT_TOPIC = 'pulse/fergs-stpete/main-floor'
const REGION = 'us-east-2'

export function useIoTData() {
  const [iotData, setIoTData] = useState({})
  const [iotConnected, setIoTConnected] = useState(false)

  useEffect(() => {
    let device = null
    let cancelled = false

    const connect = async () => {
      try {
        const identityPoolId = awsConfig?.Auth?.Cognito?.identityPoolId || ''
        const userPoolId = awsConfig?.Auth?.Cognito?.userPoolId

        // Skip IoT connection if auth is not configured or no identity pool
        if (!isAuthConfigured || !identityPoolId) {
          console.log('AWS IoT: Authentication not configured; skipping IoT connection')
          return
        }

        // Dynamically import AWS SDK only when needed to avoid bundle bloat
        const { fetchAuthSession } = await import('aws-amplify/auth')
        const AWS = await import('aws-sdk')
        const AWSIoT = await import('aws-iot-device-sdk')

        const session = await fetchAuthSession()
        const idToken = session?.tokens?.idToken?.toString()

        if (!idToken) {
          console.warn('AWS IoT: No ID token; user not authenticated?')
          return
        }

        AWS.default.config.region = REGION
        AWS.default.config.credentials = new AWS.default.CognitoIdentityCredentials({
          IdentityPoolId: identityPoolId,
          Logins: {
            [`cognito-idp.${REGION}.amazonaws.com/${userPoolId}`]: idToken,
          },
        })

        await new Promise((resolve, reject) => {
          AWS.default.config.credentials.refresh((err) => (err ? reject(err) : resolve()))
        })

        if (cancelled) return

        const creds = AWS.default.config.credentials
        const clientId = `pulse-web-${Math.random().toString(16).slice(2)}`

        device = AWSIoT.default.device({
          region: REGION,
          host: IOT_ENDPOINT,
          clientId,
          protocol: 'wss',
          maximumReconnectTimeMs: 8000,
          keepalive: 30,
          accessKeyId: creds.accessKeyId,
          secretKey: creds.secretAccessKey,
          sessionToken: creds.sessionToken,
        })

        device.on('connect', () => {
          if (cancelled) return
          setIoTConnected(true)
          device.subscribe(IOT_TOPIC)
        })

        device.on('message', (_topic, payload) => {
          try {
            const data = JSON.parse(payload?.toString?.() || '{}')
            // Data should already match UI schema from publisher
            setIoTData((prev) => ({ ...prev, ...data }))
          } catch (e) {
            console.error('AWS IoT: Failed to parse payload', e)
          }
        })

        device.on('error', (err) => {
          console.error('AWS IoT error:', err)
        })

      } catch (e) {
        console.error('AWS IoT: connection failed', e)
      }
    }

    connect()

    return () => {
      cancelled = true
      setIoTConnected(false)
      try {
        if (device) device.end(true)
      } catch {}
    }
  }, [])

  return { iotData, iotConnected }
}
