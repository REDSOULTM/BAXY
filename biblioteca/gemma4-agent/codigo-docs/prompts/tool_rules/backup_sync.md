Backup rule: backup_sync(...) creates and restores local ZIP backups. Actions: status, backup_create, list, restore, dedupe, verify.

Distinct from filesystem(action='archive'|'unarchive') (one-off zip ops) and from cloud sync. backup_sync keeps an index, supports overwrite|skip|rename on restore, finds duplicates by SHA256, and verifies ZIP integrity.

Use this when the user wants a recoverable snapshot of a folder, or to deduplicate a tree. Not for off-machine replication.
