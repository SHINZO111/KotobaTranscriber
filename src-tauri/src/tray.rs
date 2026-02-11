// System tray management

use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::TrayIconBuilder,
    Manager,
};

/// Create the system tray with show/hide/quit menu items
pub fn create_tray(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let show = MenuItemBuilder::with_id("show", "表示").build(app)?;
    let hide = MenuItemBuilder::with_id("hide", "非表示").build(app)?;
    let quit = MenuItemBuilder::with_id("quit", "終了").build(app)?;

    let menu = MenuBuilder::new(app)
        .item(&show)
        .item(&hide)
        .separator()
        .item(&quit)
        .build()?;

    // Generate a 32x32 orange "K" icon (RGBA)
    let icon_data = create_tray_icon_rgba();
    let icon = Image::new_owned(icon_data, 32, 32);

    TrayIconBuilder::new()
        .icon(icon)
        .tooltip("KotobaTranscriber")
        .menu(&menu)
        .on_menu_event(move |app, event| match event.id().as_ref() {
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.unminimize();
                    let _ = window.set_focus();
                }
            }
            "hide" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
            }
            "quit" => {
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let tauri::tray::TrayIconEvent::Click {
                button: tauri::tray::MouseButton::Left,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    if window.is_visible().unwrap_or(false) {
                        let _ = window.hide();
                    } else {
                        let _ = window.show();
                        let _ = window.unminimize();
                        let _ = window.set_focus();
                    }
                }
            }
        })
        .build(app)?;

    Ok(())
}

/// Generate a 32x32 orange "K" icon as RGBA byte data
fn create_tray_icon_rgba() -> Vec<u8> {
    const SIZE: u32 = 32;
    let total_pixels = (SIZE * SIZE) as usize;
    let mut data = vec![0u8; total_pixels * 4];

    // Orange: #FF9800
    let (r, g, b): (u8, u8, u8) = (0xFF, 0x98, 0x00);

    for y in 0..SIZE {
        for x in 0..SIZE {
            let idx = ((y * SIZE + x) * 4) as usize;

            // Circular background
            let cx = x as f32 - 15.5;
            let cy = y as f32 - 15.5;
            let dist = (cx * cx + cy * cy).sqrt();

            if dist < 14.0 {
                data[idx] = r;
                data[idx + 1] = g;
                data[idx + 2] = b;
                data[idx + 3] = 255;

                // "K" letter in white
                let in_k = (x >= 9 && x <= 12) // Vertical bar
                    || (x >= 13 && x <= 22 && {
                        let ky = y as i32 - 16;
                        let kx = x as i32 - 13;
                        (ky - kx).abs() <= 2 || (ky + kx).abs() <= 2
                    });

                if in_k && y >= 7 && y <= 25 {
                    data[idx] = 255;
                    data[idx + 1] = 255;
                    data[idx + 2] = 255;
                }
            }
        }
    }

    data
}
