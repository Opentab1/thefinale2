"""
Pulse 1.0 - System Watchdog
Comprehensive health monitoring and auto-recovery for critical components
Keeps song detector and database reader always running
"""

import logging
import time
import threading
from typing import Optional, Callable, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ComponentWatchdog:
    """Monitors a single component and auto-restarts on failure"""
    
    def __init__(self, name: str, check_fn: Callable, restart_fn: Callable, 
                 check_interval: float = 10.0, failure_threshold: int = 3):
        self.name = name
        self.check_fn = check_fn
        self.restart_fn = restart_fn
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        
        self.consecutive_failures = 0
        self.total_failures = 0
        self.total_restarts = 0
        self.last_check_time = 0.0
        self.last_failure_time = 0.0
        self.last_restart_time = 0.0
        self.status = "unknown"
        self.error = None
    
    def check_health(self) -> bool:
        """Check if component is healthy"""
        try:
            self.last_check_time = time.time()
            is_healthy = self.check_fn()
            
            if is_healthy:
                if self.consecutive_failures > 0:
                    logger.info(f"✅ {self.name} recovered after {self.consecutive_failures} failures")
                self.consecutive_failures = 0
                self.status = "healthy"
                self.error = None
                return True
            else:
                self.consecutive_failures += 1
                self.total_failures += 1
                self.last_failure_time = time.time()
                self.status = "unhealthy"
                self.error = "health_check_failed"
                logger.warning(
                    f"⚠️ {self.name} health check failed "
                    f"(consecutive: {self.consecutive_failures}/{self.failure_threshold})"
                )
                return False
        except Exception as e:
            self.consecutive_failures += 1
            self.total_failures += 1
            self.last_failure_time = time.time()
            self.status = "error"
            self.error = str(e)
            logger.error(f"⚠️ {self.name} health check error: {e}")
            return False
    
    def attempt_recovery(self) -> bool:
        """Attempt to restart the component"""
        try:
            logger.warning(f"🔄 Attempting to restart {self.name}...")
            self.restart_fn()
            self.total_restarts += 1
            self.last_restart_time = time.time()
            self.consecutive_failures = 0
            logger.info(f"✅ {self.name} restart successful")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to restart {self.name}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get component statistics"""
        return {
            "name": self.name,
            "status": self.status,
            "error": self.error,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "total_restarts": self.total_restarts,
            "last_check_time": self.last_check_time,
            "last_failure_time": self.last_failure_time,
            "last_restart_time": self.last_restart_time
        }


class SystemWatchdog:
    """Main watchdog that monitors all critical components"""
    
    def __init__(self, check_interval: float = 5.0):
        self.check_interval = check_interval
        self.components = {}
        self.running = False
        self.stop_event = threading.Event()
        self.watchdog_thread = None
        
        self.total_checks = 0
        self.total_recoveries = 0
        self.start_time = time.time()
    
    def register_component(self, name: str, check_fn: Callable, restart_fn: Callable,
                          check_interval: Optional[float] = None, 
                          failure_threshold: int = 3):
        """Register a component for monitoring"""
        interval = check_interval or self.check_interval
        component = ComponentWatchdog(name, check_fn, restart_fn, interval, failure_threshold)
        self.components[name] = component
        logger.info(f"📋 Registered {name} for watchdog monitoring")
    
    def start(self):
        """Start the watchdog"""
        if self.running:
            logger.warning("Watchdog already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()
        logger.info(f"🐕 System Watchdog started (monitoring {len(self.components)} components)")
    
    def stop(self):
        """Stop the watchdog"""
        self.running = False
        self.stop_event.set()
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=5.0)
        logger.info("🐕 System Watchdog stopped")
    
    def _watchdog_loop(self):
        """Main watchdog loop"""
        logger.info("🐕 Watchdog loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                for name, component in self.components.items():
                    # Check if it's time to check this component
                    time_since_check = current_time - component.last_check_time
                    
                    if time_since_check >= component.check_interval:
                        self.total_checks += 1
                        is_healthy = component.check_health()
                        
                        # Attempt recovery if threshold reached
                        if not is_healthy and component.consecutive_failures >= component.failure_threshold:
                            logger.error(
                                f"🚨 {name} has failed {component.consecutive_failures} times - "
                                f"initiating recovery!"
                            )
                            
                            success = component.attempt_recovery()
                            if success:
                                self.total_recoveries += 1
                            else:
                                logger.error(f"❌ Failed to recover {name} - will retry on next cycle")
                
                # Log periodic status
                if self.total_checks % 100 == 0:
                    self._log_summary()
                
                # Sleep until next check
                self.stop_event.wait(min([c.check_interval for c in self.components.values()] or [self.check_interval]))
                
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.stop_event.wait(5.0)
        
        logger.info("🐕 Watchdog loop stopped")
    
    def _log_summary(self):
        """Log a summary of watchdog status"""
        uptime = time.time() - self.start_time
        logger.info("=" * 80)
        logger.info(f"🐕 WATCHDOG STATUS (uptime: {uptime/3600:.1f}h, checks: {self.total_checks})")
        logger.info("=" * 80)
        
        for name, component in self.components.items():
            stats = component.get_stats()
            status_icon = "✅" if stats["status"] == "healthy" else "⚠️"
            logger.info(
                f"{status_icon} {name}: {stats['status']} | "
                f"Failures: {stats['total_failures']} | "
                f"Restarts: {stats['total_restarts']} | "
                f"Consecutive Failures: {stats['consecutive_failures']}"
            )
        
        logger.info(f"Total Recoveries: {self.total_recoveries}")
        logger.info("=" * 80)
    
    def get_status(self) -> Dict[str, Any]:
        """Get watchdog status"""
        return {
            "running": self.running,
            "uptime_seconds": time.time() - self.start_time,
            "total_checks": self.total_checks,
            "total_recoveries": self.total_recoveries,
            "components": {name: comp.get_stats() for name, comp in self.components.items()},
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create watchdog
    watchdog = SystemWatchdog(check_interval=5.0)
    
    # Example: Monitor a dummy component
    def check_dummy():
        return True
    
    def restart_dummy():
        logger.info("Restarting dummy component...")
    
    watchdog.register_component("dummy", check_dummy, restart_dummy)
    
    # Start watchdog
    watchdog.start()
    
    try:
        while True:
            time.sleep(10)
            status = watchdog.get_status()
            logger.info(f"Watchdog status: {status}")
    except KeyboardInterrupt:
        watchdog.stop()
