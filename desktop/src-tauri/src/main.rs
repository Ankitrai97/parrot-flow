#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{menu::{Menu, MenuItem}, tray::TrayIconBuilder, Manager};

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let show = MenuItem::with_id(app, "show", "Open Parrot Flow", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            TrayIconBuilder::new().menu(&menu).on_menu_event(|app, event| match event.id.as_ref() {
                "show" => { if let Some(window) = app.get_webview_window("main") { let _ = window.show(); let _ = window.set_focus(); } }
                "quit" => app.exit(0),
                _ => {}
            }).build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run Parrot Flow desktop application");
}
