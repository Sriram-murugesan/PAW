//! Runs the real Python backend from the workspace environment.
#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use paw_desktop::api_proxy::{self, ApiResponse, ProxyError};
use paw_desktop::backend::{BackendCommand, Status, Supervisor};
use serde_json::{Value, json};

fn real_backend(home: &Path) -> BackendCommand {
    BackendCommand {
        program: PathBuf::from(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../.venv/bin/paw-backend"
        )),
        args: vec!["serve".into()],
        env: vec![
            ("XDG_DATA_HOME".into(), home.into()),
            ("HOME".into(), home.into()),
        ],
    }
}

fn script(body: &str) -> BackendCommand {
    BackendCommand {
        program: "/bin/sh".into(),
        args: vec!["-c".into(), body.into()],
        env: vec![("PATH".into(), "/usr/bin:/bin".into())],
    }
}

type Log = Arc<Mutex<Vec<Status>>>;

fn supervise(command: BackendCommand) -> (Supervisor, Log) {
    let log: Log = Arc::default();
    let copy = Arc::clone(&log);
    let supervisor = Supervisor::new(command, move |s| copy.lock().unwrap().push(s));
    supervisor.start();
    (supervisor, log)
}

fn wait_until(what: &str, seconds: u64, check: impl Fn() -> bool) {
    let deadline = Instant::now() + Duration::from_secs(seconds);
    while !check() {
        assert!(Instant::now() < deadline, "timed out: {what}");
        std::thread::sleep(Duration::from_millis(20));
    }
}

fn wait_ready(supervisor: &Supervisor) -> u32 {
    wait_until("ready", 30, || supervisor.status() == Status::Ready);
    supervisor.pid().unwrap()
}

fn alive(pid: u32) -> bool {
    Path::new(&format!("/proc/{pid}")).exists()
}

async fn call(
    s: &Supervisor,
    method: &str,
    path: &str,
    body: Option<Value>,
) -> Result<ApiResponse, ProxyError> {
    let client = api_proxy::client().unwrap();
    let endpoint = s.endpoint().unwrap();
    api_proxy::send(
        &client,
        &endpoint,
        method,
        path,
        &BTreeMap::new(),
        body.as_ref(),
    )
    .await
}

fn memory() -> Value {
    json!({"category": "achievement", "title": "Kept", "content": "From Rust"})
}

#[tokio::test(flavor = "multi_thread")]
async fn memory_survives_restart_through_the_proxy() {
    let home = tempfile::tempdir().unwrap();
    let (first, log) = supervise(real_backend(home.path()));
    let pid = wait_ready(&first);
    let made = call(&first, "POST", "/api/memory", Some(memory()))
        .await
        .unwrap();
    assert_eq!(made.status, 201);
    first.stop();
    assert!(!alive(pid));
    assert!(first.endpoint().is_none());
    assert_eq!(
        *log.lock().unwrap(),
        [Status::Starting, Status::Ready, Status::Stopped]
    );

    let (second, _) = supervise(real_backend(home.path()));
    wait_ready(&second);
    let list = call(&second, "GET", "/api/memory", None).await.unwrap();
    assert_eq!(list.body["data"][0]["title"], "Kept");
    let id = list.body["data"][0]["id"].as_str().unwrap();
    let archived = call(&second, "POST", &format!("/api/memory/{id}/archive"), None).await;
    assert_eq!(archived.unwrap().status, 200, "POST without a body");
    let gone = call(&second, "DELETE", &format!("/api/memory/{id}"), None)
        .await
        .unwrap();
    assert_eq!((gone.status, gone.body), (204, Value::Null));
    second.stop();
}

#[tokio::test(flavor = "multi_thread")]
async fn query_text_is_encoded_and_errors_pass_through() {
    let home = tempfile::tempdir().unwrap();
    let (s, _) = supervise(real_backend(home.path()));
    wait_ready(&s);
    call(&s, "POST", "/api/memory", Some(memory()))
        .await
        .unwrap();
    let client = api_proxy::client().unwrap();
    for (text, expected) in [("rust", 1), ("a&limit=0#x", 0), ("100%", 0)] {
        let query = BTreeMap::from([("q".to_owned(), text.to_owned())]);
        let endpoint = s.endpoint().unwrap();
        let r = api_proxy::send(&client, &endpoint, "GET", "/api/memory", &query, None)
            .await
            .unwrap();
        assert_eq!(r.status, 200, "{text}");
        assert_eq!(r.body["data"].as_array().unwrap().len(), expected, "{text}");
    }
    let bad = call(&s, "POST", "/api/memory", Some(json!({})))
        .await
        .unwrap();
    assert_eq!(bad.status, 422);
    let huge = json!({"content": "x".repeat(1_100_000)});
    let refused = call(&s, "POST", "/api/memory", Some(huge)).await;
    assert_eq!(refused.unwrap_err(), ProxyError::TooLarge);
    let refused = call(&s, "GET", "/health", None).await;
    assert_eq!(refused.unwrap_err(), ProxyError::NotAllowed);
    s.stop();
}

#[test]
fn restarts_after_a_crash() {
    let home = tempfile::tempdir().unwrap();
    let (s, log) = supervise(real_backend(home.path()));
    let first = wait_ready(&s);
    let token = s.endpoint().unwrap().token;
    // SAFETY: plain system call.
    unsafe { libc::kill(first.cast_signed(), libc::SIGKILL) };
    wait_until("restart", 30, || {
        s.status() == Status::Ready && s.pid().is_some_and(|p| p != first)
    });
    assert_ne!(
        s.endpoint().unwrap().token,
        token,
        "each run has its own token"
    );
    s.stop();
    assert_eq!(
        *log.lock().unwrap(),
        [
            Status::Starting,
            Status::Ready,
            Status::Starting,
            Status::Ready,
            Status::Stopped
        ]
    );
}

#[test]
fn token_is_not_in_the_process_listing() {
    let home = tempfile::tempdir().unwrap();
    let (s, _) = supervise(real_backend(home.path()));
    let pid = wait_ready(&s);
    let token = s.endpoint().unwrap().token;
    assert_eq!(token.len(), 64);
    for file in ["cmdline", "environ"] {
        let text = std::fs::read(format!("/proc/{pid}/{file}")).unwrap();
        assert!(!String::from_utf8_lossy(&text).contains(&token), "{file}");
    }
    s.stop();
}

#[test]
fn second_instance_reports_why_and_does_not_retry() {
    let home = tempfile::tempdir().unwrap();
    let (first, _) = supervise(real_backend(home.path()));
    wait_ready(&first);
    let (second, log) = supervise(real_backend(home.path()));
    let failed = Status::Failed {
        code: "already_running".into(),
    };
    wait_until("failure", 30, || second.status() == failed);
    assert_eq!(*log.lock().unwrap(), [Status::Starting, failed]);
    first.stop();
    second.start();
    wait_ready(&second);
    second.stop();
}

#[test]
fn gives_up_after_repeated_crashes() {
    let home = tempfile::tempdir().unwrap();
    let marks = home.path().join("marks");
    let (s, _) = supervise(script(&format!("echo x >> {}; exit 1", marks.display())));
    let failed = Status::Failed {
        code: "backend_did_not_start".into(),
    };
    wait_until("give up", 30, || s.status() == failed);
    assert_eq!(std::fs::read_to_string(&marks).unwrap().lines().count(), 4);
    s.stop();
}

#[test]
fn missing_program_is_reported() {
    let mut command = script("");
    command.program = "/nonexistent/paw-backend".into();
    let (s, _) = supervise(command);
    let failed = Status::Failed {
        code: "backend_not_found".into(),
    };
    wait_until("failure", 5, || s.status() == failed);
    s.stop();
}

#[test]
fn environment_is_not_inherited() {
    // Cargo sets CARGO_MANIFEST_DIR for tests, so it would be visible if inherited.
    assert!(std::env::var_os("CARGO_MANIFEST_DIR").is_some());
    let code = "read t; if [ -n \"$CARGO_MANIFEST_DIR\" ]; then c=leaked; else c=clean; fi; \
                echo '{\"event\":\"error\",\"code\":\"'$c'\"}'";
    let (s, _) = supervise(script(code));
    let clean = Status::Failed {
        code: "clean".into(),
    };
    wait_until("report", 5, || s.status() == clean);
    s.stop();
}

#[test]
fn stop_is_safe_at_any_moment() {
    for delay in [0, 1, 20, 300, 1200] {
        let home = tempfile::tempdir().unwrap();
        let (s, _) = supervise(real_backend(home.path()));
        std::thread::sleep(Duration::from_millis(delay));
        let pid = s.pid();
        s.stop();
        assert_eq!(s.status(), Status::Stopped);
        assert!(pid.is_none_or(|p| !alive(p)), "after {delay} ms");
        assert!(s.pid().is_none());
    }
}

#[test]
fn stubborn_backend_is_killed() {
    let ready = "read t; trap '' TERM; echo '{\"event\":\"ready\",\"port\":1}'; \
                 while :; do sleep 0.1; done";
    let (s, _) = supervise(script(ready));
    let pid = wait_ready(&s);
    s.stop();
    assert!(!alive(pid));
}
