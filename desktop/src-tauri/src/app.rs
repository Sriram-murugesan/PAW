//! Window, commands and wiring.

use std::collections::BTreeMap;
use std::ffi::OsString;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Emitter, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;

use crate::api_proxy::{self, ApiResponse, ProxyError};
use crate::backend::{BackendCommand, Status, Supervisor};
use crate::files::{self, FileError};

pub const STATUS_EVENT: &str = "backend-status";

struct Api {
    client: reqwest::Client,
}

async fn call(
    supervisor: &Supervisor,
    api: &Api,
    method: &str,
    path: &str,
    query: &BTreeMap<String, String>,
    body: Option<&Value>,
) -> Result<ApiResponse, ProxyError> {
    let endpoint = supervisor.endpoint().ok_or(ProxyError::Unavailable)?;
    api_proxy::send(&api.client, &endpoint, method, path, query, body).await
}

#[tauri::command]
async fn api_request(
    supervisor: State<'_, Supervisor>,
    api: State<'_, Api>,
    method: String,
    path: String,
    query: BTreeMap<String, String>,
    body: Option<Value>,
) -> Result<ApiResponse, ProxyError> {
    call(&supervisor, &api, &method, &path, &query, body.as_ref()).await
}

#[tauri::command]
fn backend_status(supervisor: State<'_, Supervisor>) -> Status {
    supervisor.status()
}

#[tauri::command]
fn backend_retry(supervisor: State<'_, Supervisor>) {
    supervisor.start();
}

#[derive(Clone, Copy, Deserialize)]
#[serde(rename_all = "lowercase")]
enum ExportFormat {
    Json,
    Markdown,
}

#[derive(Serialize)]
#[serde(tag = "result", rename_all = "snake_case")]
enum FileOutcome {
    Cancelled,
    Done { count: u64, skipped: u64 },
    Failed { message: String },
}

fn failed(message: impl Into<String>) -> FileOutcome {
    FileOutcome::Failed {
        message: message.into(),
    }
}

async fn in_background<T: Send + 'static>(work: impl FnOnce() -> T + Send + 'static) -> Option<T> {
    tauri::async_runtime::spawn_blocking(work).await.ok()
}

#[tauri::command]
async fn export_memories(
    app: AppHandle,
    supervisor: State<'_, Supervisor>,
    api: State<'_, Api>,
    format: ExportFormat,
) -> Result<FileOutcome, ()> {
    let (name, kind) = match format {
        ExportFormat::Json => ("paw-memories.json", "json"),
        ExportFormat::Markdown => ("paw-memories.md", "markdown"),
    };
    let dialog = app.dialog().file().set_file_name(name);
    let Some(chosen) = in_background(move || dialog.blocking_save_file())
        .await
        .flatten()
    else {
        return Ok(FileOutcome::Cancelled);
    };
    let Ok(path) = chosen.into_path() else {
        return Ok(failed("That location cannot be used."));
    };
    let query = BTreeMap::from([("format".to_owned(), kind.to_owned())]);
    let response = call(&supervisor, &api, "GET", "/api/memory/export", &query, None).await;
    let Ok(ApiResponse { status: 200, body }) = response else {
        return Ok(failed("PAW could not read your memories."));
    };
    let data = &body["data"];
    let count = data["count"].as_u64().unwrap_or(0);
    let text = match format {
        ExportFormat::Markdown => data["markdown"].as_str().map(str::to_owned),
        ExportFormat::Json => serde_json::to_string_pretty(data).ok(),
    };
    let Some(text) = text else {
        return Ok(failed("PAW could not prepare the export."));
    };
    Ok(
        match in_background(move || files::write_private(&path, &text)).await {
            Some(Ok(())) => FileOutcome::Done { count, skipped: 0 },
            _ => failed("The file could not be written."),
        },
    )
}

#[tauri::command]
async fn import_memories(
    app: AppHandle,
    supervisor: State<'_, Supervisor>,
    api: State<'_, Api>,
) -> Result<FileOutcome, ()> {
    let dialog = app.dialog().file().add_filter("JSON", &["json"]);
    let Some(chosen) = in_background(move || dialog.blocking_pick_file())
        .await
        .flatten()
    else {
        return Ok(FileOutcome::Cancelled);
    };
    let Ok(path) = chosen.into_path() else {
        return Ok(failed("That file cannot be used."));
    };
    let text = match in_background(move || files::read_limited(&path)).await {
        Some(Ok(text)) => text,
        Some(Err(FileError::TooLarge)) => return Ok(failed("The file is larger than 1 MB.")),
        _ => return Ok(failed("The file could not be read.")),
    };
    let Ok(items) = serde_json::from_str::<Value>(&text) else {
        return Ok(failed("The file is not valid JSON."));
    };
    let path = "/api/memory/proposals/import";
    let response = call(
        &supervisor,
        &api,
        "POST",
        path,
        &BTreeMap::new(),
        Some(&items),
    )
    .await;
    Ok(match response {
        Ok(ApiResponse { status: 201, body }) => FileOutcome::Done {
            count: body["data"]["added"].as_u64().unwrap_or(0),
            skipped: body["data"]["skipped"].as_u64().unwrap_or(0),
        },
        Ok(ApiResponse { status: 422, body }) => {
            let field = &body["error"]["details"]["fields"][0];
            failed(format!(
                "The file does not match the import format ({}: {}).",
                field["field"].as_str().unwrap_or("file"),
                field["message"].as_str().unwrap_or("not valid"),
            ))
        }
        _ => failed("PAW could not import the file."),
    })
}

/// Only what the backend needs. The token is not among these; it goes over stdin.
fn backend_environment() -> Vec<(OsString, OsString)> {
    ["HOME", "XDG_DATA_HOME", "LANG", "LC_ALL", "TZ", "PATH"]
        .iter()
        .filter_map(|name| Some((OsString::from(name), std::env::var_os(name)?)))
        .collect()
}

fn backend_program(app: &AppHandle) -> PathBuf {
    if cfg!(debug_assertions) {
        return PathBuf::from(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../.venv/bin/paw-backend"
        ));
    }
    app.path()
        .resource_dir()
        .unwrap_or_default()
        .join("backend/paw-backend")
}

fn is_own_page(url: &tauri::Url) -> bool {
    let dev = cfg!(debug_assertions)
        && url.scheme() == "http"
        && url.host_str() == Some("localhost")
        && url.port() == Some(1420);
    (url.scheme() == "tauri" && url.host_str() == Some("localhost")) || dev
}

fn setup(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let handle = app.handle().clone();
    let supervisor = Supervisor::new(
        BackendCommand {
            program: backend_program(&handle),
            args: vec!["serve".into()],
            env: backend_environment(),
        },
        move |status| {
            let _ = handle.emit(STATUS_EVENT, status);
        },
    );
    app.manage(supervisor.clone());
    app.manage(Api {
        client: api_proxy::client()?,
    });
    supervisor.start();
    let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
        .title("PAW")
        .inner_size(1120.0, 660.0)
        .center()
        .min_inner_size(760.0, 500.0)
        .on_navigation(is_own_page);
    #[cfg(feature = "smoke")]
    let window = crate::smoke::attach(window);
    window.build()?;
    Ok(())
}

pub fn run() -> tauri::Result<()> {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .setup(setup);
    #[cfg(not(feature = "smoke"))]
    let builder = builder.invoke_handler(tauri::generate_handler![
        api_request,
        backend_status,
        backend_retry,
        export_memories,
        import_memories
    ]);
    #[cfg(feature = "smoke")]
    let builder = builder.invoke_handler(tauri::generate_handler![
        api_request,
        backend_status,
        backend_retry,
        export_memories,
        import_memories,
        crate::smoke::smoke_report
    ]);
    let app = builder.build(tauri::generate_context!())?;
    app.run(|app, event| {
        if let RunEvent::Exit = event {
            app.state::<Supervisor>().stop();
        }
    });
    Ok(())
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn only_own_pages_load() {
        assert!(is_own_page(&"tauri://localhost/".parse().unwrap()));
        for bad in [
            "https://example.com/",
            "http://localhost:8000/",
            "file:///etc/passwd",
            "data:text/html,x",
            "tauri://evil/",
        ] {
            assert!(!is_own_page(&bad.parse().unwrap()), "{bad}");
        }
    }

    #[test]
    fn token_names_are_not_passed_on() {
        let names: Vec<_> = backend_environment().into_iter().map(|(k, _)| k).collect();
        assert!(names.iter().all(|n| n != "PYTHONPATH" && n != "LD_PRELOAD"));
    }
}
