# AI Bartender Counter - Architecture Vision

## Overview
This document describes how an **AI Bartender Counter** feature would integrate into the existing Pulse system architecture, **without making any code changes**. This shows the conceptual design and how it would appear in the system.

---

## 🍹 Feature Concept

An AI-powered sensor that counts how many drinks a bartender makes per hour using computer vision. The system would:
- Monitor the bar area via camera
- Detect drink-making actions (shaking, pouring, mixing, serving)
- Track drink counts per hour
- Display real-time metrics on the dashboard
- Store historical data for analytics

---

## 🏗️ Architecture Integration

### 1. **Sensor Service** (`services/sensors/bartender_counter.py`)

Following the same pattern as `camera_people.py`, this would be a new sensor module:

```python
class BartenderCounter:
    def __init__(self):
        # Similar to PeopleCounter
        self.running = False
        self.drinks_this_hour = 0
        self.drinks_today = 0
        self.detection_confidence = 0.0
        self.last_drink_time = None
        
    def start_counting(self):
        # Background thread monitoring bar area
        # Uses similar CV detection as people counter
        
    def get_hourly_count(self):
        return self.drinks_this_hour
        
    def get_daily_count(self):
        return self.drinks_today
```

**Integration Points:**
- Would be initialized in `services/hub/main.py` (similar to how `PeopleCounter` is initialized)
- Would follow the same sensor lifecycle pattern (start/stop)
- Would use the same camera infrastructure (or a separate camera focused on bar area)

---

### 2. **Hub Integration** (`services/hub/main.py`)

The hub would initialize and manage the bartender counter:

```python
# In _init_components():
self.bartender_counter = None

if modules.get('bartender_counter'):
    self.bartender_counter = BartenderCounter()
    self.bartender_counter.start_counting()

# In _collect_sensor_data():
data = {
    # ... existing fields ...
    "drinks_this_hour": 0,
    "drinks_today": 0,
    "bartender_active": False,
    "avg_drinks_per_hour": 0.0
}

if self.bartender_counter:
    data["drinks_this_hour"] = self.bartender_counter.get_hourly_count()
    data["drinks_today"] = self.bartender_counter.get_daily_count()
    data["bartender_active"] = self.bartender_counter.is_active()
    data["avg_drinks_per_hour"] = self.bartender_counter.get_avg_hourly_rate()
```

---

### 3. **Database Schema** (`services/storage/db.py`)

A new table would store drink counts:

```sql
CREATE TABLE IF NOT EXISTS drinks_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    drinks_count INTEGER NOT NULL,
    hour_of_day INTEGER,
    day_of_week INTEGER,
    confidence REAL,
    metadata TEXT
)
```

The database methods would include:
- `log_drink(drinks_count, confidence)`
- `get_hourly_drinks(hours=24)`
- `get_daily_drinks(days=7)`
- `get_avg_drinks_per_hour()`

---

### 4. **Dashboard API** (`dashboard/api/server.py`)

New REST endpoints would expose drink data:

```python
@app.route('/api/bartender/current')
def get_current_drinks():
    """Get current hour drink count"""
    if hub_instance and hub_instance.bartender_counter:
        data = {
            "drinks_this_hour": hub_instance.bartender_counter.get_hourly_count(),
            "drinks_today": hub_instance.bartender_counter.get_daily_count(),
            "timestamp": datetime.now().isoformat()
        }
        return jsonify(data)
    return jsonify({"error": "Bartender counter not available"}), 404

@app.route('/api/bartender/history')
def get_drinks_history():
    """Get drink count history"""
    hours = request.args.get('hours', default=24, type=int)
    data = db.get_hourly_drinks(hours)
    return jsonify(data)
```

**WebSocket Updates:**
- The existing `broadcast_sensor_data()` function would automatically include drink counts
- Frontend would receive real-time updates via `sensor_update` events

---

### 5. **Dashboard UI** (`dashboard/ui/src/components/LiveOverview.jsx`)

New metric cards would appear on the Live Overview page:

```jsx
// In LiveOverview component:
const {
  drinks_this_hour = 0,
  drinks_today = 0,
  avg_drinks_per_hour = 0,
  bartender_active = false
} = sensorData

// New MetricCard components:
<MetricCard
  icon={<Cocktail className="w-8 h-8" />}
  title="Drinks This Hour"
  value={drinks_this_hour}
  unit="drinks"
  color="orange"
/>

<MetricCard
  icon={<Clock className="w-8 h-8" />}
  title="Average/Hour"
  value={avg_drinks_per_hour?.toFixed(1) || '-'}
  unit="drinks/hr"
  color="blue"
/>

<MetricCard
  icon={<TrendingUp className="w-8 h-8" />}
  title="Today's Total"
  value={drinks_today}
  unit="drinks"
  color="green"
/>
```

**Visual Appearance:**
- Cards would match the existing design (gray-800 background, rounded-xl, border)
- Icons from lucide-react (same as other metrics)
- Real-time updates via WebSocket (same as occupancy, temperature, etc.)
- Would appear in the grid alongside other metrics

---

### 6. **Analytics Page** (`dashboard/ui/src/components/Analytics.jsx`)

New charts and graphs would show drink trends:

```jsx
// Hourly drink count chart
<LineChart
  data={drinksHistory}
  xKey="hour"
  yKey="drinks"
  title="Drinks Per Hour (Last 24 Hours)"
/>

// Peak hours analysis
<BarChart
  data={peakHours}
  title="Peak Drink-Making Hours"
/>

// Daily comparison
<ComparisonChart
  data={dailyComparison}
  title="Daily Drink Count Comparison"
/>
```

---

## 📊 Dashboard Visualization

### Live Overview Page

The dashboard would show:

```
┌─────────────────────────────────────────────────────────┐
│  Live Overview                                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ Occupancy   │  │ Temperature │  │ Drinks/Hour │   │
│  │     3       │  │   72.5°F    │  │     12      │   │
│  │   people    │  │             │  │   drinks    │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ Humidity    │  │ Light Level │  │ Avg/Hour    │   │
│  │   45.2%     │  │   450 lux   │  │   10.5     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Drinks Today: 87 | Peak Hour: 8-9 PM (18 drinks)│  │
│  │ Current Hour: 12 drinks | Trend: ↗️ +2.3/hr    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Analytics Page

Would include sections like:

- **Drink Production Trends**
  - Line chart showing drinks per hour over time
  - Bar chart comparing daily totals
  - Heatmap showing peak hours/days

- **Performance Metrics**
  - Average drinks per hour
  - Busiest hour of day
  - Busiest day of week
  - Production rate (drinks/minute during active periods)

---

## 🔄 Data Flow

```
Camera (Bar Area)
    ↓
BartenderCounter Sensor
    ↓ (detects drink-making actions)
    ↓
Hub (_collect_sensor_data)
    ↓
Database (drinks_log table)
    ↓
Dashboard API (/api/bartender/current)
    ↓
WebSocket (sensor_update event)
    ↓
React Dashboard (LiveOverview component)
    ↓
Real-time UI Updates
```

---

## 🎯 Detection Strategy

The AI would detect drink-making through:

1. **Motion Patterns**
   - Shaking motion (cocktail shaker)
   - Pouring motion (bottle to glass)
   - Mixing motion (stirring)

2. **Object Recognition**
   - Glass/bottle presence in bar area
   - Shaker/strainer detection
   - Serving gestures

3. **Temporal Analysis**
   - Duration of actions (typical drink prep time)
   - Sequence of motions (shaking → pouring → serving)
   - Correlation with serving area activity

4. **Confidence Scoring**
   - Each detection has confidence level (0.0 - 1.0)
   - Only counts above threshold (e.g., 0.7)
   - Prevents false positives from general movement

---

## 📈 Configuration

Would be added to `config/config.yaml`:

```yaml
modules:
  camera: true
  mic: true
  bme280: true
  bartender_counter: true  # New module

bartender_counter:
  enabled: true
  camera_index: 0  # Or separate camera
  confidence_threshold: 0.7
  detection_zone: "bar_area"  # ROI coordinates
  reset_hourly: true
  min_detection_interval: 5  # seconds between detections
```

---

## 🔧 System Integration

### Health Monitoring
- Would appear in `SystemHealth` component
- Status: Active/Inactive
- Detection rate metrics
- Confidence score trends

### Automation Potential
- Could trigger HVAC adjustments (more people = more drinks = more heat)
- Could adjust lighting based on activity
- Could correlate with music volume (busy = louder)

### Logging
- Would log to `automation_log` table
- Events like: "Drink count threshold reached", "Peak hour detected"

---

## 🎨 UI/UX Notes

**Color Scheme:**
- Orange/amber for drink-related metrics (distinct from blue/red/green used elsewhere)
- Animated progress bars showing hourly progress
- Sparkline charts showing recent trend

**Real-time Indicators:**
- Pulse animation when drink detected
- Sound effect option (configurable)
- Notification badges for milestones (e.g., "100 drinks today!")

**Mobile Responsive:**
- Cards stack on mobile (same as other metrics)
- Touch-friendly controls
- Swipe gestures for historical data

---

## 📊 Example Data Structure

```json
{
  "drinks_this_hour": 12,
  "drinks_today": 87,
  "avg_drinks_per_hour": 10.5,
  "bartender_active": true,
  "last_drink_time": "2024-01-15T14:32:10Z",
  "peak_hour": {
    "hour": 20,
    "count": 18
  },
  "hourly_breakdown": [
    {"hour": 14, "count": 12},
    {"hour": 15, "count": 15},
    {"hour": 16, "count": 18}
  ]
}
```

---

## 🚀 Technical Implementation Notes

**Similar to Existing Sensors:**
- Follows same pattern as `PeopleCounter`
- Uses same camera infrastructure
- Integrates with same hub orchestration
- Uses same database patterns
- Follows same API structure
- Uses same WebSocket updates
- Matches same UI component patterns

**Key Differences:**
- Focuses on bar area (could use separate camera or ROI)
- Detects actions rather than just people
- Tracks temporal patterns (hourly counts)
- May need more sophisticated CV (action recognition vs object detection)

**Performance Considerations:**
- Could run on same camera feed as people counter (with ROI)
- Or use dedicated camera for bar area
- Could leverage AI HAT acceleration (like people counter does)
- Detection runs in background thread (non-blocking)

---

## 📝 Summary

The AI Bartender Counter would seamlessly integrate into the existing Pulse architecture:

1. **Sensor Layer**: New `BartenderCounter` class following `PeopleCounter` pattern
2. **Hub Layer**: Initialized and managed like other sensors
3. **Database Layer**: New `drinks_log` table storing hourly counts
4. **API Layer**: New REST endpoints and WebSocket updates
5. **UI Layer**: New metric cards in LiveOverview, charts in Analytics

The feature would **look and feel** identical to existing sensors - appearing as metric cards on the dashboard, updating in real-time, and providing historical analytics. It would be a natural extension of the current system architecture, following all established patterns and conventions.
