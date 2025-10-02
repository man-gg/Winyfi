# Network Monitoring System

A comprehensive network monitoring and management system built with Python. This system provides real-time monitoring of network devices, bandwidth tracking, and network health analysis.

## Features

- **Real-time Network Monitoring**
  - Device discovery and tracking
  - Bandwidth monitoring and logging
  - Latency measurement and quality assessment
  - Network loop detection
  - ARP and broadcast traffic analysis

- **Network Health Analysis**
  - Speed testing (full and mini tests)
  - Latency quality ratings
  - Network anomaly detection
  - Throughput measurement

- **Device Management**
  - Client device tracking
  - MAC address monitoring
  - IP address mapping
  - Hostname resolution
  - Vendor identification

- **User Interface**
  - Modern dashboard built with ttkbootstrap
  - Real-time network statistics
  - Visual network mapping
  - Performance graphs and metrics

## Prerequisites

- Python 3.13+
- MySQL Database
- Required Python packages (install via pip):
  - mysql-connector-python
  - speedtest-cli
  - scapy
  - psutil
  - pillow
  - ttkbootstrap

## Installation

1. Clone the repository:
   ```bash
   git clone [repository-url]
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # On Windows
   .venv\Scripts\activate
   # On Unix or MacOS
   source .venv/bin/activate
   ```

3. Install required packages:
   ```bash
   pip install mysql-connector-python speedtest-cli scapy psutil pillow ttkbootstrap
   ```

4. Configure the database:
   - Create a MySQL database
   - Update the connection settings in `db.py`

## Usage

1. Start the main application:
   ```bash
   python main.py
   ```

2. Log in using your credentials through the login interface

3. Use the dashboard to:
   - Monitor network devices
   - Track bandwidth usage
   - View network statistics
   - Generate reports
   - Manage network tickets

## Project Structure

- `main.py` - Application entry point
- `dashboard.py` - Main UI and dashboard implementation
- `network_utils.py` - Core network monitoring functions
- `bandwidth_logger.py` - Bandwidth tracking and logging
- `router_utils.py` - Router management utilities
- `user_utils.py` - User management functions
- `ticket_utils.py` - Network ticket system
- `report_utils.py` - Reporting functionality
- `print_utils.py` - Printing utilities
- `db.py` - Database configuration and operations

## Security Features

- User authentication system
- Secure password handling
- Role-based access control
- Session management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here]

## Support

For support, please [add contact information or support instructions]
