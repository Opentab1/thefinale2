// AWS Cognito Configuration
export const awsConfig = {
  Auth: {
    Cognito: {
      userPoolId: 'us-east-2_I6EBJm3te',
      userPoolClientId: '4v7vp7trh72q1priqno9k5prsq',
      region: 'us-east-2',
      loginWith: {
        email: true
      }
    }
  }
}

// AWS IoT Configuration for RPi data streaming
export const iotConfig = {
  region: 'us-east-2',
  endpoint: 'wss://iot.us-east-2.amazonaws.com/mqtt',
  clientId: 'pulse-dashboard-' + Math.random().toString(36).substring(7)
}
