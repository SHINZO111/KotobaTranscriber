// Tauri IPC commands
// Rust functions callable from the frontend (Svelte) via invoke()

use crate::AppState;
use tauri::State;
use tauri_plugin_dialog::DialogExt;

/// Get the current API port number.
/// Returns None if the sidecar has not reported its port yet.
#[tauri::command]
pub fn get_api_port(state: State<'_, AppState>) -> Result<Option<u16>, String> {
    Ok(state.get_port())
}

/// Get the current API authentication token.
/// Returns None if the sidecar has not reported its token yet.
#[tauri::command]
pub fn get_api_token(state: State<'_, AppState>) -> Result<Option<String>, String> {
    Ok(state.get_token())
}

/// Native file dialog -- single file selection.
/// Returns the selected file path as a string, or None if cancelled.
#[tauri::command]
pub fn select_file(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let file = app
        .dialog()
        .file()
        .add_filter(
            "Audio/Video Files",
            &[
                "mp3", "wav", "m4a", "flac", "ogg", "aac", "wma", "opus", "amr",
                "mp4", "avi", "mov", "mkv", "3gp", "webm",
            ],
        )
        .add_filter("All Files", &["*"])
        .blocking_pick_file();

    match file {
        Some(path) => Ok(Some(path.to_string())),
        None => Ok(None),
    }
}

/// Native file dialog -- multiple file selection.
/// Returns a list of selected file paths, or empty list if cancelled.
#[tauri::command]
pub fn select_files(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    let files = app
        .dialog()
        .file()
        .add_filter(
            "Audio/Video Files",
            &[
                "mp3", "wav", "m4a", "flac", "ogg", "aac", "wma", "opus", "amr",
                "mp4", "avi", "mov", "mkv", "3gp", "webm",
            ],
        )
        .add_filter("All Files", &["*"])
        .blocking_pick_files();

    match files {
        Some(paths) => Ok(paths.into_iter().map(|f| f.to_string()).collect()),
        None => Ok(vec![]),
    }
}

/// Native folder selection dialog.
/// Returns the selected folder path as a string, or None if cancelled.
#[tauri::command]
pub fn select_folder(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let folder = app.dialog().file().blocking_pick_folder();
    match folder {
        Some(path) => Ok(Some(path.to_string())),
        None => Ok(None),
    }
}
