use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::env;
use std::fs;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;
use tauri::{Manager, State};

#[derive(Deserialize)]
struct UiRequest {
    invocation_id: String,
    message: String,
}

#[derive(Serialize)]
struct RuntimeInfo {
    automation: bool,
}

struct CoreProcess {
    child: Child,
    input: BufWriter<ChildStdin>,
    output: BufReader<ChildStdout>,
    workspace: PathBuf,
}

impl CoreProcess {
    fn spawn(app: &tauri::App) -> Result<Self, String> {
        let core_path = match env::var_os("BAXY_ROUND_B_CORE") {
            Some(path) => PathBuf::from(path),
            None => app
                .path()
                .resource_dir()
                .map_err(|_| "No se pudo resolver el directorio de recursos.".to_owned())?
                .join("core")
                .join("baxy-rust-slice.exe"),
        };
        let core_path = core_path
            .canonicalize()
            .map_err(|_| "No se encontró el core Rust empaquetado.".to_owned())?;
        let data_root = match env::var_os("BAXY_ROUND_B_DATA") {
            Some(path) => PathBuf::from(path),
            None => app
                .path()
                .app_local_data_dir()
                .map_err(|_| "No se pudo resolver el directorio local de BAXY.".to_owned())?,
        };
        fs::create_dir_all(&data_root)
            .map_err(|_| "No se pudo preparar el directorio local de BAXY.".to_owned())?;
        let data_root = data_root
            .canonicalize()
            .map_err(|_| "No se pudo validar el directorio local de BAXY.".to_owned())?;
        let workspace = data_root.join("workspace");
        fs::create_dir_all(&workspace)
            .map_err(|_| "No se pudo preparar el workspace local.".to_owned())?;

        let mut child = Command::new(&core_path)
            .arg("--server")
            .current_dir(core_path.parent().ok_or_else(|| "Ruta de core inválida.".to_owned())?)
            .env("BAXY_TOURNAMENT_ROOT", &data_root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| "El core Rust no pudo iniciarse.".to_owned())?;
        let input = child
            .stdin
            .take()
            .ok_or_else(|| "El canal de entrada del core no está disponible.".to_owned())?;
        let output = child
            .stdout
            .take()
            .ok_or_else(|| "El canal de salida del core no está disponible.".to_owned())?;
        Ok(Self {
            child,
            input: BufWriter::new(input),
            output: BufReader::new(output),
            workspace,
        })
    }

    fn submit(&mut self, request: UiRequest) -> Result<Value, String> {
        if request.invocation_id.is_empty()
            || request.invocation_id.len() > 128
            || request.message.as_bytes().len() > 16_384
        {
            return Err("La petición de interfaz no es válida.".to_owned());
        }
        if self
            .child
            .try_wait()
            .map_err(|_| "No se pudo comprobar el core local.".to_owned())?
            .is_some()
        {
            return Err("El core local terminó antes de responder.".to_owned());
        }
        let wire = json!({
            "invocation_id": request.invocation_id,
            "message": request.message,
            "workspace": self.workspace,
        });
        serde_json::to_writer(&mut self.input, &wire)
            .map_err(|_| "No se pudo codificar la petición local.".to_owned())?;
        self.input
            .write_all(b"\n")
            .and_then(|_| self.input.flush())
            .map_err(|_| "No se pudo enviar la petición al core local.".to_owned())?;
        let mut output = String::new();
        self.output
            .read_line(&mut output)
            .map_err(|_| "No se pudo leer el resultado del core local.".to_owned())?;
        if output.trim().is_empty() {
            return Err("El core local no devolvió un resultado.".to_owned());
        }
        let response: Value = serde_json::from_str(&output)
            .map_err(|_| "El core local devolvió un resultado inválido.".to_owned())?;
        if response.get("invocation_id").and_then(Value::as_str)
            != wire.get("invocation_id").and_then(Value::as_str)
        {
            return Err("El core respondió para otra invocación.".to_owned());
        }
        Ok(response)
    }
}

impl Drop for CoreProcess {
    fn drop(&mut self) {
        let _ = self.input.flush();
        if self.child.try_wait().ok().flatten().is_none() {
            let _ = self.child.kill();
            let _ = self.child.wait();
        }
    }
}

struct AppState {
    core: Mutex<CoreProcess>,
}

#[tauri::command]
fn submit(request: UiRequest, state: State<'_, AppState>) -> Result<Value, String> {
    let mut core = state
        .core
        .lock()
        .map_err(|_| "El core local no está disponible.".to_owned())?;
    core.submit(request)
}

#[tauri::command]
fn runtime_info() -> RuntimeInfo {
    RuntimeInfo {
        automation: env::var("BAXY_ROUND_B_AUTOMATION").is_ok_and(|value| value == "1"),
    }
}

fn main() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let core = CoreProcess::spawn(app)?;
            app.manage(AppState {
                core: Mutex::new(core),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![submit, runtime_info])
        .build(tauri::generate_context!())
        .expect("BAXY Tauri no pudo inicializarse");
    app.run(|_, _| {});
}
