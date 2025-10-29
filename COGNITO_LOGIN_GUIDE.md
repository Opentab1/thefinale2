# AWS Cognito Login - User Guide

## 🔐 How to Access Pulse Dashboard

### Production URL
**https://dashboard.advizia.ai**

Alternative: https://main.dbrzsy5y2d67d.amplifyapp.com

## First Time Setup

### 1. Create Your Account

1. Visit https://dashboard.advizia.ai
2. Click **"Don't have an account? Sign up"**
3. Enter your email address
4. Create a password (minimum 8 characters)
5. Click **"Sign Up"**

### 2. Verify Your Email

1. Check your email inbox
2. Look for a message from AWS Cognito
3. Copy the 6-digit verification code
4. Return to the dashboard
5. Enter the code
6. Click **"Confirm Account"**

### 3. Sign In

1. Click **"Sign In"**
2. Enter your verified email
3. Enter your password
4. Click **"Sign In"**

You're now logged in! 🎉

## Features Available After Login

### Dashboard Access
- ✅ Live sensor monitoring
- ✅ Control automation systems
- ✅ View analytics
- ✅ Manage multiple locations
- ✅ Configure settings
- ✅ Access AWS IoT status

### Header Controls
- **Location Selector** - Switch between venues
- **Connection Status** - View real-time connection
- **Safe Mode** - Emergency automation override
- **Sign Out** - Securely log out

## Managing Locations

### Add a New Location

1. Navigate to **Settings** tab
2. Scroll to **"Location Management"**
3. Enter location name (e.g., "Downtown Venue")
4. Enter address (optional)
5. Click **"Add Location"**

### Switch Locations

1. Go to Settings → Location Management
2. Find the location you want
3. Click **"Switch to this location"**
4. Or use the location indicator in the header

### Remove a Location

1. Go to Settings → Location Management
2. Click the red trash icon next to the location
3. Location is immediately removed

## GoDaddy Domain Management

### Access Domain Settings

1. Navigate to **Settings** tab
2. Click **"Manage Domain on GoDaddy"** button (top right)
3. Opens GoDaddy in new tab
4. Manage DNS, SSL, and other domain settings

### Current Domain Setup
- **Primary:** dashboard.advizia.ai
- **Points to:** AWS Amplify
- **SSL:** Auto-configured by Amplify

## AWS Configuration Details

### Cognito User Pool
```
User Pool ID: us-east-2_I6EBJm3te
App Client ID: 4v7vp7trh72q1priqno9k5prsq
Region: us-east-2
```

### Features
- ✓ Secure authentication
- ✓ Email verification
- ✓ Password reset (coming soon)
- ✓ Session management
- ✓ Automatic token refresh

### Security
- Passwords must be at least 8 characters
- Email verification required
- Sessions expire after inactivity
- All traffic encrypted (HTTPS)

## Troubleshooting

### "Cannot sign in"
**Possible causes:**
- Email not verified yet
- Wrong password
- Account doesn't exist

**Solutions:**
1. Check spam folder for verification email
2. Try password reset (if available)
3. Create new account if needed

### "Connection failed"
**Possible causes:**
- Internet connection issue
- Server maintenance
- Browser issue

**Solutions:**
1. Check your internet connection
2. Refresh the page (F5)
3. Try a different browser
4. Clear browser cache

### "No data showing"
**Possible causes:**
- RPi not sending data
- Location mismatch
- IoT bridge offline

**Solutions:**
1. Check RPi is powered on
2. Verify IoT bridge is running
3. Check selected location matches RPi location
4. See AWS_IOT_SETUP.md for details

### Verification Email Not Received
1. Check spam/junk folder
2. Wait a few minutes (can take up to 5 min)
3. Add no-reply@verificationemail.com to contacts
4. Try signing up with different email

## Password Requirements

Your password must have:
- ✓ Minimum 8 characters
- ✓ At least one number (recommended)
- ✓ At least one special character (recommended)

Strong password example: `MyPulse2024!`

## Session Management

### Automatic Sign Out
- Sessions expire after 30 days of inactivity
- You'll be redirected to login page
- Simply sign in again to continue

### Manual Sign Out
1. Click **"Sign Out"** button in header
2. You'll be returned to login page
3. All session data is cleared

### Remember Me
- Sessions persist across browser restarts
- Stored securely in browser
- Automatic token refresh
- No need to sign in every time

## Multi-Device Access

### Use on Multiple Devices
- ✅ Same account works on all devices
- ✅ Phone, tablet, desktop
- ✅ Any modern browser
- ✅ PWA installable on mobile

### Install as App (Mobile)

**iOS:**
1. Open in Safari
2. Tap Share button
3. Tap "Add to Home Screen"
4. Tap "Add"

**Android:**
1. Open in Chrome
2. Tap menu (⋮)
3. Tap "Install app"
4. Tap "Install"

## Privacy & Data

### What We Store
- Email address
- Hashed password (never plain text)
- Session tokens
- Location preferences
- Settings

### What We Don't Store
- Credit card information
- Personal identification
- Location tracking
- Usage analytics (optional)

### Data Security
- All data encrypted in transit (HTTPS)
- Passwords hashed with AWS Cognito
- No third-party access
- GDPR compliant

## Getting Help

### Documentation
- Main README: `/workspace/README.md`
- IoT Setup: `/workspace/AWS_IOT_SETUP.md`
- Deployment Guide: `/workspace/DEPLOYMENT_COMPLETE.md`

### Common Questions

**Q: Can I change my email?**
A: Currently not supported. Create new account if needed.

**Q: Can I change my password?**
A: Password reset feature coming soon.

**Q: How many locations can I add?**
A: Unlimited locations supported.

**Q: Is my data backed up?**
A: Yes, AWS handles all backups automatically.

**Q: Can multiple users access same location?**
A: Yes, each user has their own account and can access any location.

## Admin Features (Coming Soon)

- [ ] User management
- [ ] Role-based access control
- [ ] Team invitations
- [ ] Audit logs
- [ ] Usage reports

## Contact & Support

For issues or questions:
1. Check this guide first
2. Review AWS_IOT_SETUP.md
3. Check browser console for errors
4. Contact system administrator

---

**Live Dashboard:** https://dashboard.advizia.ai
**Repository:** https://github.com/Opentab1/thefinale2
**Powered by:** AWS Cognito, AWS IoT Core, AWS Amplify

*Last Updated: 2025-10-29*
