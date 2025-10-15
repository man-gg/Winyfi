# UniFi API Integration Suggestions for Winyfi Dashboard

## Overview
Your UniFi API is now ready for integration into `dashboard.py`. The following endpoints provide all necessary data for router cards, bandwidth statistics, and client views:

- **List APs and Bandwidth:** `/api/unifi/devices`
- **List Clients:** `/api/unifi/clients`
- **Total Bandwidth Usage:** `/api/unifi/bandwidth/total`
- **Total Client Count:** `/api/unifi/clients/count`

---

## Integration Suggestions

### 1. Router Cards (APs)
- Fetch data from `/api/unifi/devices`.
- Display each AP's model, name, IP, MAC, download (`xput_down`), and upload (`xput_up`) bandwidth.
- Example:
  ```python
  import requests
  aps = requests.get('http://127.0.0.1:5001/api/unifi/devices').json()
  for ap in aps:
      # Render AP info in dashboard
  ```

### 2. Bandwidth Statistics
- Fetch total bandwidth from `/api/unifi/bandwidth/total`.
- Display overall download and upload usage in the dashboard.
- Example:
  ```python
  stats = requests.get('http://127.0.0.1:5001/api/unifi/bandwidth/total').json()
  total_down = stats['total_down']
  total_up = stats['total_up']
  # Show in dashboard
  ```

### 3. Client List and Count
- Fetch clients from `/api/unifi/clients`.
- Display each client's hostname, MAC, IP, connected AP, download (`rx_bytes`), and upload (`tx_bytes`).
- Fetch total client count from `/api/unifi/clients/count` for summary stats.
- Example:
  ```python
  clients = requests.get('http://127.0.0.1:5001/api/unifi/clients').json()
  count = requests.get('http://127.0.0.1:5001/api/unifi/clients/count').json()['count']
  # Render client info and count
  ```

### 4. Error Handling
- Check for HTTP status codes and handle errors gracefully in the dashboard UI.
- Example:
  ```python
  resp = requests.get(...)
  if resp.status_code == 200:
      data = resp.json()
  else:
      # Show error message
  ```

### 5. Mock Mode for Development
- The API supports mock mode, so you can develop and test without UniFi hardware.
- Toggle mock mode via `/api/unifi/mock` endpoint.

---

## Next Steps
- Integrate these API calls into your dashboard logic and UI.
- Use the provided endpoints for all UniFi-related data needs.
- For frontend/UI help or more code examples, just ask!
