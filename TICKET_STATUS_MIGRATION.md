# Ticket Status Column Migration

## Summary
If you encounter this error when updating a ticket status:

```
Error updating ticket status: 1054 (42S22): Unknown column 'status' in 'field list'
```

It means your `ict_service_requests` table doesn't have a `status` column yet.

## Fix Options

### 1) Auto-healing (now built-in)
As of this change, calling `ticket_utils.update_ticket_status(...)` will automatically:
- Detect MySQL error 1054 for missing `status` column
- Run an `ALTER TABLE` to add `status VARCHAR(50) DEFAULT 'open'`
- Retry the update once

No action is required on your part; the first status update will self-migrate.

### 2) Manual Migration (optional, recommended)
Run the migration script to add both `status` and `priority` columns ahead of time:

```powershell
# From the workspace root
py migrate_ticket_schema.py
```

This will:
- Add `status VARCHAR(50) DEFAULT 'open'` (if missing)
- Add `priority VARCHAR(20) DEFAULT 'Normal'` (if missing)

## Notes
- New SRFs will default to `status='open'` if not specified.
- UI will show a status badge based on the `status` value (e.g., Open, In Progress, Resolved).
- Exports and detail views will include `status` once present in the table.

## Troubleshooting
- If the migration fails, verify database connectivity and permissions in `db.py` (get_connection).
- Some MySQL installations require specifying `TABLE_SCHEMA` in INFORMATION_SCHEMA queries; the manual migration script is designed to work with a proper default database selected in the connection.
