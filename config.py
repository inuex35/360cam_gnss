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

# カメラ設定
CAMERA_CONFIG = {
    'device_id': 0,                   # カメラデバイスID（通常は0）
    'width': 1920,                    # 画像幅
    'height': 1080,                   # 画像高さ
    'fps': 30,                        # フレームレート
    'codec': 'XVID',                  # 動画コーデック
    'extension': '.avi',              # 動画ファイル拡張子
    'capture_interval': 0,            # 連続撮影時の撮影間隔（秒）、0は連続録画
    'photo_extension': '.jpg',        # 写真ファイル拡張子
    'preview_width': 800,             # プレビュー画面の幅
    'preview_height': 450             # プレビュー画面の高さ
}

# GNSS設定
GNSS_CONFIG = {
    'port': '/dev/ttyAMA0',           # シリアルポート
    'baudrate': 9600,                 # ボーレート
    'parity': 'N',                    # パリティ
    'stopbits': 1,                    # ストップビット
    'timeout': 1,                     # タイムアウト（秒）
    'log_interval': 1,                # GNSSデータのログ間隔（秒）
    'gpx_extension': '.gpx',          # GPXファイル拡張子
    'nmea_extension': '.nmea',        # NMEAファイル拡張子
    'pps_gpio_pin': 18                # PPS信号が接続されるGPIOピン番号
}

# ファイル保存設定
STORAGE_CONFIG = {
    'base_path': './data',            # データ保存のベースパス
    'video_dir': 'videos',            # 動画保存ディレクトリ
    'photo_dir': 'photos',            # 写真保存ディレクトリ
    'gnss_dir': 'gnss',               # GNSSデータ保存ディレクトリ
    'sync_dir': 'sync',               # 同期情報保存ディレクトリ
    'timestamp_format': '%Y%m%d_%H%M%S',  # タイムスタンプフォーマット
    'use_timestamp_subdir': True      # 日付ごとのサブディレクトリを作成するか
}

# アプリケーション全般設定
APP_CONFIG = {
    'log_level': 'INFO',              # ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    'enable_preview': True,           # カメラプレビューを有効にするか
    'save_on_exit': True,             # 終了時にデータを保存するか
    'enable_pps_sync': True,          # PPS同期を有効にするか
    'exit_key': 'q'                   # 終了キー
}
