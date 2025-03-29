#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Flet app for controlling the 360 camera on Raspberry Pi

import flet as ft
import time
import threading
import os
import base64
import io
import cv2
import numpy as np
from datetime import datetime
from camera import Camera

# Global variables
camera = None
recording = False
preview_thread = None
stop_preview = False
frame_data = None
frame_lock = threading.Lock()

def main(page: ft.Page):
    page.title = "360° ステレオカメラコントロール"
    page.padding = 20
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1000
    page.window_height = 700
    
    # Status text
    status_text = ft.Text("カメラ: 停止中", size=16)
    recording_status = ft.Text("録画: 停止中", size=16, color=ft.colors.RED)
    
    # Camera preview
    preview_image = ft.Image(
        width=800,
        height=300,
        fit=ft.ImageFit.CONTAIN,
        border_radius=10,
    )
    
    # Function to convert OpenCV frame to Flet compatible image
    def convert_frame_to_img(frame):
        if frame is None:
            return None
        
        # Resize for preview
        frame = cv2.resize(frame, (800, 300))
        
        # Convert to bytes
        _, buffer = cv2.imencode('.jpg', frame)
        img_bytes = io.BytesIO(buffer)
        
        # Convert to base64
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{img_base64}"
    
    # Preview update thread
    def update_preview():
        global stop_preview, frame_data
        
        while not stop_preview:
            if camera and camera.running:
                frame = camera.get_preview_frame()
                
                if frame is not None:
                    with frame_lock:
                        frame_data = convert_frame_to_img(frame)
                    
                    # Update UI from main thread
                    page.invoke_async(update_preview_ui)
            
            time.sleep(0.1)  # Update at ~10 FPS to reduce CPU load
    
    # Update preview UI
    def update_preview_ui():
        global frame_data
        with frame_lock:
            if frame_data:
                preview_image.src = frame_data
                page.update(preview_image)
    
    # Start camera
    def start_camera(e):
        global camera, preview_thread, stop_preview
        
        if camera is None:
            camera = Camera()
        
        if not camera.running:
            if camera.open():
                camera.start()
                status_text.value = "カメラ: 動作中"
                status_text.color = ft.colors.GREEN
                start_btn.disabled = True
                stop_btn.disabled = False
                toggle_recording_btn.disabled = False
                capture_photo_btn.disabled = False
                display_mode_btn.disabled = False
                
                # Start preview thread
                stop_preview = False
                preview_thread = threading.Thread(target=update_preview)
                preview_thread.daemon = True
                preview_thread.start()
            else:
                status_text.value = "カメラ: 初期化エラー"
                status_text.color = ft.colors.RED
        
        page.update()
    
    # Stop camera
    def stop_camera(e):
        global camera, stop_preview, recording
        
        if camera and camera.running:
            # Stop recording if active
            if recording:
                camera.stop_recording()
                recording = False
                recording_status.value = "録画: 停止中"
                recording_status.color = ft.colors.RED
                toggle_recording_btn.text = "録画開始"
                toggle_recording_btn.bgcolor = ft.colors.RED
            
            # Stop preview thread
            stop_preview = True
            if preview_thread:
                preview_thread.join(timeout=1.0)
            
            # Stop camera
            camera.stop()
            status_text.value = "カメラ: 停止中"
            status_text.color = ft.colors.RED
            start_btn.disabled = False
            stop_btn.disabled = True
            toggle_recording_btn.disabled = True
            capture_photo_btn.disabled = True
            display_mode_btn.disabled = True
            
            # Clear preview
            preview_image.src = None
        
        page.update()
    
    # Toggle recording
    def toggle_recording(e):
        global camera, recording
        
        if camera and camera.running:
            if not recording:
                # Start recording
                camera.start_recording()
                recording = True
                recording_status.value = "録画: 録画中"
                recording_status.color = ft.colors.RED_ACCENT
                toggle_recording_btn.text = "録画停止"
                toggle_recording_btn.bgcolor = ft.colors.BLUE
            else:
                # Stop recording
                camera.stop_recording()
                recording = False
                recording_status.value = "録画: 停止中"
                recording_status.color = ft.colors.RED
                toggle_recording_btn.text = "録画開始"
                toggle_recording_btn.bgcolor = ft.colors.RED
                
                # Show where the video was saved
                if camera.current_video_path:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"ビデオを保存しました: {camera.current_video_path}"),
                        action="OK",
                    )
                    page.snack_bar.open = True
        
        page.update()
    
    # Capture photo
    def capture_photo(e):
        global camera
        
        if camera and camera.running:
            photo_path = camera.capture_photo()
            
            if photo_path:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"写真を保存しました: {photo_path}"),
                    action="OK",
                )
                page.snack_bar.open = True
                page.update()
    
    # Toggle display mode
    def toggle_display_mode(e):
        global camera
        
        if camera and camera.running:
            new_mode = camera.toggle_display_mode()
            display_mode_btn.text = f"表示モード: {get_display_mode_text(new_mode)}"
            page.update()
    
    # Get display mode text in Japanese
    def get_display_mode_text(mode):
        modes = {
            'side_by_side': '左右並列',
            'left': '左カメラ',
            'right': '右カメラ',
            'anaglyph': 'アナグリフ3D'
        }
        return modes.get(mode, mode)
    
    # Create buttons
    start_btn = ft.ElevatedButton(
        "カメラ起動",
        icon=ft.icons.VIDEOCAM,
        on_click=start_camera,
        style=ft.ButtonStyle(
            bgcolor=ft.colors.GREEN,
            color=ft.colors.WHITE,
        ),
        width=150,
    )
    
    stop_btn = ft.ElevatedButton(
        "カメラ停止",
        icon=ft.icons.VIDEOCAM_OFF,
        on_click=stop_camera,
        style=ft.ButtonStyle(
            bgcolor=ft.colors.RED,
            color=ft.colors.WHITE,
        ),
        disabled=True,
        width=150,
    )
    
    toggle_recording_btn = ft.ElevatedButton(
        "録画開始",
        icon=ft.icons.FIBER_MANUAL_RECORD,
        on_click=toggle_recording,
        style=ft.ButtonStyle(
            bgcolor=ft.colors.RED,
            color=ft.colors.WHITE,
        ),
        disabled=True,
        width=150,
    )
    
    capture_photo_btn = ft.ElevatedButton(
        "写真撮影",
        icon=ft.icons.CAMERA_ALT,
        on_click=capture_photo,
        style=ft.ButtonStyle(
            bgcolor=ft.colors.BLUE,
            color=ft.colors.WHITE,
        ),
        disabled=True,
        width=150,
    )
    
    display_mode_btn = ft.ElevatedButton(
        "表示モード: 左右並列",
        icon=ft.icons.VIEW_AGENDA,
        on_click=toggle_display_mode,
        style=ft.ButtonStyle(
            bgcolor=ft.colors.PURPLE,
            color=ft.colors.WHITE,
        ),
        disabled=True,
        width=200,
    )
    
    # Layout
    page.add(
        ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Text("360° ステレオカメラコントロール", size=24, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.CENTER),
                margin=10,
            ),
            ft.Container(
                content=ft.Row([
                    status_text,
                    ft.VerticalDivider(width=20),
                    recording_status,
                ]),
                margin=10,
            ),
            ft.Container(
                content=preview_image,
                alignment=ft.alignment.center,
                margin=10,
                padding=10,
                border=ft.border.all(2, ft.colors.BLUE_GREY_400),
                border_radius=10,
                bgcolor=ft.colors.BLACK,
            ),
            ft.Container(
                content=ft.Row([
                    start_btn,
                    stop_btn,
                    toggle_recording_btn,
                    capture_photo_btn,
                    display_mode_btn,
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                margin=20,
            ),
            ft.Container(
                content=ft.Text("ステータス:", weight=ft.FontWeight.BOLD),
                margin=ft.margin.only(left=10, top=20),
            ),
            ft.Container(
                content=ft.Text(
                    "- Fletアプリからステレオカメラを制御できます\n"
                    "- 録画したビデオは自動的にMP4に変換されます\n"
                    "- '表示モード'ボタンで左右のカメラ表示を切り替えられます",
                    size=14,
                ),
                margin=ft.margin.only(left=20, right=10),
            ),
        ])
    )
    
    # Cleanup on app close
    def on_close(e):
        global camera, stop_preview
        
        if camera and camera.running:
            # Stop preview thread
            stop_preview = True
            if preview_thread:
                preview_thread.join(timeout=1.0)
            
            # Stop recording if active
            if recording:
                camera.stop_recording()
            
            # Stop camera
            camera.stop()
        
        return True
    
    page.on_close = on_close

if __name__ == "__main__":
    ft.app(target=main)
