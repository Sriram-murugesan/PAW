//! Starts, watches and stops the Python backend.
//!
//! The backend exits when its stdin closes. The kernel closes our end when this process ends for
//! any reason, so a crash here cannot leave the backend running.

use std::ffi::OsString;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::{Arc, Condvar, Mutex, MutexGuard, PoisonError};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};

const START_TIMEOUT: Duration = Duration::from_secs(30);
const MAX_RESTARTS: u32 = 3;
/// A backend that ran this long was healthy, so earlier failures no longer count.
const STABLE_AFTER: Duration = Duration::from_secs(60);

#[derive(Clone)]
pub struct BackendCommand {
    pub program: PathBuf,
    pub args: Vec<OsString>,
    pub env: Vec<(OsString, OsString)>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum Status {
    Starting,
    Ready,
    Failed { code: String },
    Stopped,
}

#[derive(Clone)]
pub struct Endpoint {
    pub port: u16,
    pub token: String,
}

#[derive(Deserialize)]
#[serde(tag = "event", rename_all = "snake_case")]
enum Hello {
    Ready { port: u16 },
    Error { code: String },
}

struct Shared {
    status: Status,
    endpoint: Option<Endpoint>,
    stdin: Option<ChildStdin>,
    pid: Option<u32>,
    stopping: bool,
}

struct Inner {
    command: BackendCommand,
    shared: Mutex<Shared>,
    wake: Condvar,
    on_status: Box<dyn Fn(Status) + Send + Sync>,
}

#[derive(Clone)]
pub struct Supervisor {
    inner: Arc<Inner>,
    worker: Arc<Mutex<Option<JoinHandle<()>>>>,
}

fn lock<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex.lock().unwrap_or_else(PoisonError::into_inner)
}

impl Supervisor {
    pub fn new(
        command: BackendCommand,
        on_status: impl Fn(Status) + Send + Sync + 'static,
    ) -> Self {
        let shared = Shared {
            status: Status::Stopped,
            endpoint: None,
            stdin: None,
            pid: None,
            stopping: false,
        };
        Self {
            inner: Arc::new(Inner {
                command,
                shared: Mutex::new(shared),
                wake: Condvar::new(),
                on_status: Box::new(on_status),
            }),
            worker: Arc::new(Mutex::new(None)),
        }
    }

    /// Start, or start again after a failure. Does nothing while already running.
    pub fn start(&self) {
        let mut worker = lock(&self.worker);
        if worker.as_ref().is_some_and(|w| !w.is_finished()) {
            return;
        }
        lock(&self.inner.shared).stopping = false;
        self.inner.set_status(Status::Starting);
        let inner = Arc::clone(&self.inner);
        *worker = Some(thread::spawn(move || inner.run()));
    }

    pub fn status(&self) -> Status {
        lock(&self.inner.shared).status.clone()
    }

    pub fn endpoint(&self) -> Option<Endpoint> {
        lock(&self.inner.shared).endpoint.clone()
    }

    pub fn pid(&self) -> Option<u32> {
        lock(&self.inner.shared).pid
    }

    /// Ask the backend to exit, then insist. Returns once it is gone.
    pub fn stop(&self) {
        {
            let mut shared = lock(&self.inner.shared);
            shared.stopping = true;
            shared.stdin = None; // EOF: the backend finishes its requests and exits
            self.inner.wake.notify_all();
        }
        for (wait, signal) in [(7, libc::SIGTERM), (2, libc::SIGKILL)] {
            if self.wait_finished(Duration::from_secs(wait)) {
                break;
            }
            self.signal(signal);
        }
        if let Some(worker) = lock(&self.worker).take() {
            let _ = worker.join();
        }
        self.inner.set_status(Status::Stopped);
    }

    fn wait_finished(&self, limit: Duration) -> bool {
        let deadline = Instant::now() + limit;
        loop {
            if lock(&self.worker)
                .as_ref()
                .is_none_or(JoinHandle::is_finished)
            {
                return true;
            }
            if Instant::now() >= deadline {
                return false;
            }
            thread::sleep(Duration::from_millis(25));
        }
    }

    fn signal(&self, signal: i32) {
        // The worker clears pid under this lock only after reaping, so the pid is still ours.
        let shared = lock(&self.inner.shared);
        if let Some(pid) = shared.pid.and_then(|p| i32::try_from(p).ok()) {
            // SAFETY: plain system call with no memory arguments.
            unsafe { libc::kill(pid, signal) };
        }
    }
}

impl Inner {
    fn set_status(&self, status: Status) {
        let changed = {
            let mut shared = lock(&self.shared);
            let changed = shared.status != status;
            shared.status = status.clone();
            changed
        };
        if changed {
            (self.on_status)(status);
        }
    }

    fn stopping(&self) -> bool {
        lock(&self.shared).stopping
    }

    fn run(&self) {
        let mut restarts = 0;
        loop {
            let started = Instant::now();
            let failure = self.run_once();
            if self.stopping() {
                return;
            }
            if started.elapsed() > STABLE_AFTER {
                restarts = 0;
            }
            // Errors the backend reports itself will not improve by trying again.
            if failure.permanent || restarts >= MAX_RESTARTS {
                self.set_status(Status::Failed { code: failure.code });
                return;
            }
            restarts += 1;
            self.set_status(Status::Starting);
            let pause = Duration::from_millis(250 * u64::from(1u32 << restarts));
            let shared = lock(&self.shared);
            let _ = self.wake.wait_timeout_while(shared, pause, |s| !s.stopping);
            if self.stopping() {
                return;
            }
        }
    }

    fn run_once(&self) -> Failure {
        let Ok(token) = new_token() else {
            return Failure::permanent("no_randomness");
        };
        let mut child = match self.spawn(&token) {
            Ok(child) => child,
            Err(code) => return Failure::permanent(code),
        };
        let hello = self.read_hello(&mut child);
        let outcome = match hello {
            Some(Hello::Ready { port }) => {
                lock(&self.shared).endpoint = Some(Endpoint { port, token });
                self.set_status(Status::Ready);
                Failure::transient("backend_exited")
            }
            Some(Hello::Error { code }) => Failure {
                code,
                permanent: true,
            },
            None => {
                if !self.stopping() {
                    let _ = child.kill();
                }
                Failure::transient("backend_did_not_start")
            }
        };
        self.reap(child);
        outcome
    }

    fn spawn(&self, token: &str) -> Result<Child, &'static str> {
        let mut child = Command::new(&self.command.program)
            .args(&self.command.args)
            .env_clear() // nothing such as PYTHONPATH leaks in
            .envs(self.command.env.iter().cloned())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null()) // the backend keeps its own log
            .spawn()
            .map_err(|_| "backend_not_found")?;
        let mut stdin = child.stdin.take();
        if let Some(pipe) = stdin.as_mut() {
            let _ = pipe.write_all(format!("{token}\n").as_bytes());
            let _ = pipe.flush();
        }
        let mut shared = lock(&self.shared);
        shared.pid = Some(child.id());
        // If stop() ran meanwhile, dropping stdin here delivers the EOF it wanted to send.
        shared.stdin = if shared.stopping { None } else { stdin };
        Ok(child)
    }

    fn read_hello(&self, child: &mut Child) -> Option<Hello> {
        let stdout = child.stdout.take()?;
        let (send, receive) = mpsc::channel();
        thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            let mut line = String::new();
            let _ = reader.read_line(&mut line);
            let _ = send.send(line);
            // Keep draining so that the backend can never block on a full pipe.
            let _ = std::io::copy(&mut reader, &mut std::io::sink());
        });
        match receive.recv_timeout(START_TIMEOUT) {
            Ok(line) => serde_json::from_str(&line).ok(),
            Err(RecvTimeoutError::Timeout | RecvTimeoutError::Disconnected) => None,
        }
    }

    fn reap(&self, mut child: Child) {
        // Wait without reaping first, so that pid and process disappear together under the lock.
        loop {
            {
                let mut shared = lock(&self.shared);
                if matches!(child.try_wait(), Ok(Some(_)) | Err(_)) {
                    shared.pid = None;
                    shared.endpoint = None;
                    shared.stdin = None;
                    self.wake.notify_all();
                    return;
                }
            }
            thread::sleep(Duration::from_millis(50));
        }
    }
}

struct Failure {
    code: String,
    permanent: bool,
}

impl Failure {
    fn permanent(code: &str) -> Self {
        Self {
            code: code.to_owned(),
            permanent: true,
        }
    }

    fn transient(code: &str) -> Self {
        Self {
            code: code.to_owned(),
            permanent: false,
        }
    }
}

/// 256 random bits as hexadecimal.
fn new_token() -> Result<String, getrandom::Error> {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes)?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}
