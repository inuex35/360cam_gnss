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
import subprocess
from datetime import datetime
from threading import Thread, Event
import numpy as np
import picamera
from picamera import PiCamera
import io

from config import CAMERA_CONFIG, STORAGE_CONFIG, APP_CONFIG

class Camera:
    """Class for managing stereoscopic/360-degree camera capture and recording using Raspberry Pi Camera Module"""
    
    def __init__(self, sync_manager=None):
        """
        Initialize the Camera class
        
        Args:
            sync_manager: Instance of sync manager (optional)
        """
        self.logger = logging.getLogger('Camera')
        self.config = CAMERA_CONFIG
        self.storage_config = STORAGE_CONFIG
        self.app_config = APP_CONFIG
        
        # Camera variables
        self.camera = None
        self.frame = None
        self.running = False
        self.recording = False
        self.h264_output = None
        self.frame_count = 0
        self.start_time = None
        self.current_video_path = None
        self.h264_path = None
        self.sync_manager = sync_manager
        
        # Thread-related
        self.capture_thread = None
        self.stop_event = Event()
        
        # Initialize storage directories
        self._init_directories()
    
    def _init_directories(self):
        """Initialize storage directories"""
        base_path = self.storage_config['base_path']
        video_dir = os.path.join(base_path, self.storage_config['video_dir'])
        photo_dir = os.path.join(base_path, self.storage_config['photo_dir'])
        
        for directory in [base_path, video_dir, photo_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                self.logger.info(f"Created directory: {directory}")
    
    def open(self):
        """Open camera"""
        try:
            # Initialize the PiCamera
            self.camera = PiCamera(
                stereo_mode='side-by-side',
                stereo_decimate=False
            )
            self.camera.resolution = (self.config['width'], self.config['height'])
            self.camera.framerate = self.config['fps']
            
            # Give camera some time to initialize
            time.sleep(2)
            
            self.logger.info(f"Opened Pi Camera in stereo mode: {self.config['width']}x{self.config['height']} @ {self.config['fps']}fps")
            return True
        except Exception as e:
            self.logger.error(f"Camera initialization error: {str(e)}")
            return False
    
    def start(self):
        """Start camera capture"""
        if self.running:
            self.logger.warning("Camera is already running")
            return
        
        if not self.camera:
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
        
        if self.camera:
            self.camera.close()
            self.camera = None
        
        self.running = False
        self.logger.info("Stopped camera capture")
    
    def _capture_loop(self):
        """Frame capture loop from camera"""
        stream = io.BytesIO()
        
        try:
            for _ in self.camera.capture_continuous(stream, format='jpeg', use_video_port=True):
                if self.stop_event.is_set():
                    break
                
                # Reset stream position
                stream.seek(0)
                
                # Convert to numpy array
                data = np.frombuffer(stream.getvalue(), dtype=np.uint8)
                self.frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
                
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
                
                self.frame_count += 1
                
                # Reset stream for next capture
                stream.seek(0)
                stream.truncate()
                
                # Small delay to match framerate
                time.sleep(1.0 / self.config['fps'])
        
        except Exception as e:
            self.logger.error(f"Capture loop error: {str(e)}")
    
    def start_recording(self):
        """Start recording"""
        if self.recording:
            self.logger.warning("Already recording")
            return
        
        if not self.running:
            self.logger.warning("Camera not started, cannot record")
            return
        
        try:
            # Create path for new video file
            timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
            video_filename = f"stereo_{timestamp}.mp4"
            h264_filename = f"stereo_{timestamp}.h264"
            
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
            self.h264_path = os.path.join(video_dir, h264_filename)
            
            # Start recording using raspivid-like settings
            self.camera.start_recording(self.h264_path, format='h264')
            
            self.recording = True
            self.start_time = datetime.now()
            self.frame_count = 0
            
            self.logger.info(f"Started recording: {self.h264_path}")
            
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
            # Stop recording
            self.camera.stop_recording()
            
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            self.logger.info(f"Stopped recording: {self.h264_path} (duration: {duration:.2f}s)")
            
            # Convert h264 to mp4 using MP4Box
            try:
                self.logger.info(f"Converting {self.h264_path} to {self.current_video_path}")
                subprocess.run(['MP4Box', '-add', self.h264_path, self.current_video_path], check=True)
                self.logger.info(f"Conversion complete: {self.current_video_path}")
                
                # Remove h264 file after successful conversion
                os.remove(self.h264_path)
            except Exception as e:
                self.logger.error(f"Error converting video: {str(e)}")
            
            # Notify sync manager of recording stop
            if self.sync_manager:
                self.sync_manager.register_recording_stop(self.current_video_path, end_time)
            
            self.recording = False
        except Exception as e:
            self.logger.error(f"Stop recording error: {str(e)}")
    
    def capture_photo(self):
        """Capture a photo"""
        if not self.running:
            self.logger.warning("Camera not started")
            return None
        
        try:
            timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
            photo_filename = f"stereo_{timestamp}{self.config['photo_extension']}"
            
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
            
            # Capture directly to file
            self.camera.capture(photo_path, format='jpeg')
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
