# SPDX-License-Identifier: MIT
# CircuitPython 10.x LED Matrix Scroller - Properly Refactored
# Clean architecture without typing imports or unsupported features

import gc
import io
import time
import json
import binascii
import ipaddress
import ssl
from collections import deque

import wifi
import socketpool
import adafruit_requests
import microcontroller
from adafruit_matrixportal.matrix import Matrix
from messageboard import MessageBoard
from messageboard.fontpool import FontPool
from messageboard.message import Message

from secrets import secrets


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Centralized configuration constants."""

    # Display
    WIDTH = 128
    HEIGHT = 32
    BIT_DEPTH = 5
    DEFAULT_COLOR = 0xFFFFFF
    DEFAULT_FONT = "lemon"
    MASK_COLOR = 0xE127F9

    # Timing
    POLL_PERIOD = 30  # seconds between IO polls
    BUSY_WAIT = 2     # seconds after processing a message
    IDLE_WAIT = 10    # seconds when queues are empty

    # Networking
    WIFI_TIMEOUT = 30
    WIFI_IP_TIMEOUT = 15
    HTTP_TIMEOUT = 10
    MAX_RETRIES = 3
    CONN_CHECK_RETRIES = 3

    # Adafruit IO
    FETCH_LIMIT = 5
    QUEUE_CAPACITY = 250

    # Fonts
    FONTS = {
        "bmilk": "fonts/Bettermilk-16.pcf",
        "comic8": "fonts/Comicate-14.pcf",
        "coolv": "fonts/Coolvetica-14.pcf",
        "handv": "fonts/Handvetica-14.pcf",
        "lemon": "fonts/LemonMilk-10.pcf",
        "showcard": "fonts/Showcard-12.pcf",
    }

    # Animation definitions: (type, name, kwargs_dict)
    ANIMATIONS = {
        "in_right": ("Scroll", "in_from_right", {}),
        "in_left": ("Scroll", "in_from_left", {}),
        "out_right": ("Scroll", "out_to_right", {}),
        "out_left": ("Scroll", "out_to_left", {}),
        "in_top": ("Scroll", "in_from_top", {"duration": 2}),
        "in_bottom": ("Scroll", "in_from_bottom", {"duration": 2}),
        "out_top": ("Scroll", "out_to_top", {"duration": 2}),
        "out_bottom": ("Scroll", "out_to_bottom", {"duration": 2}),
        "flash": ("Static", "flash", {"count": 3, "duration": 1.5}),
        "blink": ("Static", "blink", {"count": 3, "duration": 1.5}),
        "fade": ("Static", "fade_in_out", {"duration": 3}),
        "none": None,
    }

    # Multi-step effects: [(effect_name, delay), ...]
    MULTI_STEP_FX = {
        "none": [("in_right", 0), ("out_left", 0)],
        "left2right": [("in_right", 0), ("out_left", 0)],
        "right2left": [("in_right", 0), ("out_left", 0)],
        "left2left": [("in_left", 0), ("out_left", 0)],
        "right2right": [("in_right", 0), ("out_right", 0)],
        "top2top": [("in_top", 2), ("out_top", 0)],
        "bottom2bottom": [("in_bottom", 2), ("out_bottom", 0)],
        "top2bottom": [("in_top", 2), ("out_bottom", 0)],
        "bottom2top": [("in_bottom", 2), ("out_top", 0)],
    }

    @staticmethod
    def screen_off_path():
        return f"images/{Config.WIDTH}/ledbg00.bmp"

    @staticmethod
    def image_path(filename):
        return f"images/{Config.WIDTH}/{filename}.bmp"


# ============================================================================
# UTILITIES
# ============================================================================

def feed_watchdog():
    """Feed watchdog if available, silently ignore if not."""
    try:
        microcontroller.watchdog.feed()
    except (AttributeError, RuntimeError):
        pass


def parse_color(color_value):
    """Parse color from string (#RRGGBB) or int (0xRRGGBB)."""
    if isinstance(color_value, str):
        return int(color_value.lstrip('#'), 16)
    return int(color_value)


def format_ip(address):
    """Convert various IP address types to dotted string."""
    if hasattr(address, 'compressed'):
        return address.compressed
    if hasattr(address, 'packed'):
        return ".".join(str(b) for b in address.packed)
    return str(address)


def format_uptime(seconds, parts=3):
    """Format seconds as human-readable uptime string."""
    intervals = [("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = []
    for suffix, duration in intervals:
        if seconds >= duration:
            value = int(seconds // duration)
            seconds %= duration
            result.append(f"{value}{suffix}")
    return ", ".join(result[:parts]) if result else "0s"


# ============================================================================
# LOGGER
# ============================================================================

class Logger:
    """Simple logging utility for structured output."""

    def __init__(self, verbose=True):
        self.verbose = verbose
        self.start_time = time.monotonic()

    def info(self, message):
        """Log informational message."""
        if self.verbose:
            print(f"[INFO] {message}")

    def error(self, message, exception=None):
        """Log error message with optional exception."""
        print(f"[ERROR] {message}")
        if exception:
            print(f"  └─ {type(exception).__name__}: {exception}")

    def debug(self, message):
        """Log debug message."""
        if self.verbose:
            print(f"[DEBUG] {message}")

    def status(self, text_queue_len, msg_queue_len):
        """Log compact status line."""
        uptime = format_uptime(time.monotonic() - self.start_time)
        free_kb = gc.mem_free() // 1024
        print(f"IO ✓ | text:{text_queue_len:03d} msg:{msg_queue_len:03d} | "
              f"free {free_kb:4d} KiB | up {uptime}")


# ============================================================================
# ICON MANAGER
# ============================================================================

class IconManager:
    """Manages icon lifecycle with proper validation and cleanup."""

    def __init__(self, logger):
        self.logger = logger
        self._icon = None

    def set_from_base64(self, b64_data):
        """
        Decode and validate base64 BMP data.
        Returns True if successful, False otherwise.
        """
        if not isinstance(b64_data, str):
            self.logger.error("Icon data must be string")
            return False

        # Clean and pad base64 string
        b64_data = b64_data.strip()
        padding_needed = (4 - (len(b64_data) % 4)) % 4
        b64_data += "=" * padding_needed

        # Decode
        try:
            raw_data = binascii.a2b_base64(b64_data)
        except binascii.Error as e:
            self.logger.error("Base64 decode failed", e)
            return False

        # Validate BMP header
        if len(raw_data) < 2 or raw_data[:2] != b"BM":
            self.logger.error(f"Invalid BMP header: {raw_data[:2]}")
            return False

        # Replace old icon safely
        self._close_current()
        self._icon = io.BytesIO(raw_data)
        self._icon.seek(0)
        self.logger.debug("Icon loaded successfully")
        return True

    def attach_to_message(self, message):
        """
        Attach current icon to message if valid.
        Returns True if attached, False otherwise.
        """
        if not self._icon:
            return False

        # Check if closed
        try:
            if self._icon.closed:
                return False
        except AttributeError:
            pass

        try:
            self._icon.seek(0)
            # Verify still valid
            if self._icon.read(2) != b"BM":
                self.logger.error("Icon corruption detected")
                self._close_current()
                return False

            self._icon.seek(0)
            message.add_image(self._icon)
            return True
        except Exception as e:
            self.logger.error("Failed to attach icon", e)
            return False

    def clear(self):
        """Clear current icon."""
        self._close_current()

    def _close_current(self):
        """Safely close current icon."""
        if self._icon:
            try:
                self._icon.close()
            except Exception:
                pass
            self._icon = None


# ============================================================================
# WIFI MANAGER
# ============================================================================

class WiFiManager:
    """Handles WiFi connection, reconnection, and health checks."""

    def __init__(self, logger):
        self.logger = logger
        self.pool = socketpool.SocketPool(wifi.radio)
        self.ssl_context = ssl.create_default_context()

    def connect(self):
        """
        Establish WiFi connection (static or DHCP).
        Returns True on success, False on failure.
        """
        ssid = secrets["ssid"].strip()
        password = secrets["password"].strip()

        self.logger.info(f"Connecting to '{ssid}'")
        self.logger.debug(f"MAC: {self._format_mac()}")

        # Configure static IP if provided
        if secrets.get("gateway"):
            self._configure_static_ip()

        # Connect
        try:
            wifi.radio.connect(ssid, password, timeout=Config.WIFI_TIMEOUT)
            self.logger.info("WiFi connected")
        except ConnectionError as e:
            self.logger.error(f"Connection failed: {e}")
            return False

        # Wait for valid IP
        if not self._wait_for_ip():
            return False

        self._log_network_info()
        return True

    def check_connectivity(self, max_attempts=None):
        """
        Verify internet connectivity by pinging adafruit.com.
        Attempts reconnection on failure.
        Returns True if connected, False otherwise.
        """
        if max_attempts is None:
            max_attempts = Config.CONN_CHECK_RETRIES

        for attempt in range(1, max_attempts + 1):
            if self._ping_test():
                return True

            self.logger.error(f"Connectivity check failed (attempt {attempt}/{max_attempts})")

            if attempt < max_attempts:
                self.connect()
                time.sleep(2 ** attempt)  # Exponential backoff

        return False

    def _configure_static_ip(self):
        """Configure static IP addressing."""
        try:
            wifi.radio.set_ipv4_address(
                ipv4=ipaddress.IPv4Address(secrets["static_ip"]),
                netmask=ipaddress.IPv4Address(secrets["netmask"]),
                gateway=ipaddress.IPv4Address(secrets["gateway"])
            )

            # Set DNS
            if "dns" in secrets:
                try:
                    dns_addr = ipaddress.IPv4Address(secrets["dns"])
                    wifi.radio.ipv4_dns = dns_addr
                except (ValueError, AttributeError):
                    try:
                        wifi.radio.ipv4_dns = secrets["dns"]
                    except (KeyError, AttributeError):
                        pass

            self.logger.debug(f"Static IP: {secrets['static_ip']}")
        except Exception as e:
            self.logger.error("Static IP configuration failed", e)

    def _wait_for_ip(self):
        """Wait for non-zero IP address."""
        start = time.monotonic()
        while wifi.radio.ipv4_address.packed == b"\x00\x00\x00\x00":
            if time.monotonic() - start > Config.WIFI_IP_TIMEOUT:
                self.logger.error("Timeout waiting for IP address")
                return False
            time.sleep(0.2)
            feed_watchdog()
        return True

    def _ping_test(self):
        """Simple connectivity test."""
        try:
            session = adafruit_requests.Session(self.pool, self.ssl_context)
            with session.get("https://www.adafruit.com", timeout=5) as response:
                return response.status_code == 200
        except Exception:
            return False

    def _format_mac(self):
        """Format MAC address as colon-separated hex."""
        return ":".join(f"{b:02X}" for b in wifi.radio.mac_address)

    def _log_network_info(self):
        """Log current network configuration."""
        self.logger.info(f"IP: {format_ip(wifi.radio.ipv4_address)}")
        try:
            dns = getattr(wifi.radio, 'ipv4_dns', None)
            if dns and callable(dns):
                dns = dns()
            if dns:
                self.logger.debug(f"DNS: {format_ip(dns)}")
        except Exception:
            pass


# ============================================================================
# ADAFRUIT IO CLIENT
# ============================================================================

class AdafruitIOClient:
    """Handles all Adafruit IO API interactions."""

    def __init__(self, logger, wifi_manager):
        self.logger = logger
        self.wifi_manager = wifi_manager
        self.session = None
        self._recreate_session()

        username = secrets["aio_username"]
        self.headers = {"X-AIO-Key": secrets["aio_key"]}

        # Build URLs
        base = f"https://io.adafruit.com/api/v2/{username}"
        self.group_url = f"{base}/groups/scroller"
        self.text_feed_url = f"{base}/feeds/scroller.text-queue/data"
        self.message_feed_url = f"{base}/feeds/scroller.message-queue/data"

    def fetch_group_settings(self):
        """Fetch scroller group settings. Returns dict or None."""
        status, data = self._request("GET", self.group_url)
        if status == 200 and isinstance(data, dict):
            return data
        self.logger.error(f"Group settings fetch failed: HTTP {status}")
        return None

    def fetch_feed_items(self, feed_url, limit=None):
        """Fetch items from a feed. Returns list."""
        if limit is None:
            limit = Config.FETCH_LIMIT

        status, data = self._request("GET", feed_url)
        if status == 200 and isinstance(data, list):
            return data[:limit]
        self.logger.error(f"Feed fetch failed: HTTP {status}")
        return []

    def delete_item(self, feed_url, item_id):
        """Delete an item from a feed. Returns True on success."""
        status, _ = self._request("DELETE", f"{feed_url}/{item_id}", stream=True)
        if status == 200 or status == 404:
            return True
        if status is not None:
            self.logger.error(f"Delete failed for ID {item_id}: HTTP {status}")
        return False

    def _request(self, method, url, stream=False, max_retries=None):
        """
        Execute HTTP request with automatic retry and session recovery.
        Returns (status_code, data) tuple or (None, None) on failure.
        """
        if max_retries is None:
            max_retries = Config.MAX_RETRIES

        for attempt in range(1, max_retries + 1):
            try:
                feed_watchdog()

                with self.session.request(
                    method,
                    url,
                    headers=self.headers,
                    timeout=Config.HTTP_TIMEOUT
                ) as response:
                    if response.status_code == 200:
                        if stream:
                            return 200, None
                        try:
                            return 200, response.json()
                        except ValueError:
                            return 200, response.text
                    return response.status_code, None

            except OSError as e:
                self.logger.error(f"{method} OSError (attempt {attempt})", e)
                self._recreate_session()

                # Check connectivity on OSError
                if not self.wifi_manager.check_connectivity(max_attempts=1):
                    self.logger.error("Lost connectivity during request")

                time.sleep(2 ** attempt)

            except Exception as e:
                self.logger.error(f"{method} unexpected error", e)
                time.sleep(2 ** attempt)

        return None, None

    def _recreate_session(self):
        """Recreate HTTP session."""
        self.session = adafruit_requests.Session(
            self.wifi_manager.pool,
            self.wifi_manager.ssl_context
        )


# ============================================================================
# MESSAGE PARSER
# ============================================================================

class MessageParser:
    """Validates and parses message payloads."""

    def __init__(self, logger):
        self.logger = logger

    def parse_text(self, raw_text):
        """Parse simple text message. Returns validated text or None."""
        if not isinstance(raw_text, str):
            self.logger.error("Text must be string")
            return None

        text = raw_text.strip()
        if not text:
            self.logger.error("Empty text message")
            return None

        return text

    def parse_structured(self, raw_json):
        """Parse and validate structured message JSON. Returns dict or None."""
        try:
            payload = json.loads(raw_json)
        except (ValueError, TypeError) as e:
            self.logger.error("Invalid JSON", e)
            return None

        if not isinstance(payload, dict):
            self.logger.error("Payload must be dict")
            return None

        elements = payload.get("elements", [])
        if not isinstance(elements, list):
            self.logger.error("Elements must be list")
            return None

        # Validate each element
        for elem in elements:
            if not isinstance(elem, dict):
                self.logger.error("Element must be dict")
                return None
            if "type" not in elem or "data" not in elem:
                self.logger.error("Element missing type/data")
                return None

        return payload

    @staticmethod
    def is_base64_icon(data):
        """
        Heuristically determine if data is base64-encoded icon.
        Base64 data should be reasonably long and contain base64 chars.
        """
        if not isinstance(data, str) or len(data) < 100:
            return False

        # Check for base64 characters (simple heuristic)
        base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        matching = sum(1 for c in data if c in base64_chars)

        # If >80% of chars are base64 chars, likely base64
        return matching / len(data) > 0.8


# ============================================================================
# DISPLAY CONTROLLER
# ============================================================================

class DisplayController:
    """Manages matrix display, animations, and message rendering."""

    def __init__(self, logger, messageboard, fontpool):
        self.logger = logger
        self.messageboard = messageboard
        self.fontpool = fontpool

        # Current display state
        self.current_font = Config.DEFAULT_FONT
        self.current_color = Config.DEFAULT_COLOR
        self.current_background = Config.screen_off_path()
        self.wallpaper = Config.screen_off_path()
        self.current_fx = "left2right"
        self.background_enabled = True

    def show_connecting_splash(self, message):
        """Display connection status message."""
        message.clear()
        message.add_text("Connecting", color=Config.DEFAULT_COLOR)
        self.messageboard.animate(message, "Static", "show")

    def hide_splash(self, message):
        """Hide status message."""
        self.messageboard.animate(message, "Static", "hide")

    def update_background(self, path):
        """Update display background."""
        actual_path = path if self.background_enabled else Config.screen_off_path()
        self.messageboard.set_background(actual_path)

    def render_text_message(self, text, color, icon_manager):
        """Render a simple text message with current settings."""
        msg = self._create_message()

        # Attach icon if available
        icon_manager.attach_to_message(msg)

        # Add text
        msg.add_text(text, color=color)

        # Animate
        self.update_background(self.current_background)
        self._animate_with_fx(msg, self.current_fx)

        # Clean up
        msg = None
        gc.collect()

    def render_structured_message(self, elements, icon_manager):
        """Render a structured message with multiple elements."""
        msg = self._create_message()
        font_changed = False

        # Process elements
        for elem in elements:
            elem_type = elem["type"]
            elem_data = elem["data"]

            if elem_type == "font":
                self.current_font = elem_data
                if not font_changed:
                    # Recreate message with new font
                    msg = Message(
                        self.fontpool.find_font(self.current_font),
                        mask_color=Config.MASK_COLOR
                    )
                    font_changed = True

            elif elem_type == "back":
                self.current_background = Config.image_path(elem_data)

            elif elem_type == "color":
                try:
                    self.current_color = parse_color(elem_data)
                except (ValueError, TypeError) as e:
                    self.logger.error(f"Invalid color: {elem_data}", e)

            elif elem_type == "icon":
                # Determine if base64 or file path
                if MessageParser.is_base64_icon(elem_data):
                    if icon_manager.set_from_base64(elem_data):
                        icon_manager.attach_to_message(msg)
                else:
                    try:
                        msg.add_image(f"images/{elem_data}.bmp")
                    except Exception as e:
                        self.logger.error(f"Failed to load icon: {elem_data}", e)

            elif elem_type == "text":
                msg.add_text(elem_data, color=self.current_color)

            elif elem_type == "fx":
                self.current_fx = elem_data

        # Display
        self.update_background(self.current_background)
        self._animate_with_fx(msg, self.current_fx)
        self.update_background(self.wallpaper)

        # Clean up
        msg = None
        gc.collect()

    def apply_group_settings(self, settings):
        """Apply settings from scroller group feeds."""
        for key, value in settings.items():
            try:
                if key == "scroller.font":
                    self.current_font = value

                elif key == "scroller.background":
                    self.current_background = Config.image_path(value)

                elif key == "scroller.wallpaper":
                    self.wallpaper = Config.image_path(value)
                    self.update_background(self.wallpaper)

                elif key == "scroller.color":
                    self.current_color = parse_color(value)

                elif key == "scroller.background-on":
                    self.background_enabled = value.lower() == "true"

            except Exception as e:
                self.logger.error(f"Failed to apply setting {key}={value}", e)

    def _create_message(self):
        """Create a new message with current font."""
        return Message(
            self.fontpool.find_font(self.current_font),
            mask_color=Config.MASK_COLOR
        )

    def _animate_with_fx(self, message, fx):
        """Execute animation effect sequence."""
        try:
            steps = Config.MULTI_STEP_FX.get(fx, [(fx, 0)])

            for effect_name, delay in steps:
                animation_def = Config.ANIMATIONS.get(effect_name)

                if animation_def is None:
                    continue

                anim_type, anim_name, kwargs = animation_def
                self.messageboard.animate(message, anim_type, anim_name, **kwargs)

                if delay > 0:
                    time.sleep(delay)
                    feed_watchdog()

        except Exception as e:
            self.logger.error(f"Animation error for fx '{fx}'", e)


# ============================================================================
# APPLICATION
# ============================================================================

class Application:
    """Main application coordinator."""

    def __init__(self):
        # Core components
        self.logger = Logger(verbose=True)
        self.wifi_manager = WiFiManager(self.logger)
        self.io_client = AdafruitIOClient(self.logger, self.wifi_manager)
        self.icon_manager = IconManager(self.logger)
        self.parser = MessageParser(self.logger)

        # Display setup
        matrix = Matrix(
            width=Config.WIDTH,
            height=Config.HEIGHT,
            bit_depth=Config.BIT_DEPTH,
            rotation=0
        )
        self.messageboard = MessageBoard(matrix)
        self.fontpool = self._initialize_fonts()
        self.display = DisplayController(self.logger, self.messageboard, self.fontpool)

        # System message for status
        self.system_message = Message(self.fontpool.find_font(Config.DEFAULT_FONT))

        # Message queues
        self.text_queue = deque((), Config.QUEUE_CAPACITY)
        self.message_queue = deque((), Config.QUEUE_CAPACITY)

        # State
        self.system_enabled = True
        self.last_poll_time = 0.0
        self.start_time = time.monotonic()

    def _initialize_fonts(self):
        """Load all fonts into pool."""
        fontpool = FontPool()
        for name, path in Config.FONTS.items():
            try:
                fontpool.add_font(name, path)
                self.logger.debug(f"Loaded font: {name}")
            except Exception as e:
                self.logger.error(f"Failed to load font {name}", e)
        return fontpool

    def initialize(self):
        """Initialize WiFi and connectivity. Returns True on success."""
        self.display.show_connecting_splash(self.system_message)

        if not self.wifi_manager.connect():
            self.logger.error("WiFi initialization failed")
            return False

        if not self.wifi_manager.check_connectivity():
            self.logger.error("Connectivity check failed")
            return False

        self.display.hide_splash(self.system_message)
        self.logger.info("Initialization complete")
        return True

    def run(self):
        """Main event loop."""
        while True:
            loop_start = time.monotonic()
            processed_message = False

            try:
                if self.system_enabled:
                    # Process queues
                    if self._process_text_queue():
                        processed_message = True
                    if self._process_message_queue():
                        processed_message = True

                    # Poll Adafruit IO
                    self._poll_adafruit_io()

                # Log status
                self.logger.status(len(self.text_queue), len(self.message_queue))

            except Exception as e:
                self.logger.error("Loop error", e)

            # Sleep based on activity
            wait_time = Config.BUSY_WAIT if processed_message else Config.IDLE_WAIT
            feed_watchdog()
            time.sleep(wait_time)
            gc.collect()

    def _process_text_queue(self):
        """Process one text message from queue. Returns True if processed."""
        if not self.text_queue:
            return False

        raw_text = self.text_queue.popleft()
        text = self.parser.parse_text(raw_text)

        if text:
            self.display.render_text_message(
                text,
                self.display.current_color,
                self.icon_manager
            )
            return True

        return False

    def _process_message_queue(self):
        """Process one structured message from queue. Returns True if processed."""
        if not self.message_queue:
            return False

        raw_json = self.message_queue.popleft()
        payload = self.parser.parse_structured(raw_json)

        if payload:
            elements = payload.get("elements", [])
            self.display.render_structured_message(elements, self.icon_manager)
            return True

        return False

    def _poll_adafruit_io(self):
        """Poll Adafruit IO for new messages and settings (rate-limited)."""
        now = time.monotonic()
        if now - self.last_poll_time < Config.POLL_PERIOD:
            return

        if not self.wifi_manager.check_connectivity(max_attempts=1):
            self.logger.error("Connectivity lost, skipping poll")
            return

        self.logger.info("Polling Adafruit IO...")

        # Fetch group settings
        group_data = self.io_client.fetch_group_settings()
        if group_data:
            self._apply_group_settings(group_data)

        # Fetch text messages
        self._fetch_feed_items(
            self.io_client.text_feed_url,
            self.text_queue,
            "text"
        )

        # Fetch structured messages
        self._fetch_feed_items(
            self.io_client.message_feed_url,
            self.message_queue,
            "message"
        )

        self.last_poll_time = now
        gc.collect()

    def _apply_group_settings(self, group_data):
        """Extract and apply settings from group data."""
        feeds = group_data.get("feeds", [])
        settings = {}

        for feed in feeds:
            feed_watchdog()
            key = feed.get("key")
            value = feed.get("last_value")

            if key and value is not None:
                settings[key] = value

                # Handle icon separately
                if key == "scroller.icon":
                    self.icon_manager.set_from_base64(value)

                # Handle system enable
                elif key == "scroller.system-on":
                    self.system_enabled = value.lower() == "true"

        self.display.apply_group_settings(settings)

    def _fetch_feed_items(self, feed_url, queue, feed_type):
        """Fetch items from feed, add to queue, and delete from IO."""
        items = self.io_client.fetch_feed_items(feed_url)

        for item in items:
            feed_watchdog()

            item_id = item.get("id")
            item_value = item.get("value")

            if not item_id or not item_value:
                continue

            # Log item (truncate for display)
            try:
                preview = json.loads(item_value).get("name", "Unnamed")
            except Exception:
                preview = str(item_value)[:25]

            created_epoch = item.get("created_epoch", 0)
            timestamp = time.localtime(created_epoch)
            time_str = f"{timestamp.tm_hour:02d}:{timestamp.tm_min:02d}:{timestamp.tm_sec:02d}"

            self.logger.info(f"[{time_str}] +{feed_type} {preview}")

            # Add to queue (FIFO order)
            queue.append(item_value)

            # Delete from IO
            self.io_client.delete_item(feed_url, item_id)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Application entry point."""
    app = Application()

    if not app.initialize():
        print("Initialization failed. Check WiFi credentials and network.")
        while True:
            time.sleep(60)

    app.run()


# Run the application
main()
