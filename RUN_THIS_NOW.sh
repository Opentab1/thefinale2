#!/bin/bash
echo "================================================================================"
echo "🚨 CRITICAL AUDIO FIX - AUTOMATED DEPLOYMENT"
echo "================================================================================"
echo ""
echo "This will:"
echo "  1. Deploy the bulletproof audio fix"
echo "  2. Start the system"
echo "  3. Run verification tests"
echo "  4. Show you the status"
echo ""
read -p "Press ENTER to continue or Ctrl+C to cancel..."

cd /workspace

echo ""
echo "Step 1: Deploying fix..."
./DEPLOY_CRITICAL_AUDIO_FIX.sh

echo ""
echo "Step 2: Starting system in background..."
nohup python3 services/hub/main.py > /tmp/pulse_hub.log 2>&1 &
PULSE_PID=$!
echo "System started (PID: $PULSE_PID)"

echo ""
echo "Step 3: Waiting 10 seconds for system to initialize..."
sleep 10

echo ""
echo "Step 4: Running verification tests..."
python3 test_audio_resilience.py

echo ""
echo "================================================================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "================================================================================"
echo ""
echo "Your system is now running in the background."
echo ""
echo "To monitor health in real-time:"
echo "  python3 monitor_audio_health.py"
echo ""
echo "To view logs:"
echo "  tail -f /tmp/pulse_hub.log"
echo ""
echo "To stop the system:"
echo "  kill $PULSE_PID"
echo ""
echo "================================================================================"
