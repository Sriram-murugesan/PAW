//! Import and export. File paths come from native dialogs, never from the interface.

use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::os::unix::fs::OpenOptionsExt;
use std::path::Path;

pub const MAX_IMPORT: u64 = 1_000_000;

#[derive(Debug, PartialEq, Eq)]
pub enum FileError {
    TooLarge,
    NotText,
    Io,
}

/// Write a private file, replacing the target only once the new content is complete.
pub fn write_private(path: &Path, content: &str) -> Result<(), FileError> {
    let name = path.file_name().ok_or(FileError::Io)?.to_string_lossy();
    let partial = path.with_file_name(format!(".{name}.{}.partial", std::process::id()));
    let result = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&partial)
        .and_then(|mut file| {
            file.write_all(content.as_bytes())?;
            file.sync_all()
        })
        .and_then(|()| std::fs::rename(&partial, path));
    if result.is_err() {
        let _ = std::fs::remove_file(&partial);
    }
    result.map_err(|_| FileError::Io)
}

pub fn read_limited(path: &Path) -> Result<String, FileError> {
    let file = File::open(path).map_err(|_| FileError::Io)?;
    if !file.metadata().map_err(|_| FileError::Io)?.is_file() {
        return Err(FileError::Io);
    }
    let mut bytes = Vec::new();
    file.take(MAX_IMPORT + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| FileError::Io)?;
    if bytes.len() as u64 > MAX_IMPORT {
        return Err(FileError::TooLarge);
    }
    String::from_utf8(bytes).map_err(|_| FileError::NotText)
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;

    #[test]
    fn writes_privately_and_replaces() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("out.json");
        std::fs::write(&path, "old").unwrap();
        write_private(&path, "new").unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "new");
        let mode = std::fs::metadata(&path).unwrap().permissions().mode();
        assert_eq!(mode & 0o777, 0o600);
        assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(), 1);
    }

    #[test]
    fn failed_write_leaves_the_old_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("taken");
        std::fs::create_dir_all(path.join("x")).unwrap();
        assert_eq!(write_private(&path, "new"), Err(FileError::Io));
        assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(), 1);
    }

    #[test]
    fn limits_imports() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("in");
        std::fs::write(&path, "ok").unwrap();
        assert_eq!(read_limited(&path), Ok("ok".into()));
        std::fs::write(&path, vec![b'a'; 1_000_001]).unwrap();
        assert_eq!(read_limited(&path), Err(FileError::TooLarge));
        std::fs::write(&path, [0xff, 0xfe]).unwrap();
        assert_eq!(read_limited(&path), Err(FileError::NotText));
        assert_eq!(read_limited(dir.path()), Err(FileError::Io));
    }
}
