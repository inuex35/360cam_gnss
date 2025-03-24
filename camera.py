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
    """Class for managing 360-degree camera capture and recording"""
    
    def __init__(self, sync_manager=None, session_dir=None):
        """
        Initialize the Camera class
        
        Args:
            sync_manager: Instance of sync manager (optional)
            session_dir: Session directory for storing data
        """
        self.logger = logging.getLogger('Camera')
        self.config = CAMERA_CONFIG
        self.storage_config = STORAGE_CONFIG
        self.app_config = APP_CONFIG
        
        # Initialize camera capture
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
        self.session_dir = session_dir
        
        # Thread-related
        self.capture_thread = None
        self.stop_event = Event()
        
        # Initialize storage directories
        self._init_directories()
    
    def _init_directories(self):
        """Initialize storage directories"""
        base_path = self.storage_config['base_path']
        if not os.path.exists(base_path):
            os.makedirs(base_path)
            self.logger.info(f"Created directory: {base_path}")
        
        # If session directory is provided, use it
        if self.session_dir:
            if not os.path.exists(self.session_dir):
                os.makedirs(self.session_dir)
                self.logger.info(f"Created session directory: {self.session_dir}")
    
    def open(self):
        """Open camera"""
        try:
            self.cap = cv2.VideoCapture(self.device_id)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['width'])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['height'])
            self.cap.set(cv2.CAP_PROP_FPS, self.config['fps'])
            
            if not self.cap.isOpened():
                self.logger.error(f"Could not open camera ID {self.device_id}")
                return False
            
            actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.logger.info(f"Opened camera: {actual_width}x{actual_height} @ {actual_fps}fps")
            return True
        except Exception as e:
            self.logger.error(f"Camera initialization error: {str(e)}")
            return False
    
    def start(self):
        """Start camera capture"""
        if self.running:
            self.logger.warning("Camera is already running")
            return
        
        if not self.cap or not self.cap.isOpened():
            if not self.open():
                return
        
        self.running = True
        self.stop_event.clear()
        self.capture_thread = Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        self.logger.info("Started camera capture")
    
    def stop(self):
        """Stop camera capture"""
        self.stop_event.set()
        if self.recording:
            self.stop_recording()
        
        if self.capture_thread:
            self.capture_thread.join(timeout=3.0)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.running = False
        self.logger.info("Stopped camera capture")
    
    def _capture_loop(self):
        """Frame capture loop from camera"""
        last_frame_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                ret, frame = self.cap.read()
                current_time = time.time()
                
                if not ret:
                    self.logger.warning("Failed to get frame")
                    time.sleep(0.1)
                    continue
                
                self.frame = frame
                self.frame_count += 1
                
                # Add timestamp to image
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                
                # Add PPS sync info if available
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
                
                # Add timestamp
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
                    
                # Frame rate adjustment
                delay = 1.0 / self.config['fps'] - (current_time - last_frame_time)
                if delay > 0:
                    time.sleep(delay)
                last_frame_time = time.time()
                
            except Exception as e:
                self.logger.error(f"Capture loop error: {str(e)}")
                time.sleep(0.5)
    
    def start_recording(self):
        """Start recording"""
        if self.recording:
            self.logger.warning("Already recording")
            return
        
        if not self.running:
            self.logger.warning("Camera not started, cannot record")
            return
        
        try:
            # Create session directory if it doesn't exist yet
            if not self.session_dir:
                timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
                self.session_dir = os.path.join(
                    self.storage_config['base_path'],
                    timestamp
                )
                if not os.path.exists(self.session_dir):
                    os.makedirs(self.session_dir)
                    self.logger.info(f"Created session directory: {self.session_dir}")
                
                # Notify sync manager of new session directory
                if self.sync_manager:
                    self.sync_manager.set_session_dir(self.session_dir)
            
            # Create video filename
            video_filename = f"{self.storage_config['filename_prefix']}_video{self.config['extension']}"
            self.current_video_path = os.path.join(self.session_dir, video_filename)
            
            # Initialize video writer
            fourcc = cv2.VideoWriter_fourcc(*self.config['codec'])
            self.writer = cv2.VideoWriter(
                self.current_video_path,
                fourcc,
                self.config['fps'],
                (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            )
            
            if not self.writer.isOpened():
                self.logger.error(f"Could not open video writer: {self.current_video_path}")
                return
            
            self.recording = True
            self.start_time = datetime.now()
            self.frame_count = 0
            
            self.logger.info(f"Started recording: {self.current_video_path}")
            
            # Notify sync manager of recording start
            if self.sync_manager:
                self.sync_manager.register_recording_start(self.current_video_path, self.start_time)
                
        except Exception as e:
            self.logger.error(f"Start recording error: {str(e)}")
    
    def stop_recording(self):
        """Stop recording"""
        if not self.recording:
            self.logger.warning("Not recording")
            return
        
        try:
            if self.writer:
                self.writer.release()
                self.writer = None
            
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            self.logger.info(f"Stopped recording: {self.current_video_path} (duration: {duration:.2f}s, frames: {self.frame_count})")
            
            # Notify sync manager of recording stop
            if self.sync_manager:
                self.sync_manager.register_recording_stop(self.current_video_path, end_time)
            
            self.recording = False
        except Exception as e:
            self.logger.error(f"Stop recording error: {str(e)}")
    
    def capture_photo(self):
        """Capture a photo"""
        if not self.running or self.frame is None:
            self.logger.warning("Camera not started or no frame available")
            return None
        
        try:
            # Create session directory if it doesn't exist yet
            if not self.session_dir:
                timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
                self.session_dir = os.path.join(
                    self.storage_config['base_path'],
                    timestamp
                )
                if not os.path.exists(self.session_dir):
                    os.makedirs(self.session_dir)
                    self.logger.info(f"Created session directory: {self.session_dir}")
                
                # Notify sync manager of new session directory
                if self.sync_manager:
                    self.sync_manager.set_session_dir(self.session_dir)
            
            # Create unique photo filename with timestamp
            timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
            photo_filename = f"{self.storage_config['filename_prefix']}_photo_{timestamp}{self.config['photo_extension']}"
            photo_path = os.path.join(self.session_dir, photo_filename)
            
            # Save photo
            cv2.imwrite(photo_path, self.frame)
            self.logger.info(f"Saved photo: {photo_path}")
            
            # Notify sync manager of photo capture
            if self.sync_manager:
                self.sync_manager.register_photo_capture(photo_path, datetime.now())
            
            return photo_path
        except Exception as e:
            self.logger.error(f"Photo capture error: {str(e)}")
            return None
    
    def get_preview_frame(self):
        """Get a frame for preview"""
        if self.frame is None:
            return None
        
        try:
            # Resize
            preview_width = self.config['preview_width']
            preview_height = self.config['preview_height']
            preview_frame = cv2.resize(self.frame, (preview_width, preview_height))
            return preview_frame
        except Exception as e:
            self.logger.error(f"Preview frame error: {str(e)}")
            return None
    
    def get_session_dir(self):
        """Get the current session directory"""
        return self.session_dir
