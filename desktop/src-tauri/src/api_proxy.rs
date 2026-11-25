//! The only way the interface reaches the backend. The token stays on this side.

use std::collections::BTreeMap;
use std::time::Duration;

use reqwest::{Client, Method, Url, redirect};
use serde::Serialize;
use serde_json::Value;

use crate::backend::Endpoint;

const MAX_BODY: usize = 1_048_576;
const TIMEOUT: Duration = Duration::from_secs(60);

#[derive(Debug, Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: Value,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ProxyError {
    NotAllowed,
    TooLarge,
    Unavailable,
}

pub fn client() -> Result<Client, reqwest::Error> {
    Client::builder()
        .no_proxy() // a system proxy must never see the token
        .redirect(redirect::Policy::none())
        .timeout(TIMEOUT)
        .build()
}

fn allowed_method(method: &str) -> Option<Method> {
    match method {
        "GET" => Some(Method::GET),
        "POST" => Some(Method::POST),
        "PUT" => Some(Method::PUT),
        "DELETE" => Some(Method::DELETE),
        _ => None,
    }
}

/// Plain segments under /api only: no dots, percent escapes, query, fragment or empty segments.
fn allowed_path(path: &str) -> bool {
    path.len() <= 200
        && path.strip_prefix("/api/").is_some_and(|rest| {
            rest.split('/').all(|segment| {
                !segment.is_empty()
                    && segment
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
            })
        })
}

pub async fn send(
    client: &Client,
    endpoint: &Endpoint,
    method: &str,
    path: &str,
    query: &BTreeMap<String, String>,
    body: Option<&Value>,
) -> Result<ApiResponse, ProxyError> {
    let method = allowed_method(method).ok_or(ProxyError::NotAllowed)?;
    if !allowed_path(path) {
        return Err(ProxyError::NotAllowed);
    }
    let mut url = Url::parse(&format!("http://127.0.0.1:{}{path}", endpoint.port))
        .map_err(|_| ProxyError::NotAllowed)?;
    if !query.is_empty() {
        url.query_pairs_mut().extend_pairs(query);
    }
    // An explicit length, even zero, because the backend refuses chunked bodies.
    let payload = match body {
        Some(value) => serde_json::to_vec(value).map_err(|_| ProxyError::NotAllowed)?,
        None => Vec::new(),
    };
    if payload.len() > MAX_BODY {
        return Err(ProxyError::TooLarge);
    }
    let mut request = client.request(method, url).bearer_auth(&endpoint.token);
    if body.is_some() {
        request = request
            .header("content-type", "application/json")
            .body(payload);
    }
    // Error text is dropped: it would contain the URL and so the search text.
    let response = request.send().await.map_err(|_| ProxyError::Unavailable)?;
    let status = response.status().as_u16();
    let bytes = response
        .bytes()
        .await
        .map_err(|_| ProxyError::Unavailable)?;
    let body = if bytes.is_empty() {
        Value::Null
    } else {
        serde_json::from_slice(&bytes).map_err(|_| ProxyError::Unavailable)?
    };
    Ok(ApiResponse { status, body })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paths() {
        for good in [
            "/api/memory",
            "/api/memory/proposals",
            "/api/backups/20261124T170000000000Z_manual_0a1b2c3d/restore",
            "/api/memory/00000000-0000-4000-8000-000000000000",
        ] {
            assert!(allowed_path(good), "{good}");
        }
        for bad in [
            "",
            "/",
            "/health",
            "/api",
            "/api/",
            "/api//memory",
            "/api/memory/",
            "/api/../health",
            "/api/memory/..",
            "/api/%2e%2e/health",
            "/api/memory?x=1",
            "/api/memory#x",
            "/api/memory\\x",
            "/api/memory x",
            "/api/mem\u{f6}ry",
            "@evil.example/api/memory",
            "http://evil.example/api/memory",
            "//evil.example/api/memory",
            "/api/memory\r\nX: y",
        ] {
            assert!(!allowed_path(bad), "{bad}");
        }
        assert!(!allowed_path(&format!("/api/{}", "a".repeat(300))));
    }

    #[test]
    fn methods() {
        assert!(allowed_method("GET").is_some());
        for bad in ["get", "PATCH", "CONNECT", "TRACE", "OPTIONS", ""] {
            assert!(allowed_method(bad).is_none(), "{bad}");
        }
    }
}
