# ticket_utils.py
from db import get_connection
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
