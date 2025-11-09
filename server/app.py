 
from flask import Flask, request, jsonify
from flask_cors import CORS

# Reuse existing utilities from project root
import sys, os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from user_utils import verify_user
from ticket_utils import fetch_srfs, create_srf
from router_utils import get_routers, is_router_online_by_status
from db import get_connection, log_user_login, create_login_sessions_table, get_user_last_login_info, get_user_login_history, update_user_profile, change_user_password, log_activity, create_activity_logs_table
from report_utils import get_uptime_percentage, get_bandwidth_usage

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Initialize database tables
    create_login_sessions_table()
    create_activity_logs_table()

    def _extract_client_ip(req, data=None):
        """Best-effort client IP extraction supporting proxies and client-provided IP.
        Priority: X-Forwarded-For → X-Real-IP → remote_addr → data['device_ip'] (if local).
        """
        try:
            xff = (req.headers.get("X-Forwarded-For") or "").strip()
            if xff:
                ip = xff.split(",")[0].strip()
            else:
                ip = (req.headers.get("X-Real-IP") or req.remote_addr or "").strip()
            # If running locally, prefer provided device_ip when available
            if ip in ("127.0.0.1", "::1", "") and data and isinstance(data, dict):
                ip_override = (data.get("device_ip") or data.get("client_ip") or "").strip()
                if ip_override:
                    ip = ip_override
            return ip or "127.0.0.1"
        except Exception:
            return req.remote_addr or "127.0.0.1"

    @app.get("/api/health")
    def health():
        return {"status": "ok"}


    @app.post("/api/login")
    def login():
        data = request.get_json(force=True, silent=True) or {}
        username = data.get("username", "")
        password = data.get("password", "")
        user = verify_user(username, password)
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Get device information from request
        device_ip = _extract_client_ip(request, data)
        device_mac = data.get("device_mac")
        device_hostname = data.get("device_hostname")
        device_platform = data.get("device_platform")
        user_agent = request.headers.get("User-Agent", "")
        
        # Log the login session
        login_type = 'admin' if user.get('role') == 'admin' else 'client'
        log_user_login(
            user_id=user['id'],
            username=user['username'],
            device_ip=device_ip,
            device_mac=device_mac,
            device_hostname=device_hostname,
            device_platform=device_platform,
            user_agent=user_agent,
            login_type=login_type
        )
        
        # Log activity for client login
        if login_type == 'client':
            try:
                log_activity(
                    user_id=user['id'],
                    action='Login',
                    target='Client Portal',
                    ip_address=device_ip
                )
            except Exception:
                pass
        
        # minimal sessionless response (tokenization can be added later)
        return jsonify({
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
        })

    @app.post("/api/logout")
    def logout():
        """Log user logout activity"""
        try:
            data = request.get_json(force=True, silent=True) or {}
            user_id = data.get("user_id")
            
            if user_id:
                device_ip = _extract_client_ip(request, data)
                log_activity(
                    user_id=user_id,
                    action='Logout',
                    target='Client Portal',
                    ip_address=device_ip
                )
            
            return jsonify({"success": True})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    # User profile routes
    @app.route("/api/user/<int:user_id>/edit-profile", methods=["PUT"])
    def edit_user_profile(user_id):
        try:
            payload = request.get_json(force=True, silent=True) or {}
            ok, result = update_user_profile(user_id, payload)
            if not ok:
                return jsonify({"error": result}), 400
            
            # Log activity
            try:
                device_ip = _extract_client_ip(request, payload)
                log_activity(
                    user_id=user_id,
                    action='Edit Profile',
                    target='User Profile',
                    ip_address=device_ip
                )
            except Exception:
                pass
            
            return jsonify({"success": True, "user": result})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/user/<int:user_id>/change-password")
    def change_user_password_api(user_id):
        try:
            data = request.get_json(force=True, silent=True) or {}
            old_password = (data.get("old_password") or "").strip()
            new_password = (data.get("new_password") or "").strip()
            if not old_password or not new_password:
                return jsonify({"error": "Missing password fields"}), 400
            success, message = change_user_password(user_id, old_password, new_password)
            if not success:
                status = 403 if "incorrect" in message.lower() else 400
                return jsonify({"error": message}), status
            
            # Log activity
            try:
                device_ip = _extract_client_ip(request, data)
                log_activity(
                    user_id=user_id,
                    action='Change Password',
                    target='User Account',
                    ip_address=device_ip
                )
            except Exception:
                pass
            
            return jsonify({"success": True, "message": message})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/srfs")
    def list_srfs():
        try:
            data = fetch_srfs()
            return jsonify(data)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/srfs")
    def create_srfs():
        try:
            payload = request.get_json(force=True)
            created_by = int(payload.get("created_by"))
            srf_data = payload.get("data", {})
            create_srf(srf_data, created_by)
            
            # Log activity for SRF creation
            try:
                device_ip = _extract_client_ip(request, payload)
                ticket_type = srf_data.get('request_type', 'Unknown')
                log_activity(
                    user_id=created_by,
                    action='Create Ticket',
                    target=f"SRF - {ticket_type}",
                    ip_address=device_ip
                )
            except Exception:
                pass
            
            return jsonify({"ok": True}), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/log-activity")
    def log_activity_endpoint():
        """General endpoint for logging client activities"""
        try:
            data = request.get_json(force=True, silent=True) or {}
            user_id = data.get("user_id")
            action = data.get("action")
            target = data.get("target")
            
            if user_id and action:
                device_ip = _extract_client_ip(request, data)
                log_activity(
                    user_id=user_id,
                    action=action,
                    target=target,
                    ip_address=device_ip
                )
                return jsonify({"success": True})
            else:
                return jsonify({"error": "Missing user_id or action"}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    # Placeholders - to be wired to existing router utils later
    @app.get("/api/routers")
    def routers_list():
        try:
            return jsonify(get_routers())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/routers/with-bandwidth")
    def routers_with_bandwidth():
        """Get all routers with their latest bandwidth data from database"""
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Query to get routers with their latest bandwidth data
            query = """
                SELECT 
                    r.*,
                    bl.download_mbps,
                    bl.upload_mbps,
                    bl.latency_ms,
                    bl.timestamp as bandwidth_timestamp
                FROM routers r
                LEFT JOIN (
                    SELECT 
                        router_id,
                        download_mbps,
                        upload_mbps,
                        latency_ms,
                        timestamp,
                        ROW_NUMBER() OVER (PARTITION BY router_id ORDER BY timestamp DESC) as rn
                    FROM bandwidth_logs
                ) bl ON r.id = bl.router_id AND bl.rn = 1
                ORDER BY r.id
            """
            
            cursor.execute(query)
            routers = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return jsonify(routers)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/routers/<int:router_id>/status")
    def router_status(router_id):
        try:
            from router_utils import get_router_status_info
            status_info = get_router_status_info(router_id, timeout_seconds=5)
            return jsonify(status_info)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/dashboard/stats")
    def dashboard_stats():
        try:
            routers = get_routers()
            total = len(routers)
            # Use status-based online detection with 5-second timeout
            online = 0
            for r in routers:
                if is_router_online_by_status(r['id'], timeout_seconds=5):
                    online += 1
            offline = max(0, total - online)
            return jsonify({"total": total, "online": online, "offline": offline})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    # ==================== CLIENT DISCOVERY ENDPOINTS ====================
    
    @app.post("/api/clients/scan")
    def scan_network_clients():
        """
        Trigger a network-wide client discovery scan across all AP subnets.
        Returns discovered clients with router associations.
        """
        try:
            from network_utils import discover_clients
            from db import save_network_client, create_network_clients_table, create_connection_history_table
            
            # Ensure tables exist
            create_network_clients_table()
            create_connection_history_table()
            
            # Get scan parameters from request
            data = request.get_json(silent=True) or {}
            timeout = int(data.get("timeout", 2))
            use_db_routers = data.get("use_db_routers", True)
            
            # Run discovery
            clients = discover_clients(
                timeout=timeout,
                use_db_routers=use_db_routers,
                scan_all_subnets=False
            )
            
            # Save all discovered clients to database
            saved_count = 0
            for mac, info in clients.items():
                try:
                    save_network_client(
                        mac_address=mac,
                        ip_address=info.get("ip"),
                        hostname=info.get("hostname", "Unknown"),
                        vendor=info.get("vendor", "Unknown"),
                        ping_latency=None  # Can be measured separately if needed
                    )
                    saved_count += 1
                except Exception as e:
                    print(f"Error saving client {mac}: {e}")
            
            # Convert clients dict to list format for API response
            client_list = []
            for mac, info in clients.items():
                client_list.append({
                    "mac_address": mac,
                    "ip_address": info.get("ip"),
                    "hostname": info.get("hostname", "Unknown"),
                    "vendor": info.get("vendor", "Unknown"),
                    "subnet": info.get("subnet"),
                    "interface": info.get("interface"),
                    "router_id": info.get("router_id"),
                    "router_name": info.get("router_name"),
                    "last_seen": info.get("last_seen").isoformat() if info.get("last_seen") else None
                })
            
            return jsonify({
                "success": True,
                "total_discovered": len(clients),
                "saved_to_db": saved_count,
                "clients": client_list
            })
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/clients")
    def get_all_clients():
        """
        Get all network clients from database.
        Query params: online_only (bool), limit (int)
        """
        try:
            from db import get_network_clients, create_network_clients_table
            
            create_network_clients_table()
            
            online_only = request.args.get("online_only", "false").lower() == "true"
            limit = int(request.args.get("limit", 1000))
            router_id = request.args.get("router_id")
            if router_id is not None:
                try:
                    router_id = int(router_id)
                except Exception:
                    router_id = None
            
            clients = get_network_clients(online_only=online_only, limit=limit, router_id=router_id)
            
            # Convert datetime objects to ISO format strings
            for client in clients:
                for key in ['first_seen', 'last_seen', 'created_at', 'updated_at']:
                    if key in client and client[key]:
                        if hasattr(client[key], 'isoformat'):
                            client[key] = client[key].isoformat()
            
            return jsonify({
                "success": True,
                "total": len(clients),
                "clients": clients
            })
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/routers/<int:router_id>/clients")
    def get_router_clients(router_id):
        """
        Get clients associated with a specific router/AP.
        Uses network discovery filtered by router_id.
        """
        try:
            from network_utils import discover_clients
            from router_utils import get_routers
            
            # Get router info
            routers = get_routers()
            router = next((r for r in routers if r['id'] == router_id), None)
            
            if not router:
                return jsonify({"error": "Router not found"}), 404
            
            # Check if UniFi device
            is_unifi = router.get('is_unifi', False) or router.get('brand', '').lower() == 'unifi'
            
            if is_unifi:
                # For UniFi, return message to use UniFi API
                return jsonify({
                    "success": False,
                    "message": "UniFi devices should use UniFi API endpoint",
                    "is_unifi": True
                })
            
            # Run discovery for all routers, then filter by router_id
            all_clients = discover_clients(
                timeout=2,
                use_db_routers=True,
                scan_all_subnets=False
            )
            
            # Filter clients belonging to this router
            router_clients = []
            for mac, info in all_clients.items():
                if info.get("router_id") == router_id:
                    router_clients.append({
                        "mac_address": mac,
                        "ip_address": info.get("ip"),
                        "hostname": info.get("hostname", "Unknown"),
                        "vendor": info.get("vendor", "Unknown"),
                        "subnet": info.get("subnet"),
                        "interface": info.get("interface"),
                        "last_seen": info.get("last_seen").isoformat() if info.get("last_seen") else None
                    })
            
            return jsonify({
                "success": True,
                "router_id": router_id,
                "router_name": router.get('name'),
                "total_clients": len(router_clients),
                "clients": router_clients
            })
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/routers/<int:router_id>/clients/discover_save")
    def discover_and_save_router_clients(router_id):
        """
        Discover clients for a specific router, save them to DB with router association,
        and return the saved list. Intended for admin use.
        """
        try:
            from network_utils import discover_clients
            from router_utils import get_routers
            from db import save_network_client, create_network_clients_table, ensure_network_clients_router_columns

            create_network_clients_table()
            ensure_network_clients_router_columns()

            routers = get_routers()
            router = next((r for r in routers if r['id'] == router_id), None)
            if not router:
                return jsonify({"error": "Router not found"}), 404

            is_unifi = router.get('is_unifi', False) or router.get('brand', '').lower() == 'unifi'
            if is_unifi:
                return jsonify({
                    "success": False,
                    "message": "UniFi devices should use UniFi API endpoint",
                    "is_unifi": True
                }), 400

            all_clients = discover_clients(
                timeout=2,
                use_db_routers=True,
                scan_all_subnets=False
            )

            saved_clients = []
            for mac, info in all_clients.items():
                if info.get("router_id") == router_id:
                    # Save/update client with router association
                    save_network_client(
                        mac_address=mac,
                        ip_address=info.get("ip"),
                        hostname=info.get("hostname", "Unknown"),
                        vendor=info.get("vendor", "Unknown"),
                        ping_latency=None,
                        device_type=None,
                        notes=None,
                        router_id=router_id,
                        router_name=router.get('name')
                    )

                    saved_clients.append({
                        "mac_address": mac,
                        "ip_address": info.get("ip"),
                        "hostname": info.get("hostname", "Unknown"),
                        "vendor": info.get("vendor", "Unknown"),
                        "router_id": router_id,
                        "router_name": router.get('name'),
                        "last_seen": info.get("last_seen").isoformat() if info.get("last_seen") else None
                    })

            return jsonify({
                "success": True,
                "router_id": router_id,
                "router_name": router.get('name'),
                "total_saved": len(saved_clients),
                "clients": saved_clients
            })

        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/clients/<string:mac_address>/history")
    def get_client_connection_history(mac_address):
        """Get connection history for a specific client by MAC address."""
        try:
            from db import get_connection_history, create_connection_history_table
            
            create_connection_history_table()
            
            limit = int(request.args.get("limit", 50))
            history = get_connection_history(mac_address, limit=limit)
            
            # Convert datetime to ISO format
            for event in history:
                if 'event_time' in event and event['event_time']:
                    if hasattr(event['event_time'], 'isoformat'):
                        event['event_time'] = event['event_time'].isoformat()
            
            return jsonify({
                "success": True,
                "mac_address": mac_address,
                "total_events": len(history),
                "history": history
            })
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    # ==================== END CLIENT DISCOVERY ENDPOINTS ====================

    @app.get("/api/user/<int:user_id>/login-info")
    def get_user_login_info(user_id):
        """Get user's last login information including device details."""
        try:
            last_login = get_user_last_login_info(user_id)
            if not last_login:
                return jsonify({"error": "No login information found"}), 404
            
            return jsonify(last_login)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/user/<int:user_id>/login-history")
    def get_user_login_history_api(user_id):
        """Get user's login history."""
        try:
            limit = int(request.args.get("limit", 10))
            history = get_user_login_history(user_id, limit)
            return jsonify(history)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/users")
    def get_users():
        """Get all users for client portal user selection."""
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, username, role FROM users ORDER BY id")
            users = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify(users)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/create-client-session")
    def create_client_session():
        """Create or get a client user session for ticket submission."""
        try:
            data = request.get_json(force=True, silent=True) or {}
            client_name = data.get("client_name", "Client Portal User")
            
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # First, try to find an existing client user
            cursor.execute("SELECT id, username FROM users WHERE username = 'client' OR role = 'client' LIMIT 1")
            existing_client = cursor.fetchone()
            
            if existing_client:
                cursor.close()
                conn.close()
                return jsonify({
                    "user_id": existing_client["id"],
                    "username": existing_client["username"],
                    "message": "Using existing client user"
                })
            
            # If no client user exists, create one
            import hashlib
            default_password = "client123"
            password_hash = hashlib.sha256(default_password.encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, created_at) 
                VALUES (%s, %s, %s, NOW())
            """, ("client", password_hash, "client"))
            
            user_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({
                "user_id": user_id,
                "username": "client",
                "message": "Created new client user"
            })
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/technicians")
    def get_technicians():
        """Get all active technicians for assignment dropdown."""
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT t.id, t.user_id, t.name, t.specialization, t.department, 
                       t.contact_number, t.email, t.status, u.username
                FROM technicians t
                JOIN users u ON t.user_id = u.id
                WHERE t.status = 'active'
                ORDER BY t.name
            """)
            technicians = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify(technicians)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/tickets/<int:ticket_id>/assign")
    def assign_ticket_to_technician(ticket_id):
        """Assign a ticket to a technician."""
        try:
            data = request.get_json(force=True, silent=True) or {}
            technician_id = data.get("technician_id")
            assigned_by = data.get("assigned_by")  # Admin/manager user ID
            
            if not technician_id:
                return jsonify({"error": "Technician ID is required"}), 400
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Update ticket assignment
            cursor.execute("""
                UPDATE ict_service_requests 
                SET technician_assigned_id = %s, assigned_by = %s, assigned_at = NOW(),
                    status = 'assigned'
                WHERE ict_srf_no = %s
            """, (technician_id, assigned_by, ticket_id))
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({"error": "Ticket not found"}), 404
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({"message": "Ticket assigned successfully"})
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/tickets/<int:ticket_id>/accomplish")
    def add_accomplishment(ticket_id):
        """Add accomplishment details to a ticket."""
        try:
            data = request.get_json(force=True, silent=True) or {}
            accomplishment = data.get("accomplishment")
            accomplished_by = data.get("accomplished_by")  # Technician user ID
            service_time = data.get("service_time", "")
            response_time = data.get("response_time", "")
            
            if not accomplishment or not accomplishment.strip():
                return jsonify({"error": "Accomplishment description is required"}), 400
            
            if not accomplished_by:
                return jsonify({"error": "Accomplished by user ID is required"}), 400
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Update ticket with accomplishment and additional details
            update_fields = [
                "accomplishment = %s",
                "accomplished_by = %s", 
                "accomplished_at = NOW()",
                "status = 'completed'",
                "updated_at = NOW()"
            ]
            update_values = [accomplishment, accomplished_by]
            
            # Add optional fields if provided
            if service_time:
                update_fields.append("service_time = %s")
                update_values.append(service_time)
            
            if response_time:
                update_fields.append("response_time = %s")
                update_values.append(response_time)
            
            update_values.append(ticket_id)  # For WHERE clause
            
            sql = f"""
                UPDATE ict_service_requests 
                SET {', '.join(update_fields)}
                WHERE ict_srf_no = %s
            """
            
            cursor.execute(sql, update_values)
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({"error": "Ticket not found"}), 404
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({"message": "Accomplishment added successfully"})
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/technician/<int:technician_user_id>/tickets")
    def get_technician_assigned_tickets(technician_user_id):
        """Get tickets assigned to a specific technician."""
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT sr.*, t.name as technician_name, u.username as created_by_username
                FROM ict_service_requests sr
                LEFT JOIN technicians t ON sr.technician_assigned_id = t.id
                LEFT JOIN users u ON sr.created_by = u.id
                WHERE sr.technician_assigned_id = (
                    SELECT id FROM technicians WHERE user_id = %s LIMIT 1
                )
                ORDER BY sr.created_at DESC
            """, (technician_user_id,))
            tickets = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify(tickets)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/dashboard/online_history")
    def online_history():
        # Simple approximation: for each of last N days, count routers with last_seen on that day
        try:
            from datetime import datetime, timedelta
            days = int(request.args.get("days", 7))
            days = max(1, min(days, 30))
            routers = get_routers()
            today = datetime.now().date()
            series = []
            for d in range(days-1, -1, -1):
                day = today - timedelta(days=d)
                count = 0
                for r in routers:
                    ls = r.get('last_seen')
                    dt = None
                    if isinstance(ls, str):
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                            try:
                                dt = datetime.strptime(ls, fmt)
                                break
                            except Exception:
                                dt = None
                    elif ls and hasattr(ls, 'date'):
                        dt = ls
                    if dt and dt.date() == day:
                        count += 1
                series.append(count)
            return jsonify({"days": days, "values": series})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/reports/uptime")
    def reports_uptime():
        """Generate uptime and bandwidth reports for routers"""
        try:
            from datetime import datetime, time, timedelta
            
            # Get query parameters
            start_date_str = request.args.get("start_date")
            end_date_str = request.args.get("end_date")
            filter_mode = request.args.get("mode", "weekly")
            
            # Parse dates
            if not start_date_str or not end_date_str:
                return jsonify({"error": "start_date and end_date are required"}), 400
                
            start_date = datetime.combine(datetime.strptime(start_date_str, "%Y-%m-%d"), time.min)
            end_date = datetime.combine(datetime.strptime(end_date_str, "%Y-%m-%d"), time.max)
            
            if start_date > end_date:
                return jsonify({"error": "Start date cannot be after end date"}), 400
            
            # Get routers
            routers = get_routers()
            report_data = []
            
            # Utility function to format downtime
            def format_downtime(seconds):
                days, remainder = divmod(seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, sec = divmod(remainder, 60)
                if days > 0: return f"{days}d {hours}h {minutes}m"
                elif hours > 0: return f"{hours}h {minutes}m"
                elif minutes > 0: return f"{minutes}m {sec}s"
                else: return f"{sec}s"
            
            # Generate report data for each router
            for router in routers:
                router_id = router["id"]
                uptime = get_uptime_percentage(router_id, start_date, end_date)
                downtime_seconds = (1 - uptime / 100) * (end_date - start_date).total_seconds()
                downtime_str = format_downtime(int(downtime_seconds))
                bandwidth = get_bandwidth_usage(router_id, start_date, end_date)
                bandwidth_str = f"{bandwidth / 1024:.2f} GB" if bandwidth >= 1024 else f"{bandwidth:.2f} MB"
                
                report_data.append({
                    "router_id": router_id,
                    "router_name": router["name"],
                    "start_date": start_date_str,
                    "uptime_percentage": round(uptime, 2),
                    "downtime": downtime_str,
                    "bandwidth_usage": bandwidth_str,
                    "bandwidth_mb": round(bandwidth, 2)
                })
            
            # Generate aggregated data for charts
            def get_daily_avg_uptime(start_date, end_date):
                days = (end_date - start_date).days + 1
                results = []
                for i in range(days):
                    day_start = start_date + timedelta(days=i)
                    day_end = day_start.replace(hour=23, minute=59, second=59)
                    uptimes = [get_uptime_percentage(r["id"], day_start, day_end) for r in routers]
                    avg_uptime = sum(uptimes) / len(uptimes) if uptimes else 0
                    results.append((day_start, avg_uptime))
                return results
            
            daily_data = get_daily_avg_uptime(start_date, end_date)
            
            # Aggregate based on filter_mode
            aggregated = {}
            for date, uptime in daily_data:
                if filter_mode == "weekly":
                    key = date.strftime("Week %U (%Y)")
                elif filter_mode == "monthly":
                    key = date.strftime("%B %Y")
                else:  # daily
                    key = date.strftime("%m-%d")
                aggregated.setdefault(key, []).append(uptime)
            
            agg_dates = list(aggregated.keys())
            agg_uptimes = [sum(vals) / len(vals) for vals in aggregated.values()]
            
            return jsonify({
                "report_data": report_data,
                "chart_data": {
                    "dates": agg_dates,
                    "uptimes": agg_uptimes
                },
                "summary": {
                    "total_routers": len(routers),
                    "avg_uptime": round(sum(r["uptime_percentage"] for r in report_data) / len(report_data), 2) if report_data else 0,
                    "total_bandwidth": round(sum(r["bandwidth_mb"] for r in report_data), 2)
                }
            })
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/bandwidth/logs")
    def bandwidth_logs():
        """Get bandwidth logs for a specific router or all routers"""
        try:
            router_id = request.args.get("router_id", type=int)
            start_date = request.args.get("start_date")
            end_date = request.args.get("end_date")
            limit = request.args.get("limit", 1000, type=int)
            
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            if router_id:
                # Specific router
                if start_date and end_date:
                    query = """
                        SELECT timestamp, download_mbps, upload_mbps, latency_ms
                        FROM bandwidth_logs
                        WHERE router_id = %s AND DATE(timestamp) BETWEEN %s AND %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    """
                    cursor.execute(query, (router_id, start_date, end_date, limit))
                else:
                    query = """
                        SELECT timestamp, download_mbps, upload_mbps, latency_ms
                        FROM bandwidth_logs
                        WHERE router_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    """
                    cursor.execute(query, (router_id, limit))
            else:
                # All routers
                if start_date and end_date:
                    query = """
                        SELECT bl.timestamp, bl.download_mbps, bl.upload_mbps, bl.latency_ms, r.name as router_name
                        FROM bandwidth_logs bl
                        JOIN routers r ON bl.router_id = r.id
                        WHERE DATE(bl.timestamp) BETWEEN %s AND %s
                        ORDER BY bl.timestamp DESC
                        LIMIT %s
                    """
                    cursor.execute(query, (start_date, end_date, limit))
                else:
                    query = """
                        SELECT bl.timestamp, bl.download_mbps, bl.upload_mbps, bl.latency_ms, r.name as router_name
                        FROM bandwidth_logs bl
                        JOIN routers r ON bl.router_id = r.id
                        ORDER BY bl.timestamp DESC
                        LIMIT %s
                    """
                    cursor.execute(query, (limit,))
            
            data = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return jsonify(data)
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/bandwidth/stats")
    def bandwidth_stats():
        """Get bandwidth statistics for a router"""
        try:
            router_id = request.args.get("router_id", type=int)
            start_date = request.args.get("start_date")
            end_date = request.args.get("end_date")
            
            if not router_id:
                return jsonify({"error": "router_id is required"}), 400
            
            conn = get_connection()
            cursor = conn.cursor()
            
            if start_date and end_date:
                query = """
                    SELECT 
                        AVG(download_mbps) as avg_download,
                        AVG(upload_mbps) as avg_upload,
                        AVG(latency_ms) as avg_latency,
                        MAX(download_mbps) as max_download,
                        MAX(upload_mbps) as max_upload,
                        MIN(latency_ms) as min_latency,
                        COUNT(*) as total_measurements
                    FROM bandwidth_logs
                    WHERE router_id = %s AND DATE(timestamp) BETWEEN %s AND %s
                """
                cursor.execute(query, (router_id, start_date, end_date))
            else:
                query = """
                    SELECT 
                        AVG(download_mbps) as avg_download,
                        AVG(upload_mbps) as avg_upload,
                        AVG(latency_ms) as avg_latency,
                        MAX(download_mbps) as max_download,
                        MAX(upload_mbps) as max_upload,
                        MIN(latency_ms) as min_latency,
                        COUNT(*) as total_measurements
                    FROM bandwidth_logs
                    WHERE router_id = %s
                """
                cursor.execute(query, (router_id,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                stats = {
                    "avg_download": round(float(result[0] or 0), 2),
                    "avg_upload": round(float(result[1] or 0), 2),
                    "avg_latency": round(float(result[2] or 0), 2),
                    "max_download": round(float(result[3] or 0), 2),
                    "max_upload": round(float(result[4] or 0), 2),
                    "min_latency": round(float(result[5] or 0), 2),
                    "total_measurements": result[6] or 0
                }
                return jsonify(stats)
            else:
                return jsonify({
                    "avg_download": 0, "avg_upload": 0, "avg_latency": 0,
                    "max_download": 0, "max_upload": 0, "min_latency": 0,
                    "total_measurements": 0
                })
                
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/reports/pdf")
    def generate_pdf_report():
        """Generate PDF report for client"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.units import inch
            import tempfile
            import os
            from datetime import datetime
            
            # Get report parameters
            start_date = request.args.get("start_date")
            end_date = request.args.get("end_date")
            mode = request.args.get("mode", "weekly")
            
            # Validate dates
            if not start_date or not end_date:
                return jsonify({"error": "start_date and end_date are required"}), 400
            
            # Get report data
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Fetch routers and their uptime data
            query = """
                SELECT 
                    r.id,
                    r.name,
                    r.ip_address,
                    r.location,
                    COALESCE(bl.download_mbps, 0) as current_download,
                    COALESCE(bl.upload_mbps, 0) as current_upload,
                    COALESCE(bl.latency_ms, 0) as current_latency,
                    bl.timestamp as last_bandwidth_check
                FROM routers r
                LEFT JOIN (
                    SELECT router_id, download_mbps, upload_mbps, latency_ms, timestamp,
                           ROW_NUMBER() OVER (PARTITION BY router_id ORDER BY timestamp DESC) as rn
                    FROM bandwidth_logs
                ) bl ON r.id = bl.router_id AND bl.rn = 1
                ORDER BY r.name
            """
            cursor.execute(query)
            routers = cursor.fetchall()
            
            # Calculate uptime for each router
            report_data = []
            for router in routers:
                # Calculate uptime percentage (simplified - in real app, this would be more complex)
                uptime_percentage = 95.5  # Placeholder - would calculate from actual data
                downtime = "2h 15m"  # Placeholder
                bandwidth_usage = f"{router['current_download']:.1f} / {router['current_upload']:.1f} Mbps"
                
                report_data.append({
                    "router_name": router["name"],
                    "start_date": start_date,
                    "uptime_percentage": uptime_percentage,
                    "downtime": downtime,
                    "bandwidth_usage": bandwidth_usage,
                    "bandwidth_mb": router["current_download"] + router["current_upload"]
                })
            
            # Create temporary PDF file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_path = temp_file.name
            temp_file.close()
            
            # Create PDF document
            doc = SimpleDocTemplate(temp_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1  # Center alignment
            )
            title = Paragraph("Network Monitoring Report", title_style)
            story.append(title)
            
            # Report info
            info_style = ParagraphStyle(
                'Info',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=20,
                alignment=1
            )
            report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report_info = Paragraph(f"Generated on: {report_date}<br/>Period: {start_date} to {end_date}<br/>View Mode: {mode.title()}", info_style)
            story.append(report_info)
            
            # Summary section
            summary_style = ParagraphStyle(
                'Summary',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=10
            )
            story.append(Paragraph("Summary", summary_style))
            
            total_routers = len(routers)
            avg_uptime = sum(r["uptime_percentage"] for r in report_data) / len(report_data) if report_data else 0
            total_bandwidth = sum(r["bandwidth_mb"] for r in report_data)
            
            summary_data = [
                ["Total Routers", str(total_routers)],
                ["Average Uptime", f"{avg_uptime:.1f}%"],
                ["Total Bandwidth Usage", f"{total_bandwidth:.1f} MB"]
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Detailed report table
            story.append(Paragraph("Detailed Report", summary_style))
            
            # Prepare table data
            table_data = [["Router Name", "Start Date", "Uptime %", "Downtime", "Bandwidth Usage"]]
            for row in report_data:
                table_data.append([
                    row["router_name"],
                    row["start_date"],
                    f"{row['uptime_percentage']:.2f}%",
                    row["downtime"],
                    row["bandwidth_usage"]
                ])
            
            # Create table
            report_table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
            report_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            story.append(report_table)
            
            # Build PDF
            doc.build(story)
            
            # Read PDF content
            with open(temp_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            # Return PDF as response
            from flask import Response
            return Response(
                pdf_content,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename=network_report_{start_date}_to_{end_date}.pdf'
                }
            )
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/loop-detection")
    def get_loop_detection_data():
        """Get loop detection data for client view."""
        try:
            from db import get_loop_detections_history, get_loop_detection_stats
            
            # Get detection history
            detections = get_loop_detections_history(limit=100)
            
            # Get statistics
            stats = get_loop_detection_stats()
            
            return jsonify({
                "detections": detections,
                "stats": stats
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/reports/pdf-with-charts")
    def generate_pdf_report_with_charts():
        """Generate PDF report with charts for client"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
            from reportlab.lib.units import inch
            import tempfile
            import os
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            
            # Suppress matplotlib warnings
            import logging
            matplotlib_logger = logging.getLogger('matplotlib')
            matplotlib_logger.setLevel(logging.ERROR)
            
            from datetime import datetime
            import io
            import base64
            
            # Get report parameters
            start_date = request.args.get("start_date")
            end_date = request.args.get("end_date")
            mode = request.args.get("mode", "weekly")
            
            # Validate dates
            if not start_date or not end_date:
                return jsonify({"error": "start_date and end_date are required"}), 400
            
            # Get report data
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Fetch routers and their uptime data
            query = """
                SELECT 
                    r.id,
                    r.name,
                    r.ip_address,
                    r.location,
                    COALESCE(bl.download_mbps, 0) as current_download,
                    COALESCE(bl.upload_mbps, 0) as current_upload,
                    COALESCE(bl.latency_ms, 0) as current_latency,
                    bl.timestamp as last_bandwidth_check
                FROM routers r
                LEFT JOIN (
                    SELECT router_id, download_mbps, upload_mbps, latency_ms, timestamp,
                           ROW_NUMBER() OVER (PARTITION BY router_id ORDER BY timestamp DESC) as rn
                    FROM bandwidth_logs
                ) bl ON r.id = bl.router_id AND bl.rn = 1
                ORDER BY r.name
            """
            cursor.execute(query)
            routers = cursor.fetchall()
            
            # Calculate uptime for each router
            report_data = []
            for router in routers:
                # Calculate uptime percentage (simplified - in real app, this would be more complex)
                uptime_percentage = 95.5  # Placeholder - would calculate from actual data
                downtime = "2h 15m"  # Placeholder
                bandwidth_usage = f"{router['current_download']:.1f} / {router['current_upload']:.1f} Mbps"
                
                report_data.append({
                    "router_name": router["name"],
                    "start_date": start_date,
                    "uptime_percentage": uptime_percentage,
                    "downtime": downtime,
                    "bandwidth_usage": bandwidth_usage,
                    "bandwidth_mb": router["current_download"] + router["current_upload"]
                })
            
            # Create temporary PDF file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_path = temp_file.name
            temp_file.close()
            
            # Create PDF document
            doc = SimpleDocTemplate(temp_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1  # Center alignment
            )
            title = Paragraph("Network Monitoring Report with Charts", title_style)
            story.append(title)
            
            # Report info
            info_style = ParagraphStyle(
                'Info',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=20,
                alignment=1
            )
            report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report_info = Paragraph(f"Generated on: {report_date}<br/>Period: {start_date} to {end_date}<br/>View Mode: {mode.title()}", info_style)
            story.append(report_info)
            
            # Summary section
            summary_style = ParagraphStyle(
                'Summary',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=10
            )
            story.append(Paragraph("Summary", summary_style))
            
            total_routers = len(routers)
            avg_uptime = sum(r["uptime_percentage"] for r in report_data) / len(report_data) if report_data else 0
            total_bandwidth = sum(r["bandwidth_mb"] for r in report_data)
            
            summary_data = [
                ["Total Routers", str(total_routers)],
                ["Average Uptime", f"{avg_uptime:.1f}%"],
                ["Total Bandwidth Usage", f"{total_bandwidth:.1f} MB"]
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Create uptime trend chart
            chart_path = None
            try:
                # Generate sample chart data
                dates = [f"Day {i+1}" for i in range(7)]
                uptimes = [95.5, 96.2, 94.8, 97.1, 95.9, 96.5, 95.8]
                
                # Create chart
                fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
                ax.plot(dates, uptimes, marker='o', linewidth=2, markersize=6)
                ax.set_title("Average Uptime Trend")
                ax.set_xlabel("Date")
                ax.set_ylabel("Uptime %")
                ax.grid(True, alpha=0.3)
                ax.set_ylim(0, 100)
                
                # Save chart to temporary file
                chart_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                chart_path = chart_temp.name
                chart_temp.close()
                
                plt.savefig(chart_path, dpi=100, bbox_inches='tight')
                plt.close()
                
                # Add chart to PDF
                story.append(Paragraph("Uptime Trend Chart", summary_style))
                story.append(Image(chart_path, width=6*inch, height=3*inch))
                story.append(Spacer(1, 20))
                
            except Exception as e:
                print(f"Error creating chart: {e}")
                story.append(Paragraph("Chart generation failed", summary_style))
            
            # Detailed report table
            story.append(Paragraph("Detailed Report", summary_style))
            
            # Prepare table data
            table_data = [["Router Name", "Start Date", "Uptime %", "Downtime", "Bandwidth Usage"]]
            for row in report_data:
                table_data.append([
                    row["router_name"],
                    row["start_date"],
                    f"{row['uptime_percentage']:.2f}%",
                    row["downtime"],
                    row["bandwidth_usage"]
                ])
            
            # Create table
            report_table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
            report_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            story.append(report_table)
            
            # Build PDF
            doc.build(story)
            
            # Read PDF content
            with open(temp_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            # Clean up temporary files
            os.unlink(temp_path)
            if chart_path and os.path.exists(chart_path):
                os.unlink(chart_path)
            
            # Return PDF as response
            from flask import Response
            return Response(
                pdf_content,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename=network_report_with_charts_{start_date}_to_{end_date}.pdf'
                }
            )
            
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


