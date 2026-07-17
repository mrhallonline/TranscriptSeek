use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;

#[derive(Debug, Deserialize)]
struct UiRequest {
    action: String,
    #[serde(default)]
    payload: Value,
}

#[derive(Debug, Serialize)]
struct ServiceRequest<'a> {
    id: u64,
    version: u8,
    action: &'a str,
    payload: &'a Value,
}

struct ServiceBridge {
    _child: Child,
    input: ChildStdin,
    output: BufReader<ChildStdout>,
    next_id: u64,
}

impl ServiceBridge {
    fn spawn() -> Result<Self, String> {
        let configured = std::env::var_os("TRANSCRIPTSEEK_SERVICE");
        let mut command = if let Some(executable) = configured {
            Command::new(executable)
        } else {
            let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
            let project_dir = manifest_dir.parent().ok_or("Cannot locate project directory")?;
            let mut python = Command::new(if cfg!(windows) { "python" } else { "python3" });
            python.arg("-m").arg("transcriptseek.ipc");
            python.env("PYTHONPATH", project_dir.join("src"));
            python
        };

        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .env("PYTHONUNBUFFERED", "1")
            .spawn()
            .map_err(|error| format!("Unable to start the local research service: {error}"))?;
        let input = child.stdin.take().ok_or("Research service stdin unavailable")?;
        let output = child.stdout.take().ok_or("Research service stdout unavailable")?;
        Ok(Self { _child: child, input, output: BufReader::new(output), next_id: 1 })
    }

    fn request(&mut self, request: UiRequest) -> Result<Value, String> {
        let id = self.next_id;
        self.next_id += 1;
        let service_request = ServiceRequest { id, version: 1, action: &request.action, payload: &request.payload };
        serde_json::to_writer(&mut self.input, &service_request)
            .map_err(|error| format!("Unable to encode local request: {error}"))?;
        self.input.write_all(b"\n").map_err(|error| format!("Unable to send local request: {error}"))?;
        self.input.flush().map_err(|error| format!("Unable to flush local request: {error}"))?;

        let mut line = String::new();
        self.output.read_line(&mut line).map_err(|error| format!("Unable to read local response: {error}"))?;
        let response: Value = serde_json::from_str(&line).map_err(|_| "The local service returned an invalid response".to_string())?;
        if response.get("id").and_then(Value::as_u64) != Some(id) {
            return Err("Local service response did not match its request".into());
        }
        if response.get("ok").and_then(Value::as_bool) != Some(true) {
            return Err(response.pointer("/error/message").and_then(Value::as_str).unwrap_or("Local service request failed").to_string());
        }
        Ok(response.get("result").cloned().unwrap_or(Value::Null))
    }
}

#[tauri::command]
fn ipc_request(request: UiRequest, state: tauri::State<'_, Mutex<ServiceBridge>>) -> Result<Value, String> {
    state.lock().map_err(|_| "Local service lock was poisoned".to_string())?.request(request)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let bridge = ServiceBridge::spawn().expect("failed to initialize private local research service");
    tauri::Builder::default()
        .manage(Mutex::new(bridge))
        .invoke_handler(tauri::generate_handler![ipc_request])
        .run(tauri::generate_context!())
        .expect("error while running TranscriptSeek");
}

