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

import cv2
import time
import os
import logging
from datetime import datetime
from threading import Thread, Event
import numpy as np

from config import CAMERA_CONFIG, STORAGE_CONFIG, APP_CONFIG

class Camera:
    """360度カメラのキャプチャと録画を管理するクラス"""
    
    def __init__(self, sync_manager=None):
        """
        カメラクラスの初期化
        
        Args:
            sync_manager: 同期マネージャのインスタンス（オプション）
        """
        self.logger = logging.getLogger('Camera')
        self.config = CAMERA_CONFIG
        self.storage_config = STORAGE_CONFIG
        self.app_config = APP_CONFIG
        
        # カメラキャプチャの初期化
        self.device_id = self.config['device_id']
        self.cap = None
        self.frame = None
        self.running = False
        self.recording = False
        self.writer = None
        self.frame_count = 0
        self.start_time = None
        self.current_video_path = None
        self.sync_manager = sync_manager
        
        # スレッド関連
        self.capture_thread = None
        self.stop_event = Event()
        
        # 保存ディレクトリの初期化
        self._init_directories()
    
    def _init_directories(self):
        """保存ディレクトリの初期化"""
        base_path = self.storage_config['base_path']
        video_dir = os.path.join(base_path, self.storage_config['video_dir'])
        photo_dir = os.path.join(base_path, self.storage_config['photo_dir'])
        
        for directory in [base_path, video_dir, photo_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                self.logger.info(f"ディレクトリを作成しました: {directory}")
    
    def open(self):
        """カメラを開く"""
        try:
            self.cap = cv2.VideoCapture(self.device_id)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['width'])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['height'])
            self.cap.set(cv2.CAP_PROP_FPS, self.config['fps'])
            
            if not self.cap.isOpened():
                self.logger.error(f"カメラID {self.device_id} を開けませんでした")
                return False
            
            actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.logger.info(f"カメラを開きました: {actual_width}x{actual_height} @ {actual_fps}fps")
            return True
        except Exception as e:
            self.logger.error(f"カメラ初期化エラー: {str(e)}")
            return False
    
    def start(self):
        """カメラのキャプチャを開始"""
        if self.running:
            self.logger.warning("カメラは既に実行中です")
            return
        
        if not self.cap or not self.cap.isOpened():
            if not self.open():
                return
        
        self.running = True
        self.stop_event.clear()
        self.capture_thread = Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        self.logger.info("カメラキャプチャを開始しました")
    
    def stop(self):
        """カメラのキャプチャを停止"""
        self.stop_event.set()
        if self.recording:
            self.stop_recording()
        
        if self.capture_thread:
            self.capture_thread.join(timeout=3.0)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.running = False
        self.logger.info("カメラキャプチャを停止しました")
    
    def _capture_loop(self):
        """カメラからのフレーム取得ループ"""
        last_frame_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                ret, frame = self.cap.read()
                current_time = time.time()
                
                if not ret:
                    self.logger.warning("フレーム取得に失敗しました")
                    time.sleep(0.1)
                    continue
                
                self.frame = frame
                self.frame_count += 1
                
                # タイムスタンプを画像に追加
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                
                # PPSの同期情報があれば追加
                if self.sync_manager and self.app_config['enable_pps_sync']:
                    pps_info = self.sync_manager.get_last_pps_time()
                    if pps_info:
                        cv2.putText(
                            self.frame,
                            f"PPS: {pps_info}",
                            (10, 70),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 0),
                            2
                        )
                
                # タイムスタンプを追加
                cv2.putText(
                    self.frame,
                    timestamp,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )
                
                if self.recording and self.writer:
                    self.writer.write(self.frame)
                    
                # フレームレート調整
                delay = 1.0 / self.config['fps'] - (current_time - last_frame_time)
                if delay > 0:
                    time.sleep(delay)
                last_frame_time = time.time()
                
            except Exception as e:
                self.logger.error(f"キャプチャループエラー: {str(e)}")
                time.sleep(0.5)
    
    def start_recording(self):
        """録画開始"""
        if self.recording:
            self.logger.warning("既に録画中です")
            return
        
        if not self.running:
            self.logger.warning("カメラが開始されていないため、録画できません")
            return
        
        try:
            # 新しいビデオファイルのパスを作成
            timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
            video_filename = f"360cam_{timestamp}{self.config['extension']}"
            
            if self.storage_config['use_timestamp_subdir']:
                subdir = datetime.now().strftime("%Y%m%d")
                video_dir = os.path.join(
                    self.storage_config['base_path'],
                    self.storage_config['video_dir'],
                    subdir
                )
                if not os.path.exists(video_dir):
                    os.makedirs(video_dir)
            else:
                video_dir = os.path.join(
                    self.storage_config['base_path'],
                    self.storage_config['video_dir']
                )
            
            self.current_video_path = os.path.join(video_dir, video_filename)
            
            # ビデオライターの初期化
            fourcc = cv2.VideoWriter_fourcc(*self.config['codec'])
            self.writer = cv2.VideoWriter(
                self.current_video_path,
                fourcc,
                self.config['fps'],
                (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            )
            
            if not self.writer.isOpened():
                self.logger.error(f"ビデオライターを開けませんでした: {self.current_video_path}")
                return
            
            self.recording = True
            self.start_time = datetime.now()
            self.frame_count = 0
            
            self.logger.info(f"録画を開始しました: {self.current_video_path}")
            
            # 同期マネージャに録画開始を通知
            if self.sync_manager:
                self.sync_manager.register_recording_start(self.current_video_path, self.start_time)
                
        except Exception as e:
            self.logger.error(f"録画開始エラー: {str(e)}")
    
    def stop_recording(self):
        """録画停止"""
        if not self.recording:
            self.logger.warning("録画中ではありません")
            return
        
        try:
            if self.writer:
                self.writer.release()
                self.writer = None
            
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            self.logger.info(f"録画を停止しました: {self.current_video_path} (時間: {duration:.2f}秒, フレーム: {self.frame_count})")
            
            # 同期マネージャに録画終了を通知
            if self.sync_manager:
                self.sync_manager.register_recording_stop(self.current_video_path, end_time)
            
            self.recording = False
        except Exception as e:
            self.logger.error(f"録画停止エラー: {str(e)}")
    
    def capture_photo(self):
        """写真を撮影"""
        if not self.running or self.frame is None:
            self.logger.warning("カメラが開始されていないか、フレームがありません")
            return None
        
        try:
            timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
            photo_filename = f"360cam_{timestamp}{self.config['photo_extension']}"
            
            if self.storage_config['use_timestamp_subdir']:
                subdir = datetime.now().strftime("%Y%m%d")
                photo_dir = os.path.join(
                    self.storage_config['base_path'],
                    self.storage_config['photo_dir'],
                    subdir
                )
                if not os.path.exists(photo_dir):
                    os.makedirs(photo_dir)
            else:
                photo_dir = os.path.join(
                    self.storage_config['base_path'],
                    self.storage_config['photo_dir']
                )
            
            photo_path = os.path.join(photo_dir, photo_filename)
            cv2.imwrite(photo_path, self.frame)
            self.logger.info(f"写真を保存しました: {photo_path}")
            
            # 同期マネージャに写真撮影を通知
            if self.sync_manager:
                self.sync_manager.register_photo_capture(photo_path, datetime.now())
            
            return photo_path
        except Exception as e:
            self.logger.error(f"写真撮影エラー: {str(e)}")
            return None
    
    def get_preview_frame(self):
        """プレビュー用のフレームを取得"""
        if self.frame is None:
            return None
        
        try:
            # リサイズ
            preview_width = self.config['preview_width']
            preview_height = self.config['preview_height']
            preview_frame = cv2.resize(self.frame, (preview_width, preview_height))
            return preview_frame
        except Exception as e:
            self.logger.error(f"プレビューフレーム取得エラー: {str(e)}")
            return None
