#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2025 inuex35
#
# This file is part of 360cam_gnss.
#
# 360cam_gnss is free software: you can redistribute it 
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of the 
# License, or (at your option) any later version.
#

# Camera settings
CAMERA_CONFIG = {
    'width': 1280,                    # Image width (should be divisible by 32)
    'height': 480,                    # Image height (should be divisible by 16)
    'fps': 30,                        # Frame rate
    'codec': 'h264',                  # Video codec
    'extension': '.mp4',              # Video file extension
    'capture_interval': 0,            # Capture interval in seconds for time-lapse (0 for continuous recording)
    'photo_extension': '.jpg',        # Photo file extension
    'preview_width': 1024,            # Preview window width
    'preview_height': 384,            # Preview window height
    'display_mode': 'side_by_side',   # Initial display mode: 'side_by_side', 'left', 'right', 'anaglyph'
    'delete_h264_after_conversion': True,  # Delete .h264 files after conversion to .mp4
    'fullscreen': False,              # Start in fullscreen mode
    'window_title': '360cam GNSS - Stereoscopic View'  # Window title
}

# Dual fisheye camera settings - 220度超広角カメラ用に最適化
DUAL_FISHEYE_CONFIG = {
    'width': 1440,                    # 画像の幅
    'height': 720,                    # 画像の高さ
    'fps': 30,                        # フレームレート
    'codec': 'h264',                  # ビデオコーデック
    'extension': '.mp4',              # ビデオファイル拡張子
    'photo_extension': '.jpg',        # 写真ファイル拡張子
    'preview_width': 1024,            # プレビュー幅
    'preview_height': 512,            # プレビュー高さ
    'display_mode': 'equirectangular', # 初期表示モード: 'fisheye', 'equirectangular'
    'delete_h264_after_conversion': True,  # 変換後h264ファイルを削除
    'window_title': '360cam GNSS - Dual Fisheye',  # ウィンドウタイトル
    
    # 220度超広角カメラ用のフィッシュアイキャリブレーションパラメータ
    'cx1': 360,                       # 左フィッシュアイの中心X座標
    'cy1': 360,                       # 左フィッシュアイの中心Y座標
    'cx2': 1080,                      # 右フィッシュアイの中心X座標
    'cy2': 360,                       # 右フィッシュアイの中心Y座標
    'radius_scale': 1.2,              # フィッシュアイ半径スケール（220度対応に拡大）
    'equ_height_ratio': 0.5,          # 全天球出力の高さ比率
    'field_of_view': 220,             # カメラの視野角（度）
    'fisheye_overlap': 10,            # フィッシュアイ画像の重複領域（度）
}

# GNSS settings
GNSS_CONFIG = {
    'port': '/dev/ttyAMA0',           # Serial port
    'baudrate': 9600,                 # Baud rate
    'parity': 'N',                    # Parity
    'stopbits': 1,                    # Stop bits
    'timeout': 1,                     # Timeout in seconds
    'log_interval': 1,                # GNSS data logging interval in seconds
    'gpx_extension': '.gpx',          # GPX file extension
    'nmea_extension': '.nmea',        # NMEA file extension
    'pps_gpio_pin': 18                # GPIO pin number for PPS signal
}

# Storage settings
STORAGE_CONFIG = {
    'base_path': './data',            # Base path for data storage
    'video_dir': 'videos',            # Directory for video storage
    'photo_dir': 'photos',            # Directory for photo storage
    'gnss_dir': 'gnss',               # Directory for GNSS data storage
    'sync_dir': 'sync',               # Directory for synchronization info storage
    'timestamp_format': '%Y%m%d_%H%M%S',  # Timestamp format
    'use_timestamp_subdir': True      # Create subdirectories by date
}

# Application settings
APP_CONFIG = {
    'log_level': 'INFO',              # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    'enable_preview': True,           # Enable camera preview
    'save_on_exit': True,             # Save data on exit
    'enable_pps_sync': True,          # Enable PPS synchronization
    'exit_key': 'q',                  # Exit key
    'display_mode_key': 'd',          # Toggle display mode key
    'show_fps': True,                 # Show FPS counter in preview
    'show_help': True                 # Show keyboard shortcuts in preview
}
