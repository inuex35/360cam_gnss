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
    """Class for managing stereoscopic camera with real-time display and recording capabilities"""
    
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
        self.current_video_path = None
        self.h264_path = None
        self.sync_manager = sync_manager
        self.start_time = None
        
        # Display options
        self.display_mode = self.config.get('display_mode', 'side_by_side')  # 'side_by_side', 'left', 'right', 'anaglyph'
        
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
            # Initialize the PiCamera with stereo mode
            self.camera = picamera.PiCamera(
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
        """Frame capture loop from camera for real-time display"""
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
                
                # Add timestamp and other info to frame
                self._add_overlay_info(self.frame)
                
                # Reset stream for next capture
                stream.seek(0)
                stream.truncate()
                
                # Small delay to match framerate
                time.sleep(0.01)  # Adjusted for more responsive real-time display
        
        except Exception as e:
            self.logger.error(f"Capture loop error: {str(e)}")
    
    def _add_overlay_info(self, frame):
        """Add information overlay to frame"""
        if frame is None:
            return
            
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(
            frame,
            timestamp,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        # Add recording indicator if recording
        if self.recording:
            cv2.putText(
                frame,
                "REC",
                (frame.shape[1] - 80, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )
            
            # Add red circle for recording indicator
            cv2.circle(
                frame,
                (frame.shape[1] - 100, 25),
                10,
                (0, 0, 255),
                -1
            )
                
        # Add PPS sync info if available
        if self.sync_manager and self.app_config['enable_pps_sync']:
            pps_info = self.sync_manager.get_last_pps_time()
            if pps_info:
                cv2.putText(
                    frame,
                    f"PPS: {pps_info}",
                    (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )
    
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
            
            self.h264_path = os.path.join(video_dir, h264_filename)
            self.current_video_path = self.h264_path.replace('.h264', '.mp4')
            
            # Start recording directly to h264 file
            self.camera.start_recording(self.h264_path)
            
            self.recording = True
            self.start_time = datetime.now()
            
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
            
            # Convert h264 to mp4 using MP4Box in a separate thread to avoid blocking UI
            converter_thread = Thread(target=self._convert_video)
            converter_thread.daemon = True
            converter_thread.start()
            
            # Notify sync manager of recording stop
            if self.sync_manager:
                self.sync_manager.register_recording_stop(self.current_video_path, end_time)
            
            self.recording = False
        except Exception as e:
            self.logger.error(f"Stop recording error: {str(e)}")
    
    def _convert_video(self):
        """Convert h264 to mp4 in a separate thread"""
        try:
            self.logger.info(f"Converting {self.h264_path} to {self.current_video_path}")
            subprocess.run(['MP4Box', '-add', self.h264_path, self.current_video_path], check=True)
            self.logger.info(f"Conversion complete: {self.current_video_path}")
            
            # Remove h264 file after successful conversion if configured
            if self.config.get('delete_h264_after_conversion', True):
                os.remove(self.h264_path)
        except Exception as e:
            self.logger.error(f"Error converting video: {str(e)}")
    
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
            
            # Capture directly to file using picamera
            self.camera.capture(photo_path)
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
            # Create a copy to avoid modifying the original frame
            frame = self.frame.copy()
            
            # Apply display mode transformations
            frame = self._apply_display_mode(frame)
            
            # Resize if needed
            if self.config['preview_width'] > 0 and self.config['preview_height'] > 0:
                frame = cv2.resize(frame, (self.config['preview_width'], self.config['preview_height']))
                
            return frame
        except Exception as e:
            self.logger.error(f"Preview frame error: {str(e)}")
            return None
    
    def _apply_display_mode(self, frame):
        """Apply the selected display mode to the frame"""
        if frame is None:
            return None
            
        # Get frame dimensions
        height, width = frame.shape[:2]
        half_width = width // 2
        
        if self.display_mode == 'side_by_side':
            # Already in side-by-side format, no change needed
            return frame
            
        elif self.display_mode == 'left':
            # Extract left image
            return frame[:, :half_width].copy()
            
        elif self.display_mode == 'right':
            # Extract right image
            return frame[:, half_width:].copy()
            
        elif self.display_mode == 'anaglyph':
            # Create red-cyan anaglyph for 3D viewing with red-cyan glasses
            left = frame[:, :half_width].copy()
            right = frame[:, half_width:].copy()
            
            # Resize right image to match left if needed
            if left.shape[1] != right.shape[1]:
                right = cv2.resize(right, (left.shape[1], left.shape[0]))
            
            # Create anaglyph
            anaglyph = np.zeros_like(left)
            
            # Left image - red channel
            anaglyph[:, :, 2] = left[:, :, 2]  # Red channel
            
            # Right image - green and blue channels
            anaglyph[:, :, 0] = right[:, :, 0]  # Blue channel
            anaglyph[:, :, 1] = right[:, :, 1]  # Green channel
            
            return anaglyph
        
        else:
            # Default to side-by-side
            return frame
    
    def set_display_mode(self, mode):
        """Set the display mode"""
        valid_modes = ['side_by_side', 'left', 'right', 'anaglyph']
        
        if mode in valid_modes:
            self.display_mode = mode
            self.logger.info(f"Display mode set to: {mode}")
            return True
        else:
            self.logger.warning(f"Invalid display mode: {mode}. Valid modes are: {valid_modes}")
            return False
    
    def toggle_display_mode(self):
        """Toggle through available display modes"""
        modes = ['side_by_side', 'left', 'right', 'anaglyph']
        current_index = modes.index(self.display_mode) if self.display_mode in modes else 0
        next_index = (current_index + 1) % len(modes)
        self.display_mode = modes[next_index]
        self.logger.info(f"Display mode toggled to: {self.display_mode}")
        return self.display_mode
