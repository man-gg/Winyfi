# ticket_utils.py
from db import get_connection
import mysql.connector
from datetime import datetime

# -----------------------------
# ICT Service Request Form (SRF) functions
# -----------------------------
def create_srf(data: dict, created_by: int):
    """
    Create a new ICT Service Request.
    data keys: ict_srf_no (int), campus, office_building, client_name, date_time_call,
               technician_assigned, required_response_time, services_requirements,
               response_time, service_time, remarks
    created_by: user ID of the creator
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
    INSERT INTO ict_service_requests
    (ict_srf_no, campus, office_building, client_name, date_time_call, technician_assigned,
     required_response_time, services_requirements, response_time, service_time, remarks,
     created_by, created_at, updated_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
    """
    cursor.execute(sql, (
        data['ict_srf_no'], data['campus'], data['office_building'], data['client_name'],
        data['date_time_call'], data['technician_assigned'], data.get('required_response_time'),
        data.get('services_requirements'), data.get('response_time'), data.get('service_time'),
        data.get('remarks'), created_by
    ))
    conn.commit()
    cursor.close()
    conn.close()


def fetch_srfs():
    """Fetch all ICT Service Requests along with creator username."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
    SELECT s.*, u.username AS created_by_username
    FROM ict_service_requests s
    JOIN users u ON s.created_by = u.id
    ORDER BY s.created_at DESC
    """
    cursor.execute(sql)
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data


def fetch_tickets():
    """Return normalized ticket records for export/consumers.

    Maps ICT Service Requests (SRFs) to a generic ticket shape expected by the UI:
    - id: ict_srf_no
    - router_name: uses office_building or campus as a human-friendly context
    - issue: services_requirements or fallback to remarks
    - status: 'status' column if present, else defaults to 'open'
    - created_by: username if available, else created_by id
    - created_at / updated_at: pass-through datetime values
    """
    srfs = fetch_srfs() or []
    tickets = []
    for s in srfs:
        tickets.append({
            "id": s.get("ict_srf_no"),
            "router_name": s.get("office_building") or s.get("campus") or None,
            "issue": s.get("services_requirements") or s.get("remarks") or "",
            "status": s.get("status") or "open",
            "created_by": s.get("created_by_username") or s.get("created_by"),
            "created_at": s.get("created_at"),
            "updated_at": s.get("updated_at"),
        })
    return tickets

def update_srf(ict_srf_no, update_data: dict):
    """Update an existing SRF by its number."""
    conn = get_connection()
    cursor = conn.cursor()
    fields = ', '.join([f"{k}=%s" for k in update_data.keys()])
    sql = f"UPDATE ict_service_requests SET {fields}, updated_at=NOW() WHERE ict_srf_no=%s"
    values = list(update_data.values()) + [ict_srf_no]
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()


def update_ticket_status(ict_srf_no, status):
    """Update the status of a specific ticket.

    If the 'status' column is missing (MySQL error 1054), the function will
    attempt to add it automatically and retry the update once.
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = "UPDATE ict_service_requests SET status=%s, updated_at=NOW() WHERE ict_srf_no=%s"
    try:
        cursor.execute(sql, (status, ict_srf_no))
        conn.commit()
    except mysql.connector.Error as e:
        # Error 1054: Unknown column 'status' in 'field list'
        if getattr(e, "errno", None) == 1054 or "Unknown column 'status'" in str(e):
            try:
                # Create the missing column with a sensible default
                cursor.execute(
                    """
                    ALTER TABLE ict_service_requests
                    ADD COLUMN status VARCHAR(50) DEFAULT 'open' AFTER remarks
                    """
                )
                # Retry the update
                cursor.execute(sql, (status, ict_srf_no))
                conn.commit()
            except Exception as inner_e:
                conn.rollback()
                raise inner_e
        else:
            raise
    finally:
        cursor.close()
        conn.close()


def get_srf_by_id(ict_srf_no):
    """Get a specific SRF by its number."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
    SELECT s.*, u.username AS created_by_username
    FROM ict_service_requests s
    JOIN users u ON s.created_by = u.id
    WHERE s.ict_srf_no = %s
    """
    cursor.execute(sql, (ict_srf_no,))
    data = cursor.fetchone()
    cursor.close()
    conn.close()
    return data
