import { useState, useEffect } from 'react'
import { fetchAuthSession } from 'aws-amplify/auth'
import AWS from 'aws-sdk'
import AWSIoT from 'aws-iot-device-sdk'
import { awsConfig } from '../aws-config'

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

        if (!identityPoolId) {
          console.warn('AWS IoT: identityPoolId not configured; skipping IoT connection')
          return
        }

        const session = await fetchAuthSession()
        const idToken = session?.tokens?.idToken?.toString()

        if (!idToken) {
          console.warn('AWS IoT: No ID token; user not authenticated?')
          return
        }

        AWS.config.region = REGION
        AWS.config.credentials = new AWS.CognitoIdentityCredentials({
          IdentityPoolId: identityPoolId,
          Logins: {
            [`cognito-idp.${REGION}.amazonaws.com/${userPoolId}`]: idToken,
          },
        })

        await new Promise((resolve, reject) => {
          AWS.config.credentials.refresh((err) => (err ? reject(err) : resolve()))
        })

        if (cancelled) return

        const creds = AWS.config.credentials
        const clientId = `pulse-web-${Math.random().toString(16).slice(2)}`

        device = AWSIoT.device({
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
