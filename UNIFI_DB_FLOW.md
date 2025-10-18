# UniFi Database Integration - Flow Diagram

## Before (Memory Only)
```
┌─────────────────────────────────────────────────────────┐
│                    Dashboard.py                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────┐              │
│  │ _fetch_unifi_devices()               │              │
│  │  ↓                                   │              │
│  │ Fetch from UniFi API                 │              │
│  │  ↓                                   │              │
│  │ Store in self.unifi_devices (memory) │              │
│  └──────────────────────────────────────┘              │
│                                                         │
│  ┌──────────────────────────────────────┐              │
│  │ reload_routers()                     │              │
│  │  ↓                                   │              │
│  │ Load from database → router_list     │              │
│  │  ↓                                   │              │
│  │ Merge: router_list + unifi_devices   │              │
│  └──────────────────────────────────────┘              │
│                                                         │
└─────────────────────────────────────────────────────────┘

Database: Only regular routers
Memory: UniFi devices (lost on restart)
```

## After (Database Persistent)
```
┌─────────────────────────────────────────────────────────┐
│                    Dashboard.py                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────┐              │
│  │ _fetch_unifi_devices()               │              │
│  │  ↓                                   │              │
│  │ Fetch from UniFi API                 │              │
│  │  ↓                                   │  ┌──────────┐│
│  │ upsert_unifi_router() ───────────────→ │ Database ││
│  │  ↓                                   │  │          ││
│  │ Store in self.unifi_devices (memory) │  │ routers  ││
│  └──────────────────────────────────────┘  │  table   ││
│                                             └──────────┘│
│  ┌──────────────────────────────────────┐              │
│  │ reload_routers()                     │              │
│  │  ↓                                   │              │
│  │ Load ALL from database (includes     │              │
│  │ both regular routers AND UniFi)      │              │
│  │  ↓                                   │              │
│  │ Mark UniFi devices (brand='UniFi')   │              │
│  │  ↓                                   │              │
│  │ Add bandwidth data from API          │              │
│  └──────────────────────────────────────┘              │
│                                                         │
└─────────────────────────────────────────────────────────┘

Database: Regular routers + UniFi devices (persistent)
Memory: Bandwidth/API data only
```

## Data Flow Detail

### Step 1: Fetch UniFi Devices (Every 10 seconds)
```
UniFi Controller
       ↓
   UniFi API (http://localhost:5001)
       ↓
dashboard._fetch_unifi_devices()
       ↓
   For each device:
       ↓
router_utils.upsert_unifi_router()
       ↓
Check if MAC exists in database
       ↓
    ┌──────────┬──────────┐
    │          │          │
  EXISTS    NEW DEVICE
    │          │
  UPDATE    INSERT
    │          │
    └──────────┴──────────┘
           ↓
      Return ID
           ↓
    Store in memory
```

### Step 2: Reload Routers UI
```
dashboard.reload_routers()
       ↓
Call _fetch_unifi_devices()
  (Updates database)
       ↓
Reload from database:
  router_utils.get_routers()
       ↓
Get ALL routers including:
  - Regular routers
  - UniFi devices (brand='UniFi')
       ↓
For each router:
  if brand == 'UniFi':
    - Mark as is_unifi = True
    - Add bandwidth from API
       ↓
Display in UI with:
  - Blue cards for UniFi
  - Red cards for regular
```

## Database Operations

### Insert New UniFi Device
```sql
-- Check if exists
SELECT id FROM routers WHERE mac_address = '00:11:22:33:44:55';

-- If not exists, insert
INSERT INTO routers 
  (name, ip_address, mac_address, brand, location, last_seen, image_path)
VALUES 
  ('Office AP', '192.168.1.105', '00:11:22:33:44:55', 'UniFi', 'UAP-AC-PRO', NOW(), NULL);
```

### Update Existing UniFi Device
```sql
-- If exists, update
UPDATE routers
SET 
  name = 'Office AP',
  ip_address = '192.168.1.105',
  brand = 'UniFi',
  location = 'UAP-AC-PRO',
  last_seen = NOW()
WHERE id = 15;
```

### Retrieve All Routers (Including UniFi)
```sql
SELECT * FROM routers;
-- Returns both regular routers and UniFi devices
```

## Key Improvements

| Aspect              | Before                  | After                    |
|---------------------|-------------------------|--------------------------|
| Storage             | Memory only             | Database (persistent)    |
| Survives restart    | ❌ No                   | ✅ Yes                   |
| Duplicates          | Possible                | ✅ Prevented (MAC)       |
| History/Logs        | ❌ Not tracked          | ✅ Full history          |
| Reports             | ❌ Not included         | ✅ Included              |
| Export to CSV       | ❌ Not included         | ✅ Included              |
| Database ID         | Fake ID                 | ✅ Real auto-increment   |
| Status tracking     | ❌ No                   | ✅ Yes                   |
