# cloudscroll

**Wi-Fi-connected LED matrix message board powered by Adafruit IO**

cloudscroll is a CircuitPython-based scrolling message display for RGB LED matrices. Built for educational use, real-time data display, and programmable signage, it extends MakerMelissa's foundational MessageBoard design with long-run reliability, structured message parsing, dynamic integrations, and user-friendly dashboards.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![CircuitPython](https://img.shields.io/badge/CircuitPython-10.x-blueviolet.svg)
![Platform](https://img.shields.io/badge/platform-MatrixPortal%20S3-orange.svg)

---

## Table of Contents

- [Features](#features)
- [Learning Outcomes](#learning-outcomes)
- [Hardware Requirements](#hardware-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Plain Text Messages](#plain-text-messages)
  - [Structured JSON Messages](#structured-json-messages)
- [Message Format](#message-format)
- [Customization](#customization)
- [Architecture](#architecture)
- [Classroom Applications](#classroom-applications)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Features

- **Dual-Queue Architecture**: Separate queues for plain text and structured JSON messages
- **Dynamic Styling**: Fonts, colors, backgrounds, icons, and animations controlled via Adafruit IO
- **Network Resilience**: Automatic reconnection, watchdog protection, and graceful error handling
- **Rich Animations**: Multi-step effects including scrolls, fades, blinks, and custom sequences
- **External Integrations**: Support for Spotify, weather APIs, IFTTT, and more
- **Scheduled Messages**: Time-based and date-triggered message delivery
- **Drag-and-Drop Dashboard**: User-friendly Adafruit IO interface for non-technical users
- **Educational Focus**: Designed as a teaching tool for IoT, APIs, and embedded systems

---

## Learning Outcomes

- Understand RESTful APIs and IoT messaging patterns via Adafruit IO
- Create and parse JSON message formats for structured display control
- Design resilient embedded systems with watchdogs and memory optimization
- Apply physical computing and aesthetic design principles with LED matrix hardware
- Develop real-time data visualization and signage systems

---

## Hardware Requirements

| Component | Details |
|-----------|---------|
| **Microcontroller** | Adafruit MatrixPortal S3 (Product #5778) |
| **Display** | RGB LED Matrix (64×32, 128×32, or 256×32 supported) |
| **Power Supply** | 5V 4A+ external power supply (USB insufficient) |
| **Capacitor** | 470µF+ electrolytic capacitor for voltage stabilization |
| **Diffusion Panel** | Acrylic panel for improved visibility (optional) |
| **Mounting** | UGLU dashes or 3D-printed bracket |

### Power Considerations

⚠️ **Important**: The MatrixPortal S3 cannot reliably power the matrix via USB alone. An external 5V power supply is required. Large capacitors help manage voltage sag during animation refresh cycles.

📖 See Adafruit's [power guidance](https://learn.adafruit.com/adafruit-matrixportal-s3/usb-power) for details.

---

## Installation

### 1. Prepare Hardware

1. Flash CircuitPython 10.x to your MatrixPortal S3
2. Connect the RGB matrix to the MatrixPortal
3. Attach external 5V power supply with capacitor

### 2. Install Libraries

Download the CircuitPython 10.x library bundle from [circuitpython.org/libraries](https://circuitpython.org/libraries) and copy these to `/lib`:

```
lib/
├── adafruit_matrixportal/
├── adafruit_display_text.mpy
├── adafruit_bitmap_font.mpy
├── adafruit_requests.mpy
└── messageboard/          ← Custom module (included in repo)
```

### 3. Add Fonts and Images

```
fonts/
├── lemon.pcf
├── coolv.pcf
└── ...

images/
└── 128/                   ← Match your matrix width
    ├── spotify.bmp
    ├── ledbg00.bmp
    └── ...
```

### 4. Configure Settings

Create `settings.toml` in the root directory:

```toml
# Wi-Fi Configuration
CIRCUITPY_WIFI_SSID = "YOUR_WIFI_SSID"
CIRCUITPY_WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# Adafruit IO Configuration
aio_username = "your_aio_username"
aio_key = "your_aio_key"

# Optional: Static IP Configuration
# static_ip = "192.168.1.123"
# gateway = "192.168.1.1"
# netmask = "255.255.255.0"
# dns = "8.8.8.8"
```

### 5. Deploy Code

Copy `code.py` to the root of your CIRCUITPY drive. The device will automatically restart and begin running.

---

## Configuration

### Adafruit IO Feeds

CloudScroll uses the following Adafruit IO feeds (all under the `scroller` group):

| Feed | Purpose | Example Value |
|------|---------|---------------|
| `scroller.text-queue` | Plain text messages | "Hello World!" |
| `scroller.message-queue` | Structured JSON messages | `{"name":"spotify", "elements":[...]}` |
| `scroller.font` | Global font name | "lemon" |
| `scroller.background` | Global background image | "ledbgw17" |
| `scroller.wallpaper` | Idle state background | "default_bg" |
| `scroller.color` | Global text color | "#FFFFFF" |
| `scroller.icon` | Global icon (filename or base64) | "spotify" |
| `scroller.system-on` | Enable/disable display | "true" |
| `scroller.background-on` | Show/hide backgrounds | "true" |

### Code Constants

Edit these in `code.py` to customize behavior:

```python
WIDTH = 128              # Display width in pixels
HEIGHT = 32              # Display height in pixels
POLL_PERIOD = 30         # Seconds between Adafruit IO polls
FETCH_LIMIT = 5          # Max items fetched per poll
BUSY_WAIT = 2            # Delay after message (seconds)
IDLE_WAIT = 10           # Delay when idle (seconds)
```

---

## Usage

### Plain Text Messages

Send simple text messages to `scroller.text-queue` via the Adafruit IO dashboard or API:

```
Welcome to CloudScroll!
```

Text messages use global styling (font, color, background, icon) from the scroller feed group.

### Structured JSON Messages

Send rich, formatted messages to `scroller.message-queue`:

```json
{
  "name": "birthday",
  "elements": [
    { "type": "font", "data": "lemon" },
    { "type": "back", "data": "birthday_bg" },
    { "type": "icon", "data": "cake" },
    { "type": "color", "data": "#FF69B4" },
    { "type": "text", "data": "Happy Birthday Sarah!" },
    { "type": "fx", "data": "fade" }
  ]
}
```

---

## Message Format

### JSON Structure

Structured messages use a `name` field for categorization and an `elements` array for display instructions:

```json
{
  "name": "unique-label-or-category",
  "elements": [
    { "type": "font",  "data": "<font name>" },
    { "type": "back",  "data": "<background filename>" },
    { "type": "icon",  "data": "<icon filename or base64>" },
    { "type": "color", "data": "<hex color code>" },
    { "type": "text",  "data": "<message content>" },
    { "type": "fx",    "data": "<animation effect>" }
  ]
}
```

### Element Types

| Type | Description | Example |
|------|-------------|---------|
| `font` | PCF font name (no extension) | `"lemon"` |
| `back` | Background BMP filename (no extension) | `"ledbgw17"` |
| `icon` | Icon BMP filename or base64-encoded BMP | `"spotify"` |
| `color` | Text color in hex format | `"#FFFFFF"` |
| `text` | Message content | `"Now Playing: Song Title"` |
| `fx` | Animation effect | `"fade"`, `"left2right"`, `"none"` |

### Available Animations

**Single Effects:**
- `in_right`, `in_left`, `in_top`, `in_bottom`
- `out_right`, `out_left`, `out_top`, `out_bottom`
- `flash`, `blink`, `fade`, `none`

**Multi-Step Effects:**
- `left2right`, `right2left`, `left2left`, `right2right`
- `top2top`, `bottom2bottom`, `top2bottom`, `bottom2top`

### Example: Spotify Integration

```json
{
  "name": "spotify",
  "elements": [
    { "type": "font", "data": "lemon" },
    { "type": "back", "data": "ledbgw17" },
    { "type": "icon", "data": "spotify" },
    { "type": "color", "data": "#1DB954" },
    { "type": "text", "data": "♫ Call Me The Breeze - Lynyrd Skynyrd" },
    { "type": "fx", "data": "left2right" }
  ]
}
```

---

## Customization

### Custom Fonts

CloudScroll uses PCF bitmap fonts. To create custom fonts:

1. **Choose a TTF font** from Google Fonts or DaFont
2. **Convert TTF to BDF** using [ttf2bdf](https://sbiswas.tripod.com/ttf2bdf/)
3. **Convert BDF to PCF** using [Adafruit's web tool](https://adafruit.github.io/web-bdftopcf/)
4. Copy the `.pcf` file to `/fonts` on your device
5. Reference by filename (without extension) in messages

### Custom Images

Images must be BMP format with dimensions matching your matrix:

- **Icons**: Small graphics (e.g., 16×16, 32×32)
- **Backgrounds**: Full-width images matching matrix dimensions
- **Color depth**: 24-bit BMP recommended

Place images in `/images/{WIDTH}/` where `{WIDTH}` matches your matrix (e.g., `/images/128/`).

### 3D-Printed Mount

For professional wall mounting, use the [matrixportal wall mount](https://www.printables.com/model/44541-adafruit-rgb-matrix-portal-wall-mount/) by [smtibor](https://www.printables.com/@smtibor_96853)

- Print with PLA at 0.2mm layer height
- Secure to wall with screws or adhesive
- Mount MatrixPortal ensuring port accessibility

---

## Architecture

### Design Principles

CloudScroll is built on several key architectural decisions:

#### 1. Dual-Queue Message System

Two independent message queues serve different use cases:

- **Text Queue** (`scroller.text-queue`): Simple messages with global styling—ideal for dashboards, IFTTT, SMS integrations
- **Message Queue** (`scroller.message-queue`): Fully styled JSON payloads for advanced integrations and per-message customization

This separation maintains simplicity for basic use while enabling powerful control for complex applications.

#### 2. Configuration as a Service

Rather than hardcoding appearance, CloudScroll responds to remote configuration via Adafruit IO:

- Live updates to fonts, colors, backgrounds, and icons
- Dashboard-driven or automated reconfiguration (e.g., seasonal themes)
- Transparency for students inspecting data-driven systems

#### 3. Network Resilience

Designed for 24/7 operation in educational and public settings:

- **Session reuse**: Single persistent HTTP session reduces socket overhead
- **Safe request wrapper**: Auto-retry with exponential backoff, timeout handling, session rebuilding
- **Watchdog integration**: `microcontroller.watchdog.feed()` prevents hangs
- **IP configuration hold**: Waits for valid IP before proceeding (handles captive portals)
- **Connection splash**: Visual feedback during connectivity issues
- **DNS fallback**: Graceful handling of name resolution failures

#### 4. Hardware Abstraction

High-level abstractions (`FontPool`, `MessageBoard`, `IconManager`) encapsulate:

- Font management and caching
- Background switching and image handling
- Animation orchestration and effect composition

This simplifies the main event loop and makes the codebase educational and extensible.

### Event Loop Flow

```
┌─────────────────────────┐
│   WiFi Connect/Check    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Poll Adafruit IO Feeds │
│  (text, message, config)│
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Process Text Queue    │
│   (if non-empty)        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Process Message Queue  │
│   (if non-empty)        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Apply Animations & FX  │
│  Render to Display      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Feed Watchdog          │
│  Garbage Collection     │
│  Sleep (busy/idle)      │
└───────────┬─────────────┘
            │
            └──────────────► (loop)
```

### File Structure

```
CloudScroll/
├── code.py                 # Main application
├── settings.toml           # WiFi and API credentials
├── LICENSE                 # MIT license
├── README.md              # This file
├── lib/
│   ├── adafruit_matrixportal/
│   ├── adafruit_display_text.mpy
│   ├── adafruit_requests.mpy
│   └── messageboard/       # Custom module
│       ├── __init__.py
│       ├── fontpool.py
│       └── message.py
├── fonts/
│   ├── lemon.pcf
│   ├── coolv.pcf
│   └── ...
└── images/
    └── 128/                # Width-specific directory
        ├── spotify.bmp
        ├── ledbg00.bmp
        └── ...
```

---

## Classroom Applications

CloudScroll has been successfully deployed in educational settings for:

### Use Cases

- **Daily announcements**: Morning messages, schedule changes, lunch menus
- **Birthday celebrations**: Automated birthday shoutouts with custom backgrounds
- **Now playing**: Real-time Spotify integration showing currently playing music
- **Weather updates**: Live weather data from external APIs
- **Student projects**: Hands-on learning for API integration, JSON parsing, and IoT
- **Digital rituals**: Scheduled messages creating community touchpoints

### Educational Value

Students gain experience with:

- JSON structure and parsing
- RESTful API interaction
- IoT message queuing systems
- Embedded systems programming
- Visual design and UX principles
- Network protocols and resilience

### Classroom Reflections

- Students authored and debugged structured JSON messages
- BMP uploads via dashboard enhanced engagement and ownership
- Scheduled messages created meaningful "digital rituals"
- System withstood long runtimes and intermittent connectivity without crashes

---

## Contributing

Contributions are welcome! Areas for improvement:

- Additional animation effects
- Support for GIF animations
- MQTT integration
- Web-based configuration interface
- Additional example integrations (Slack, Discord, Home Assistant)

Please submit pull requests or open issues on GitHub.

---

## License

CloudScroll is licensed under the MIT License.

```
Copyright (c) 2020 Melissa LeBlanc-Williams (MakerMelissa)
Copyright (c) 2024-2025 William Chesher
```

See the [LICENSE](LICENSE) file for full details.

### SPDX

```
SPDX-License-Identifier: MIT
```

---

## Acknowledgments

CloudScroll is based on:

- **[MatrixPortal MessageBoard](https://learn.adafruit.com/matrixportal-circuitpython-animated-message-board)** by Melissa LeBlanc-Williams (MakerMelissa)
- Contributions from John Park and M. LeBlanc-Williams via Adafruit
- CloudScroll extensions by William Chesher (2024–2025)

### Resources

- **Font Design**: [Pixel Art Matrix Display Guide](https://learn.adafruit.com/pixel-art-matrix-display)
- **Custom Fonts**: [Custom Fonts for PyPortal](https://learn.adafruit.com/custom-fonts-for-pyportal-circuitpython-display)
- **Power Guidance**: [MatrixPortal S3 USB Power](https://learn.adafruit.com/adafruit-matrixportal-s3/usb-power)
- **CircuitPython**: [circuitpython.org](https://circuitpython.org/)
- **Adafruit IO**: [io.adafruit.com](https://io.adafruit.com/)

---

**Built with ❤️ for makers, educators, and learners**
