#!/usr/bin/env python3
"""
Bartender Feature Integration Test
Run this on the Raspberry Pi after installation to verify everything works
"""

import sys
import os

# Add workspace to path
sys.path.insert(0, '/opt/pulse')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database():
    """Test database integration"""
    print("\n" + "="*60)
    print("TEST 1: DATABASE INTEGRATION")
    print("="*60)
    
    try:
        from services.storage.db import PulseDB
        db = PulseDB()
        print("✅ Database initialized")
        
        # Add test bartenders
        bid1 = db.add_bartender("Sarah")
        bid2 = db.add_bartender("Mike")
        bid3 = db.add_bartender("Alex")
        print(f"✅ Added 3 bartenders: {bid1}, {bid2}, {bid3}")
        
        # Log drinks
        db.log_bartender_drink(bid1, 'cocktail')
        db.log_bartender_drink(bid1, 'beer')
        db.log_bartender_drink(bid2, 'shot')
        print("✅ Logged 3 drinks")
        
        # Get stats
        stats = db.get_bartender_stats(hours=24)
        print(f"✅ Retrieved stats for {len(stats)} bartenders")
        
        total = db.get_total_drinks_today()
        print(f"✅ Total drinks today: {total}")
        
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bartender_tracker():
    """Test bartender tracker"""
    print("\n" + "="*60)
    print("TEST 2: BARTENDER TRACKER")
    print("="*60)
    
    try:
        from services.sensors.bartender_tracker import BartenderTracker
        import numpy as np
        
        tracker = BartenderTracker(camera_index=0)
        print("✅ Tracker initialized")
        
        # Set bar zone
        tracker.set_bar_zone(100, 100, 400, 300)
        print("✅ Bar zone configured")
        
        # Test feature extraction with dummy data
        dummy_person = np.random.randint(0, 255, (128, 64, 3), dtype=np.uint8)
        features = tracker._extract_appearance_features(dummy_person)
        print(f"✅ Feature extraction works (vector size: {features.shape})")
        
        # Create test bartenders
        bid1 = tracker._create_new_bartender(features)
        bid2 = tracker._create_new_bartender(features * 0.5)
        print(f"✅ Created 2 bartenders: {bid1}, {bid2}")
        
        # Record drinks
        tracker.record_drink(bid1)
        tracker.record_drink(bid1)
        tracker.record_drink(bid2)
        print(f"✅ Recorded 3 drinks (total: {tracker.total_drinks_today})")
        
        # Get stats
        stats = tracker.get_stats()
        print(f"✅ Stats: {stats['total_drinks_today']} drinks, {stats['tracked_bartenders']} bartenders")
        print(f"✅ Privacy mode: {stats['privacy_mode']}")
        
        return True
    except Exception as e:
        print(f"❌ Tracker test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_server():
    """Test API server routes"""
    print("\n" + "="*60)
    print("TEST 3: API SERVER")
    print("="*60)
    
    try:
        from dashboard.api.server import app
        
        # Check routes
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        bartender_routes = [r for r in routes if 'bartender' in r]
        
        print(f"✅ Found {len(bartender_routes)} bartender API routes:")
        for route in bartender_routes:
            print(f"   - {route}")
        
        # Verify required routes exist
        required = [
            '/api/bartender/stats',
            '/api/bartender/list',
            '/api/bartender/drink',
            '/api/bartender/snapshot'
        ]
        
        missing = [r for r in required if r not in bartender_routes]
        if missing:
            print(f"❌ Missing routes: {missing}")
            return False
        
        print("✅ All required routes present")
        
        # Check existing routes still work
        existing = ['/api/status', '/api/sensors/current', '/api/health']
        for route in existing:
            if route in routes:
                print(f"✅ Existing route still works: {route}")
            else:
                print(f"❌ Existing route broken: {route}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_component():
    """Test UI component exists"""
    print("\n" + "="*60)
    print("TEST 4: UI COMPONENT")
    print("="*60)
    
    try:
        import os
        
        # Check BartenderDashboard.jsx exists
        ui_path = '/opt/pulse/dashboard/ui/src/components/BartenderDashboard.jsx'
        alt_path = os.path.join(os.path.dirname(__file__), 'dashboard/ui/src/components/BartenderDashboard.jsx')
        
        if os.path.exists(ui_path):
            print(f"✅ BartenderDashboard.jsx found at {ui_path}")
        elif os.path.exists(alt_path):
            print(f"✅ BartenderDashboard.jsx found at {alt_path}")
        else:
            print(f"❌ BartenderDashboard.jsx not found")
            return False
        
        # Check App.jsx was modified
        app_path = '/opt/pulse/dashboard/ui/src/App.jsx'
        alt_app_path = os.path.join(os.path.dirname(__file__), 'dashboard/ui/src/App.jsx')
        
        for path in [app_path, alt_app_path]:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    content = f.read()
                
                if 'BartenderDashboard' in content and '/bartender' in content:
                    print(f"✅ App.jsx properly integrated at {path}")
                    return True
        
        print("❌ App.jsx integration not found")
        return False
        
    except Exception as e:
        print(f"❌ UI test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print(" "*15 + "🍸 BARTENDER FEATURE INTEGRATION TEST 🍸")
    print("="*70)
    
    results = {
        'Database': test_database(),
        'Bartender Tracker': test_bartender_tracker(),
        'API Server': test_api_server(),
        'UI Component': test_ui_component()
    }
    
    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:.<50} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n" + "🎉"*35)
        print(" "*20 + "ALL TESTS PASSED!")
        print("🎉"*35)
        print("\n✅ Bartender feature is ready to use!")
        print("   Start the dashboard and click the 'Bartender' tab")
        return 0
    else:
        print("\n" + "❌"*35)
        print(" "*20 + "SOME TESTS FAILED")
        print("❌"*35)
        failed = [name for name, passed in results.items() if not passed]
        print(f"\nFailed tests: {', '.join(failed)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
