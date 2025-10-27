"""
Loop Detection Configuration Template

Copy this file to loop_detection_config.py and customize for your environment.
"""

import json
import os

# =============================================================================
# NETWORK CONFIGURATION
# =============================================================================

# Network interfaces to monitor (leave empty for auto-detect)
# Examples:
#   Windows: ["Wi-Fi", "Ethernet", "Local Area Connection"]
#   Linux: ["eth0", "wlan0", "ens33"]
#   macOS: ["en0", "en1"]
NETWORK_INTERFACES = []  # Empty = auto-detect

# Default interface (if multiple available)
DEFAULT_INTERFACE = None  # None = auto-detect

# =============================================================================
# DETECTION PARAMETERS
# =============================================================================

# Detection mode: "advanced", "lightweight", or "auto"
# - "advanced": Full analysis, best accuracy, higher CPU usage
# - "lightweight": Fast analysis, good accuracy, low CPU usage
# - "auto": Automatic mode based on traffic
DETECTION_MODE = "lightweight"

# Capture timeout in seconds
# Recommended: 3-5 for lightweight, 10-15 for advanced
CAPTURE_TIMEOUT = 5

# Severity threshold (packets/sec that triggers alert)
# Recommended: 30-50 for sensitive networks, 80-120 for normal networks
SEVERITY_THRESHOLD = 50

# Enable intelligent packet sampling (reduces CPU usage)
# Only applies to lightweight mode
ENABLE_SAMPLING = True

# =============================================================================
# MONITORING CONFIGURATION
# =============================================================================

# Enable continuous background monitoring
ENABLE_BACKGROUND_MONITORING = True

# Check interval in seconds (how often to run detection)
# Recommended: 300 (5 min) for production, 60 (1 min) for testing
CHECK_INTERVAL = 300

# Enable multi-interface monitoring
# If True and multiple interfaces specified, monitors all simultaneously
ENABLE_MULTI_INTERFACE = True

# =============================================================================
# FALSE POSITIVE REDUCTION
# =============================================================================

# Enable automatic whitelist learning
AUTO_WHITELIST = True

# Manual whitelist - MAC addresses of known legitimate devices
# Format: {"device_name": "MAC_address"}
WHITELIST_ROUTERS = {
    # Example: "Main Router": "aa:bb:cc:dd:ee:11"
}

WHITELIST_DHCP_SERVERS = {
    # Example: "DHCP Server": "aa:bb:cc:dd:ee:22"
}

WHITELIST_MDNS_DEVICES = {
    # Example: "Apple TV": "aa:bb:cc:dd:ee:33"
}

# Path to persistent whitelist file (JSON)
WHITELIST_FILE = "loop_detection_whitelist.json"

# =============================================================================
# DATABASE INTEGRATION
# =============================================================================

# Save detection results to database
SAVE_TO_DATABASE = True

# API base URL for database endpoint
API_BASE_URL = "http://localhost:5000"

# API timeout in seconds
API_TIMEOUT = 5

# Retry failed database saves
API_RETRY_ENABLED = True
API_MAX_RETRIES = 3

# =============================================================================
# ALERTING CONFIGURATION
# =============================================================================

# Enable alerts for detected loops
ENABLE_ALERTS = True

# Alert severity levels and their thresholds
ALERT_LEVELS = {
    "info": 30,      # Informational
    "warning": 50,   # Warning - investigate
    "critical": 100  # Critical - immediate action
}

# Alert methods to enable
ALERT_EMAIL = False
ALERT_SMS = False
ALERT_WEBHOOK = True
ALERT_LOG = True

# Email configuration (if ALERT_EMAIL = True)
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_FROM = "network-monitor@company.com"
EMAIL_TO = ["admin@company.com"]
EMAIL_USERNAME = ""
EMAIL_PASSWORD = ""  # Use environment variable in production!

# Webhook configuration (if ALERT_WEBHOOK = True)
WEBHOOK_URL = "http://localhost:5000/api/alerts"
WEBHOOK_METHOD = "POST"

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Enable logging
ENABLE_LOGGING = True

# Log level: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
LOG_LEVEL = "INFO"

# Log file path (None for console only)
LOG_FILE = "loop_detection.log"

# Log rotation
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# PERFORMANCE TUNING
# =============================================================================

# Maximum packets to capture per session (prevents memory overflow)
MAX_PACKETS_PER_SESSION = 10000

# Memory limit for packet storage (MB)
MEMORY_LIMIT_MB = 200

# Enable duplicate packet detection
ENABLE_DUPLICATE_DETECTION = True

# Enable early exit on detected storms
ENABLE_EARLY_EXIT = True

# Number of worker threads for multi-interface monitoring
MAX_WORKER_THREADS = 4

# =============================================================================
# ADVANCED FEATURES
# =============================================================================

# Enable cross-subnet detection
ENABLE_CROSS_SUBNET_DETECTION = True

# Penalty multiplier for cross-subnet traffic
CROSS_SUBNET_PENALTY = 2.0

# Enable STP/LLDP/CDP monitoring
ENABLE_DISCOVERY_PROTOCOL_MONITORING = True

# Enable ICMP redirect detection (routing loop detection)
ENABLE_ICMP_REDIRECT_DETECTION = True

# Track IP address changes
ENABLE_IP_CHANGE_TRACKING = True

# Maximum IP changes per device per hour before flagging
MAX_IP_CHANGES_PER_HOUR = 10

# =============================================================================
# REPORTING
# =============================================================================

# Generate periodic reports
ENABLE_PERIODIC_REPORTS = True

# Report interval in seconds (86400 = 24 hours)
REPORT_INTERVAL = 86400

# Report output directory
REPORT_OUTPUT_DIR = "loop_detection_reports"

# Report format: "json", "html", "pdf", "all"
REPORT_FORMAT = "json"

# Include historical data in reports
REPORT_INCLUDE_HISTORY = True

# History retention period in days
HISTORY_RETENTION_DAYS = 30

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_whitelist():
    """Load whitelist from file."""
    if os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE, 'r') as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"Error loading whitelist: {e}")
    return {"routers": [], "dhcp_servers": [], "mdns_devices": []}


def save_whitelist(whitelist_data):
    """Save whitelist to file."""
    try:
        with open(WHITELIST_FILE, 'w') as f:
            json.dump(whitelist_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving whitelist: {e}")
        return False


def get_config_summary():
    """Get a summary of current configuration."""
    return {
        "detection_mode": DETECTION_MODE,
        "capture_timeout": CAPTURE_TIMEOUT,
        "severity_threshold": SEVERITY_THRESHOLD,
        "monitoring_enabled": ENABLE_BACKGROUND_MONITORING,
        "check_interval": CHECK_INTERVAL,
        "multi_interface": ENABLE_MULTI_INTERFACE,
        "interfaces": NETWORK_INTERFACES or ["auto-detect"],
        "database_enabled": SAVE_TO_DATABASE,
        "alerts_enabled": ENABLE_ALERTS,
        "logging_enabled": ENABLE_LOGGING,
        "cross_subnet_detection": ENABLE_CROSS_SUBNET_DETECTION
    }


def validate_config():
    """Validate configuration settings."""
    errors = []
    warnings = []
    
    # Check detection mode
    if DETECTION_MODE not in ["advanced", "lightweight", "auto"]:
        errors.append(f"Invalid DETECTION_MODE: {DETECTION_MODE}")
    
    # Check timeout
    if CAPTURE_TIMEOUT < 1 or CAPTURE_TIMEOUT > 60:
        warnings.append(f"CAPTURE_TIMEOUT of {CAPTURE_TIMEOUT}s is unusual (recommended: 3-15s)")
    
    # Check threshold
    if SEVERITY_THRESHOLD < 10:
        warnings.append(f"Low SEVERITY_THRESHOLD ({SEVERITY_THRESHOLD}) may cause many false positives")
    
    # Check interval
    if ENABLE_BACKGROUND_MONITORING and CHECK_INTERVAL < 30:
        warnings.append(f"Short CHECK_INTERVAL ({CHECK_INTERVAL}s) may cause high CPU usage")
    
    # Check database config
    if SAVE_TO_DATABASE and not API_BASE_URL:
        errors.append("SAVE_TO_DATABASE enabled but API_BASE_URL not set")
    
    # Check email config
    if ALERT_EMAIL and (not EMAIL_FROM or not EMAIL_TO):
        errors.append("ALERT_EMAIL enabled but email addresses not configured")
    
    # Check webhook config
    if ALERT_WEBHOOK and not WEBHOOK_URL:
        errors.append("ALERT_WEBHOOK enabled but WEBHOOK_URL not set")
    
    return errors, warnings


# =============================================================================
# CONFIGURATION PRESETS
# =============================================================================

PRESETS = {
    "development": {
        "DETECTION_MODE": "lightweight",
        "CAPTURE_TIMEOUT": 3,
        "SEVERITY_THRESHOLD": 30,
        "CHECK_INTERVAL": 60,
        "ENABLE_ALERTS": False,
        "SAVE_TO_DATABASE": False,
        "LOG_LEVEL": "DEBUG"
    },
    
    "production_small": {
        "DETECTION_MODE": "lightweight",
        "CAPTURE_TIMEOUT": 5,
        "SEVERITY_THRESHOLD": 50,
        "CHECK_INTERVAL": 300,
        "ENABLE_ALERTS": True,
        "SAVE_TO_DATABASE": True,
        "LOG_LEVEL": "INFO"
    },
    
    "production_large": {
        "DETECTION_MODE": "advanced",
        "CAPTURE_TIMEOUT": 10,
        "SEVERITY_THRESHOLD": 80,
        "CHECK_INTERVAL": 600,
        "ENABLE_ALERTS": True,
        "SAVE_TO_DATABASE": True,
        "LOG_LEVEL": "INFO",
        "ENABLE_MULTI_INTERFACE": True
    },
    
    "troubleshooting": {
        "DETECTION_MODE": "advanced",
        "CAPTURE_TIMEOUT": 15,
        "SEVERITY_THRESHOLD": 40,
        "CHECK_INTERVAL": 120,
        "ENABLE_ALERTS": True,
        "SAVE_TO_DATABASE": True,
        "LOG_LEVEL": "DEBUG",
        "ENABLE_CROSS_SUBNET_DETECTION": True
    }
}


def apply_preset(preset_name):
    """Apply a configuration preset."""
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESETS.keys())}")
    
    preset = PRESETS[preset_name]
    globals().update(preset)
    
    print(f"Applied preset: {preset_name}")
    for key, value in preset.items():
        print(f"  {key} = {value}")


# =============================================================================
# INITIALIZATION
# =============================================================================

def initialize():
    """Initialize configuration."""
    import logging
    from logging.handlers import RotatingFileHandler
    
    # Setup logging
    if ENABLE_LOGGING:
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, LOG_LEVEL))
        
        formatter = logging.Formatter(LOG_FORMAT)
        
        if LOG_FILE:
            handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Validate configuration
    errors, warnings = validate_config()
    
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        raise ValueError("Invalid configuration")
    
    if warnings:
        print("⚠️ Configuration warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    # Create directories
    if ENABLE_PERIODIC_REPORTS:
        os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
    
    # Load whitelist
    whitelist = load_whitelist()
    
    # Merge with manual whitelist
    for name, mac in WHITELIST_ROUTERS.items():
        if mac not in whitelist.get("routers", []):
            whitelist.setdefault("routers", []).append(mac)
    
    for name, mac in WHITELIST_DHCP_SERVERS.items():
        if mac not in whitelist.get("dhcp_servers", []):
            whitelist.setdefault("dhcp_servers", []).append(mac)
    
    for name, mac in WHITELIST_MDNS_DEVICES.items():
        if mac not in whitelist.get("mdns_devices", []):
            whitelist.setdefault("mdns_devices", []).append(mac)
    
    # Save merged whitelist
    save_whitelist(whitelist)
    
    print("✅ Configuration initialized successfully")
    print(f"\nConfiguration Summary:")
    summary = get_config_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    return whitelist


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    print("Loop Detection Configuration")
    print("=" * 80)
    
    # Option 1: Use default configuration
    print("\n1. Using default configuration:")
    whitelist = initialize()
    
    # Option 2: Apply a preset
    # print("\n2. Applying preset:")
    # apply_preset("production_small")
    # whitelist = initialize()
    
    # Option 3: Custom configuration
    # print("\n3. Custom configuration:")
    # DETECTION_MODE = "advanced"
    # CAPTURE_TIMEOUT = 10
    # ENABLE_ALERTS = True
    # whitelist = initialize()
