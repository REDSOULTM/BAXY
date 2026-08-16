Dependency rule: dependency(...) diagnoses Python modules and system binaries that other tools rely on. Actions: status, list, verify, explain_missing, install, repair.

Distinct from package(...) (installs end-user desktop apps via winget). dependency is about what the AGENT itself needs (ffmpeg for media_edit, psycopg for database, etc.).

install is advisory unless explicitly wired elsewhere — report the install hint and let the user decide unless they asked for an automated repair.
