import json
import os
import threading
import time
from typing import Callable, Optional

try:
    from paho.mqtt import client as mqtt_client  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    mqtt_client = None  # type: ignore


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _build_client() -> Optional["mqtt_client.Client"]:
    if mqtt_client is None:
        return None

    endpoint = _get_env("AWS_IOT_ENDPOINT", "a1h5tm3jvbz8cg-ats.iot.us-east-2.amazonaws.com")
    port_str = _get_env("AWS_IOT_PORT", "8883")
    try:
        port = int(port_str) if port_str else 8883
    except ValueError:
        port = 8883

    root_ca = _get_env("AWS_IOT_ROOT_CA", "/home/pi/pulse/AmazonRootCA1.pem")
    certfile = _get_env("AWS_IOT_CERT", "/home/pi/pulse/device.crt")
    keyfile = _get_env("AWS_IOT_PRIVATE_KEY", "/home/pi/pulse/private.key")

    client_id = _get_env("AWS_IOT_CLIENT_ID", "local-sync")

    client = mqtt_client.Client(client_id)
    client.tls_set(ca_certs=root_ca, certfile=certfile, keyfile=keyfile)
    client.connect(endpoint, port)
    client.loop_start()
    return client


def start_aws_sync(record_provider: Callable[[], dict], interval_seconds: int = 30) -> Optional[threading.Thread]:
    """
    Starts a daemon thread that publishes sensor records to AWS IoT Core.

    record_provider: returns a single record dict; this module wraps into a list
    interval_seconds: publish interval
    """
    topic = _get_env("AWS_IOT_TOPIC", "pulse/fergs-stpete/main-floor")

    def _loop():
        client = None
        backoff_seconds = 5
        while True:
            try:
                if client is None:
                    client = _build_client()
                    if client is None:
                        # paho-mqtt not installed; skip sync silently
                        time.sleep(interval_seconds)
                        continue

                record = record_provider() or {}
                payload = json.dumps([record])
                if topic:
                    client.publish(topic, payload)
                time.sleep(interval_seconds)
                # reset backoff after a successful publish
                backoff_seconds = 5
            except Exception:
                # Recreate client on any error and backoff
                try:
                    if client is not None:
                        client.loop_stop()
                        client.disconnect()
                except Exception:
                    pass
                client = None
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 300)

    thread = threading.Thread(target=_loop, daemon=True, name="aws-sync-thread")
    thread.start()
    return thread
