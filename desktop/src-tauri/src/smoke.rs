//! Test-only: runs a script inside the real WebView and reports its result. See Cargo feature `smoke`.

use tauri::webview::PageLoadEvent;
use tauri::{AppHandle, Manager, Runtime, WebviewWindowBuilder};

pub fn attach<'a, R: Runtime, M: Manager<R>>(
    window: WebviewWindowBuilder<'a, R, M>,
) -> WebviewWindowBuilder<'a, R, M> {
    let script = std::env::var_os("PAW_SMOKE_SCRIPT")
        .and_then(|path| std::fs::read_to_string(path).ok())
        .unwrap_or_default();
    window.on_page_load(move |window, payload| {
        if payload.event() == PageLoadEvent::Finished {
            let _ = window.eval(&script);
        }
    })
}

#[tauri::command]
pub fn smoke_report(app: AppHandle, report: String, exit: bool) {
    println!("SMOKE {report}");
    if exit {
        // The same path as the window's close button.
        if let Some(window) = app.get_webview_window("main") {
            let _ = window.close();
        }
    }
}
