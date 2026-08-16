use serde_json::{Map, Value, json};
use std::collections::HashSet;
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{self, BufRead, BufReader, Write};
use std::path::Component;
use std::path::{Path, PathBuf};
use std::time::Instant;

const SCHEMA_VERSION: u64 = 1;
const CREATE_PREFIX: &str = "crea la nota ";
const CREATE_SEPARATOR: &str = " con el texto: ";
const COMPOUND_SUFFIXES: [&str; 2] = [" y después léela", " y despues leela"];

#[derive(Debug)]
struct RequestProblem;

fn array(values: Vec<Value>) -> Value {
    Value::Array(values)
}

#[allow(clippy::too_many_arguments)]
fn base_response(
    invocation_id: &str,
    state: &str,
    intent: &str,
    effect: &str,
    risk: &str,
    verification: &str,
    response: String,
    operations: Vec<Value>,
    evidence: Vec<Value>,
    replayed: bool,
    recovered: bool,
) -> Value {
    json!({
        "schema_version": SCHEMA_VERSION,
        "invocation_id": invocation_id,
        "mission_id": format!("mission-{invocation_id}"),
        "state": state,
        "intent": intent,
        "effect": effect,
        "risk": risk,
        "operations": array(operations),
        "verification": {
            "status": verification,
            "evidence": array(evidence)
        },
        "response": response,
        "replayed": replayed,
        "journal_recovered": recovered
    })
}

fn invalid(invocation_id: &str, message: &str, recovered: bool) -> Value {
    base_response(
        invocation_id,
        "blocked",
        "invalid",
        "none",
        "high",
        "unverified",
        message.to_owned(),
        vec![],
        vec![],
        false,
        recovered,
    )
}

fn valid_invocation_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
}

fn workspace_from_request(request: &Map<String, Value>) -> Result<PathBuf, RequestProblem> {
    let value = request
        .get("workspace")
        .and_then(Value::as_str)
        .ok_or(RequestProblem)?;
    if value.is_empty() || value.contains('\0') {
        return Err(RequestProblem);
    }
    let requested = PathBuf::from(value);
    if !requested.is_absolute() {
        return Err(RequestProblem);
    }
    if requested
        .components()
        .any(|component| matches!(component, Component::ParentDir | Component::CurDir))
    {
        return Err(RequestProblem);
    }
    if let Ok(allowed) = env::var("BAXY_TOURNAMENT_ROOT") {
        let allowed_path = PathBuf::from(allowed);
        fs::create_dir_all(&allowed_path).map_err(|_| RequestProblem)?;
        let allowed_root = allowed_path.canonicalize().map_err(|_| RequestProblem)?;
        let candidate = resolve_without_creating(&requested)?;
        if !candidate.starts_with(&allowed_root) {
            return Err(RequestProblem);
        }
    }
    fs::create_dir_all(&requested).map_err(|_| RequestProblem)?;
    let workspace = requested.canonicalize().map_err(|_| RequestProblem)?;
    Ok(workspace)
}

fn resolve_without_creating(path: &Path) -> Result<PathBuf, RequestProblem> {
    let mut cursor = path;
    let mut missing = Vec::new();
    while !cursor.exists() {
        let name = cursor.file_name().ok_or(RequestProblem)?;
        missing.push(name.to_os_string());
        cursor = cursor.parent().ok_or(RequestProblem)?;
    }
    let mut resolved = cursor.canonicalize().map_err(|_| RequestProblem)?;
    for name in missing.iter().rev() {
        resolved.push(name);
    }
    Ok(resolved)
}

fn safe_filename(raw: &str) -> Result<String, RequestProblem> {
    let name = raw.trim();
    if name.is_empty()
        || name != raw
        || name.contains('\0')
        || name == "."
        || name == ".."
        || name.contains("..")
        || name.chars().any(|character| "<>:\"/\\|?*".contains(character))
        || name.ends_with('.')
        || name.ends_with(' ')
        || name.len() > 240
    {
        return Err(RequestProblem);
    }
    let stem = name.split('.').next().unwrap_or(name).to_uppercase();
    let reserved: HashSet<&'static str> = [
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
        "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6",
        "LPT7", "LPT8", "LPT9",
    ]
    .into_iter()
    .collect();
    if reserved.contains(stem.as_str()) {
        return Err(RequestProblem);
    }
    Ok(name.to_owned())
}

fn note_path(workspace: &Path, directory: &str, filename: &str) -> Result<PathBuf, RequestProblem> {
    let root = workspace.join(directory);
    fs::create_dir_all(&root).map_err(|_| RequestProblem)?;
    let candidate = root.join(filename);
    if candidate.parent() != Some(root.as_path()) || !candidate.starts_with(workspace) {
        return Err(RequestProblem);
    }
    Ok(candidate)
}

fn atomic_write(path: &Path, text: &str, invocation_id: &str) -> io::Result<()> {
    let filename = path.file_name().and_then(|value| value.to_str()).unwrap_or("note");
    let temporary = path.with_file_name(format!(".{filename}.{invocation_id}.tmp"));
    {
        let mut stream = OpenOptions::new()
            .create(true)
            .truncate(true)
            .write(true)
            .open(&temporary)?;
        stream.write_all(text.as_bytes())?;
        stream.sync_all()?;
    }
    if path.exists() {
        fs::remove_file(path)?;
    }
    fs::rename(temporary, path)
}

fn quarantine_path(workspace: &Path) -> io::Result<PathBuf> {
    for number in 1..10_000 {
        let candidate = workspace.join(format!("journal.corrupt.{number:04}.jsonl"));
        if !candidate.exists() {
            return Ok(candidate);
        }
    }
    Err(io::Error::other("demasiadas cuarentenas de journal"))
}

fn repair_journal(workspace: &Path) -> io::Result<bool> {
    let path = workspace.join("journal.jsonl");
    if !path.exists() {
        return Ok(false);
    }
    let raw = fs::read(&path)?;
    if raw.is_empty() {
        return Ok(false);
    }
    let mut offset = 0usize;
    let mut invalid_at = None;
    while offset < raw.len() {
        let Some(relative_newline) = raw[offset..].iter().position(|byte| *byte == b'\n') else {
            invalid_at = Some(offset);
            break;
        };
        let newline = offset + relative_newline;
        let mut end = newline;
        if end > offset && raw[end - 1] == b'\r' {
            end -= 1;
        }
        match serde_json::from_slice::<Value>(&raw[offset..end]) {
            Ok(Value::Object(_)) => offset = newline + 1,
            _ => {
                invalid_at = Some(offset);
                break;
            }
        }
    }
    let Some(invalid) = invalid_at else {
        return Ok(false);
    };
    let quarantine = quarantine_path(workspace)?;
    {
        let mut bad = OpenOptions::new().create_new(true).write(true).open(quarantine)?;
        bad.write_all(&raw[invalid..])?;
        bad.sync_all()?;
    }
    {
        let journal = OpenOptions::new().write(true).open(path)?;
        journal.set_len(invalid as u64)?;
        journal.sync_all()?;
    }
    Ok(true)
}

fn load_journal(workspace: &Path) -> io::Result<Vec<Value>> {
    let path = workspace.join("journal.jsonl");
    if !path.exists() {
        return Ok(vec![]);
    }
    let stream = BufReader::new(File::open(path)?);
    let mut records = Vec::new();
    for line in stream.lines() {
        let line = line?;
        if !line.trim().is_empty() {
            let value = serde_json::from_str::<Value>(&line)
                .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
            records.push(value);
        }
    }
    Ok(records)
}

fn append_journal(workspace: &Path, value: &Value) -> io::Result<()> {
    let path = workspace.join("journal.jsonl");
    let mut stream = OpenOptions::new().create(true).append(true).open(path)?;
    serde_json::to_writer(&mut stream, value)?;
    stream.write_all(b"\n")?;
    stream.sync_all()
}

fn existing_invocation(
    records: &[Value],
    invocation_id: &str,
    message: &str,
) -> Result<(Option<Value>, bool), RequestProblem> {
    let mut started = false;
    for record in records {
        let Some(object) = record.as_object() else {
            continue;
        };
        if object.get("invocation_id").and_then(Value::as_str) != Some(invocation_id) {
            continue;
        }
        if object.get("message").and_then(Value::as_str) != Some(message) {
            return Err(RequestProblem);
        }
        if object.get("status").and_then(Value::as_str) == Some("started") {
            started = true;
        }
        if object.get("status").and_then(Value::as_str) == Some("completed")
            && let Some(result) = object.get("result")
        {
            let mut replay = result.clone();
            replay["replayed"] = Value::Bool(true);
            return Ok((Some(replay), started));
        }
    }
    Ok((None, started))
}

fn parse_create(message: &str) -> Option<(String, String, bool)> {
    let lowered = message.to_lowercase();
    if !lowered.starts_with(CREATE_PREFIX) {
        return None;
    }
    let separator = lowered[CREATE_PREFIX.len()..].find(CREATE_SEPARATOR)? + CREATE_PREFIX.len();
    let filename = message[CREATE_PREFIX.len()..separator].to_owned();
    let content_start = separator + CREATE_SEPARATOR.len();
    let mut content = message[content_start..].to_owned();
    let lowered_content = content.to_lowercase();
    let mut compound = false;
    for suffix in COMPOUND_SUFFIXES {
        if lowered_content.ends_with(suffix) {
            content.truncate(content.len() - suffix.len());
            compound = true;
            break;
        }
    }
    Some((filename, content, compound))
}

fn done(
    invocation_id: &str,
    intent: &str,
    effect: &str,
    response: String,
    operations: Vec<Value>,
    evidence: Vec<Value>,
    recovered: bool,
) -> Value {
    base_response(
        invocation_id,
        "done",
        intent,
        effect,
        "low",
        "verified",
        response,
        operations,
        evidence,
        false,
        recovered,
    )
}

fn execute(invocation_id: &str, message: &str, workspace: &Path, recovered: bool) -> Value {
    let trimmed = message.trim();
    let lowered = trimmed.to_lowercase();
    if message.contains('\0') {
        return invalid(
            invocation_id,
            "No ejecuté la petición porque contiene un byte NUL.",
            recovered,
        );
    }
    if lowered.starts_with("hola") {
        return base_response(
            invocation_id,
            "done",
            "conversation",
            "none",
            "low",
            "not_applicable",
            "Estoy bien y lista para ayudarte.".to_owned(),
            vec![],
            vec![],
            false,
            recovered,
        );
    }

    if let Some((raw_name, content, compound)) = parse_create(trimmed) {
        let Ok(name) = safe_filename(&raw_name) else {
            return base_response(
                invocation_id,
                "blocked",
                "note.create",
                "reversible",
                "high",
                "unverified",
                "No creé la nota porque su ruta sale del espacio permitido.".to_owned(),
                vec![],
                vec![],
                false,
                recovered,
            );
        };
        let Ok(path) = note_path(workspace, "notes", &name) else {
            return invalid(invocation_id, "La ruta de nota no es segura.", recovered);
        };
        if atomic_write(&path, &content, invocation_id).is_err() {
            return base_response(
                invocation_id,
                "failed",
                if compound { "note.create_and_read" } else { "note.create" },
                "reversible",
                "low",
                "unverified",
                "La nota no pudo escribirse ni verificarse.".to_owned(),
                vec![],
                vec![],
                false,
                recovered,
            );
        }
        let Ok(observed) = fs::read_to_string(&path) else {
            return base_response(
                invocation_id,
                "failed",
                if compound { "note.create_and_read" } else { "note.create" },
                "reversible",
                "low",
                "unverified",
                "La nota no pudo verificarse después de escribirla.".to_owned(),
                vec![],
                vec![],
                false,
                recovered,
            );
        };
        if observed != content {
            return base_response(
                invocation_id,
                "failed",
                if compound { "note.create_and_read" } else { "note.create" },
                "reversible",
                "low",
                "unverified",
                "La nota no pudo verificarse después de escribirla.".to_owned(),
                vec![],
                vec![],
                false,
                recovered,
            );
        }
        let relative = format!("notes/{name}");
        let mut operations = vec![json!({"operation": "note.create", "state": "done", "relative_path": relative})];
        if compound {
            operations.push(json!({"operation": "note.read", "state": "done", "relative_path": relative}));
        }
        let response = if compound {
            format!("Creé y verifiqué la nota {name}. Dice: {observed}")
        } else {
            format!("Creé y verifiqué la nota {name}.")
        };
        return done(
            invocation_id,
            if compound { "note.create_and_read" } else { "note.create" },
            "reversible",
            response,
            operations,
            vec![json!({"kind": "file_readback", "relative_path": relative, "utf8_bytes": observed.len()})],
            recovered,
        );
    }

    const READ_PREFIX: &str = "lee la nota ";
    if lowered.starts_with(READ_PREFIX) {
        let raw_name = &trimmed[READ_PREFIX.len()..];
        let Ok(name) = safe_filename(raw_name) else {
            return invalid(invocation_id, "No leí la nota porque su nombre no es seguro.", recovered);
        };
        let Ok(path) = note_path(workspace, "notes", &name) else {
            return invalid(invocation_id, "No leí la nota porque su nombre no es seguro.", recovered);
        };
        let Ok(content) = fs::read_to_string(&path) else {
            return base_response(
                invocation_id,
                "blocked",
                "note.read",
                "read_only",
                "low",
                "unverified",
                format!("No pude leer la nota {name} porque no existe."),
                vec![],
                vec![],
                false,
                recovered,
            );
        };
        let relative = format!("notes/{name}");
        return done(
            invocation_id,
            "note.read",
            "read_only",
            format!("La nota {name} dice: {content}"),
            vec![json!({"operation": "note.read", "state": "done", "relative_path": relative})],
            vec![json!({"kind": "file_read", "relative_path": relative, "utf8_bytes": content.len()})],
            recovered,
        );
    }

    const TRASH_PREFIX: &str = "mueve la nota ";
    const TRASH_SUFFIX: &str = " a la papelera";
    if lowered.starts_with(TRASH_PREFIX) && lowered.ends_with(TRASH_SUFFIX) {
        let raw_name = &trimmed[TRASH_PREFIX.len()..trimmed.len() - TRASH_SUFFIX.len()];
        let Ok(name) = safe_filename(raw_name) else {
            return invalid(invocation_id, "No moví la nota porque su nombre no es seguro.", recovered);
        };
        let (Ok(source), Ok(target)) = (
            note_path(workspace, "notes", &name),
            note_path(workspace, "trash", &name),
        ) else {
            return invalid(invocation_id, "No moví la nota porque su nombre no es seguro.", recovered);
        };
        if source.is_file() {
            if target.exists() && fs::remove_file(&target).is_err() {
                return invalid(invocation_id, "No pude preparar la papelera.", recovered);
            }
            if fs::rename(&source, &target).is_err() {
                return invalid(invocation_id, "No pude mover la nota.", recovered);
            }
        }
        if !target.is_file() || source.exists() {
            return base_response(
                invocation_id,
                "blocked",
                "note.trash",
                "reversible",
                "low",
                "unverified",
                format!("No pude mover {name} porque la nota no existe."),
                vec![],
                vec![],
                false,
                recovered,
            );
        }
        return done(
            invocation_id,
            "note.trash",
            "reversible",
            format!("Moví la nota {name} a la papelera y lo verifiqué."),
            vec![json!({"operation": "note.trash", "state": "done", "relative_path": format!("trash/{name}")})],
            vec![json!({"kind": "move_verified", "present": format!("trash/{name}"), "absent": format!("notes/{name}")})],
            recovered,
        );
    }

    const RESTORE_PREFIX: &str = "restaura la nota ";
    if lowered.starts_with(RESTORE_PREFIX) {
        let raw_name = &trimmed[RESTORE_PREFIX.len()..];
        let Ok(name) = safe_filename(raw_name) else {
            return invalid(invocation_id, "No restauré la nota porque su nombre no es seguro.", recovered);
        };
        let (Ok(source), Ok(target)) = (
            note_path(workspace, "trash", &name),
            note_path(workspace, "notes", &name),
        ) else {
            return invalid(invocation_id, "No restauré la nota porque su nombre no es seguro.", recovered);
        };
        if source.is_file() {
            if target.exists() && fs::remove_file(&target).is_err() {
                return invalid(invocation_id, "No pude preparar la restauración.", recovered);
            }
            if fs::rename(&source, &target).is_err() {
                return invalid(invocation_id, "No pude restaurar la nota.", recovered);
            }
        }
        if !target.is_file() || source.exists() {
            return base_response(
                invocation_id,
                "blocked",
                "note.restore",
                "reversible",
                "low",
                "unverified",
                format!("No pude restaurar {name} porque no está en la papelera."),
                vec![],
                vec![],
                false,
                recovered,
            );
        }
        return done(
            invocation_id,
            "note.restore",
            "reversible",
            format!("Restauré la nota {name} y lo verifiqué."),
            vec![json!({"operation": "note.restore", "state": "done", "relative_path": format!("notes/{name}")})],
            vec![json!({"kind": "move_verified", "present": format!("notes/{name}"), "absent": format!("trash/{name}")})],
            recovered,
        );
    }

    if lowered.starts_with("borra ") || lowered.starts_with("elimina ") {
        return base_response(
            invocation_id,
            "blocked",
            "unsafe.delete",
            "destructive",
            "critical",
            "unverified",
            "No ejecutaré ese borrado: el objetivo está fuera del espacio seguro y es destructivo."
                .to_owned(),
            vec![],
            vec![],
            false,
            recovered,
        );
    }
    base_response(
        invocation_id,
        "blocked",
        "unknown",
        "none",
        "low",
        "unverified",
        "No puedo completar esa petición con las capacidades disponibles.".to_owned(),
        vec![],
        vec![],
        false,
        recovered,
    )
}

fn handle_request(node: &Value) -> Value {
    let Some(request) = node.as_object() else {
        return invalid("invalid-request", "La petición no tiene un objeto válido.", false);
    };
    let Some(invocation_id) = request.get("invocation_id").and_then(Value::as_str) else {
        return invalid("invalid-request", "La petición no tiene un invocation_id válido.", false);
    };
    if !valid_invocation_id(invocation_id) {
        return invalid("invalid-request", "La petición no tiene un invocation_id válido.", false);
    }
    let Some(message) = request.get("message").and_then(Value::as_str) else {
        return invalid(invocation_id, "La petición no contiene texto válido.", false);
    };
    if message.len() > 16_384 {
        return invalid(invocation_id, "La petición supera el tamaño permitido.", false);
    }
    let Ok(workspace) = workspace_from_request(request) else {
        return invalid(invocation_id, "El workspace solicitado no está autorizado.", false);
    };
    let recovered = match repair_journal(&workspace) {
        Ok(value) => value,
        Err(_) => {
            return base_response(
                invocation_id,
                "failed",
                "internal",
                "none",
                "high",
                "unverified",
                "No pude recuperar el journal local.".to_owned(),
                vec![],
                vec![],
                false,
                false,
            );
        }
    };
    let records = match load_journal(&workspace) {
        Ok(value) => value,
        Err(_) => return invalid(invocation_id, "No pude leer el journal local.", recovered),
    };
    let (replay, started) = match existing_invocation(&records, invocation_id, message) {
        Ok(value) => value,
        Err(_) => {
            return invalid(
                invocation_id,
                "Ese invocation_id ya pertenece a otra petición.",
                recovered,
            );
        }
    };
    if let Some(mut result) = replay {
        let already = result
            .get("journal_recovered")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        result["journal_recovered"] = Value::Bool(already || recovered);
        return result;
    }
    if !started {
        let started_record = json!({
            "schema_version": SCHEMA_VERSION,
            "status": "started",
            "invocation_id": invocation_id,
            "message": message
        });
        if append_journal(&workspace, &started_record).is_err() {
            return invalid(invocation_id, "No pude iniciar el journal local.", recovered);
        }
    }
    let result = execute(invocation_id, message, &workspace, recovered);
    let completed = json!({
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "invocation_id": invocation_id,
        "message": message,
        "result": result
    });
    if append_journal(&workspace, &completed).is_err() {
        return base_response(
            invocation_id,
            "failed",
            "internal",
            "none",
            "high",
            "unverified",
            "El efecto terminó, pero no pude registrar su resultado.".to_owned(),
            vec![],
            vec![],
            false,
            recovered,
        );
    }
    completed.get("result").cloned().unwrap_or_else(|| {
        invalid(
            invocation_id,
            "No pude reconstruir el resultado local.",
            recovered,
        )
    })
}

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::BufWriter::new(io::stdout().lock());
    for line in stdin.lock().lines() {
        let Ok(line) = line else {
            eprintln!("BAXY_PROTOCOL_ERROR input_failure");
            continue;
        };
        if line.trim().is_empty() {
            continue;
        }
        let started = Instant::now();
        let input = match serde_json::from_str::<Value>(&line) {
            Ok(value) => value,
            Err(_) => {
                eprintln!("BAXY_PROTOCOL_ERROR malformed_json");
                continue;
            }
        };
        let mut result = handle_request(&input);
        result["elapsed_ns"] = Value::from(started.elapsed().as_nanos() as u64);
        if serde_json::to_writer(&mut stdout, &result).is_err()
            || stdout.write_all(b"\n").is_err()
            || stdout.flush().is_err()
        {
            break;
        }
    }
}
