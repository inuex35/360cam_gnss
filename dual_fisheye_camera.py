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

from config import DUAL_FISHEYE_CONFIG, STORAGE_CONFIG, APP_CONFIG

class DualFisheyeCamera:
    """Class for managing dual fisheye camera with real-time equirectangular conversion and streaming"""
    
    def __init__(self, sync_manager=None):
        """
        Initialize the DualFisheyeCamera class
        
        Args:
            sync_manager: Instance of sync manager (optional)
        """
        self.logger = logging.getLogger('DualFisheyeCamera')
        self.config = DUAL_FISHEYE_CONFIG
        self.storage_config = STORAGE_CONFIG
        self.app_config = APP_CONFIG
        
        # Camera variables
        self.camera = None
        self.frame = None
        self.equirectangular_frame = None
        self.running = False
        self.recording = False
        self.current_video_path = None
        self.h264_path = None
        self.sync_manager = sync_manager
        self.start_time = None
        
        # Display options
        self.display_mode = self.config.get('display_mode', 'equirectangular')  # 'fisheye', 'equirectangular'
        
        # Thread-related
        self.capture_thread = None
        self.process_thread = None
        self.stop_event = Event()
        
        # Calibration
        self.init_calibration()
        
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
    
    def init_calibration(self):
        """Initialize calibration parameters for equirectangular conversion"""
        self.logger.info("Initializing dual fisheye calibration parameters")
        
        # Get calibration parameters from config
        self.fisheye_xmap = None
        self.fisheye_ymap = None
        
        # Lazy initialization - will be built the first time it's needed
        self.calibration_initialized = False
    
    def _create_fisheye_maps(self):
        """Create mapping for fisheye to equirectangular conversion"""
        # Only create maps if not already initialized
        if self.calibration_initialized:
            return
            
        # Get frame dimensions
        width = self.config['width']
        height = self.config['height']
        
        # Create maps
        self.logger.info(f"Creating fisheye mapping with dimensions {width}x{height}")
        
        # Create destination map
        equ_h = int(height * self.config.get('equ_height_ratio', 0.5))
        equ_w = width
        
        # Create empty maps for x and y coordinate mappings
        self.fisheye_xmap = np.zeros((equ_h, equ_w), np.float32)
        self.fisheye_ymap = np.zeros((equ_h, equ_w), np.float32)
        
        # Calculate center point for each fisheye lens
        cx1 = self.config.get('cx1', width // 4)  # Left fisheye center x
        cy1 = self.config.get('cy1', height // 2)  # Left fisheye center y
        cx2 = self.config.get('cx2', width * 3 // 4)  # Right fisheye center x
        cy2 = self.config.get('cy2', height // 2)  # Right fisheye center y
        
        # Calculate radius for fisheye lens
        radius = min(cx1, cy1) if cx1 < cx2 else min(width - cx2, cy2)
        radius = int(radius * self.config.get('radius_scale', 0.9))
        
        # Create maps
        for y in range(equ_h):
            for x in range(equ_w):
                # Convert equirectangular coordinates to spherical
                theta = (x / equ_w) * 2 * np.pi
                phi = (y / equ_h) * np.pi
                
                # Convert spherical to 3D Cartesian
                x3d = np.sin(phi) * np.cos(theta)
                y3d = np.sin(phi) * np.sin(theta)
                z3d = np.cos(phi)
                
                # Determine which fisheye to use based on theta
                # Front fisheye for -pi/2 to pi/2, rear fisheye for the rest
                if -np.pi/2 <= theta <= np.pi/2:
                    # Front fisheye (left in the dual fisheye image)
                    # Project 3D point to fisheye image
                    r = radius * np.sqrt(x3d*x3d + z3d*z3d) / (y3d + 1e-6)
                    angle = np.arctan2(z3d, x3d)
                    
                    # Map to image coordinates
                    self.fisheye_xmap[y, x] = cx1 + r * np.cos(angle)
                    self.fisheye_ymap[y, x] = cy1 + r * np.sin(angle)
                else:
                    # Rear fisheye (right in the dual fisheye image)
                    # Adjust 3D point for rear fisheye
                    x3d = -x3d
                    y3d = -y3d
                    
                    # Project 3D point to fisheye image
                    r = radius * np.sqrt(x3d*x3d + z3d*z3d) / (y3d + 1e-6)
                    angle = np.arctan2(z3d, x3d)
                    
                    # Map to image coordinates
                    self.fisheye_xmap[y, x] = cx2 + r * np.cos(angle)
                    self.fisheye_ymap[y, x] = cy2 + r * np.sin(angle)
        
        # Convert maps to correct format for remap
        self.fisheye_xmap = self.fisheye_xmap.astype(np.float32)
        self.fisheye_ymap = self.fisheye_ymap.astype(np.float32)
        
        self.calibration_initialized = True
        self.logger.info("Fisheye calibration maps created successfully")
    
    def open(self):
        """Open camera"""
        try:
            # Initialize the OpenCV VideoCapture
            camera_index = self.config.get('camera_index', 0)
            self.camera = cv2.VideoCapture(camera_index)
            
            # Configure camera
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['width'])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['height'])
            self.camera.set(cv2.CAP_PROP_FPS, self.config['fps'])
            
            # Check if camera opened successfully
            if not self.camera.isOpened():
                self.logger.error(f"Failed to open camera at index {camera_index}")
                return False
            
            # Give camera some time to initialize
            time.sleep(2)
            
            self.logger.info(f"Opened OpenCV camera: {self.config['width']}x{self.config['height']} @ {self.config['fps']}fps")
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
        
        # Start capture thread
        self.capture_thread = Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        # Start processing thread
        self.process_thread = Thread(target=self._process_loop)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        self.logger.info("Started dual fisheye camera capture")
    
    def stop(self):
        """Stop camera capture"""
        self.stop_event.set()
        if self.recording:
            self.stop_recording()
        
        if self.capture_thread:
            self.capture_thread.join(timeout=3.0)
        
        if self.process_thread:
            self.process_thread.join(timeout=3.0)
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        self.running = False
        self.logger.info("Stopped dual fisheye camera capture")
    
    def _capture_loop(self):
        """Frame capture loop from camera for real-time display"""
        try:
            while not self.stop_event.is_set():
                if self.camera and self.camera.isOpened():
                    # Get frame from camera
                    ret, frame = self.camera.read()
                    
                    if ret:
                        self.frame = frame
                        
                        # Add timestamp and other info to frame
                        self._add_overlay_info(self.frame)
                    else:
                        self.logger.warning("Failed to read frame from camera")
                
                # Small delay to match framerate
                time.sleep(0.01)
        
        except Exception as e:
            self.logger.error(f"Capture loop error: {str(e)}")
    
    def _process_loop(self):
        """Process captured frames for equirectangular conversion"""
        try:
            while not self.stop_event.is_set():
                if self.frame is not None:
                    # Convert to equirectangular if needed
                    if not self.calibration_initialized:
                        self._create_fisheye_maps()
                    
                    # Apply equirectangular conversion
                    self.equirectangular_frame = self._convert_to_equirectangular(self.frame)
                
                # Small delay to match framerate
                time.sleep(0.01)
        
        except Exception as e:
            self.logger.error(f"Process loop error: {str(e)}")
    
    def _convert_to_equirectangular(self, frame):
        """Convert dual fisheye frame to equirectangular projection"""
        if frame is None:
            return None
        
        try:
            # Get equirectangular dimensions
            equ_h = int(frame.shape[0] * self.config.get('equ_height_ratio', 0.5))
            equ_w = frame.shape[1]
            
            # Remap using the pre-calculated maps
            equirectangular = cv2.remap(frame, self.fisheye_xmap, self.fisheye_ymap, 
                                        cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            
            return equirectangular
        except Exception as e:
            self.logger.error(f"Equirectangular conversion error: {str(e)}")
            return frame
    
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
            h264_filename = f"dualfisheye_{timestamp}.h264"
            
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
            
            # Create a VideoWriter for recording
            fps = self.config['fps']
            width = self.config['width']
            height = self.config['height']
            
            # Choose which frame to record based on display mode
            if self.display_mode == 'equirectangular':
                # Get equirectangular dimensions
                equ_h = int(height * self.config.get('equ_height_ratio', 0.5))
                equ_w = width
                self.video_writer = cv2.VideoWriter(
                    self.h264_path,
                    cv2.VideoWriter_fourcc(*'H264'),
                    fps,
                    (equ_w, equ_h)
                )
            else:
                # Record original fisheye
                self.video_writer = cv2.VideoWriter(
                    self.h264_path,
                    cv2.VideoWriter_fourcc(*'H264'),
                    fps,
                    (width, height)
                )
            
            self.recording = True
            self.start_time = datetime.now()
            
            self.logger.info(f"Started recording: {self.h264_path}")
            
            # Notify sync manager of recording start
            if self.sync_manager:
                self.sync_manager.register_recording_start(self.current_video_path, self.start_time)
                
            # Start recording thread
            self.recording_thread = Thread(target=self._recording_loop)
            self.recording_thread.daemon = True
            self.recording_thread.start()
                
        except Exception as e:
            self.logger.error(f"Start recording error: {str(e)}")
    
    def _recording_loop(self):
        """Loop for recording frames"""
        try:
            while self.recording and not self.stop_event.is_set():
                if self.display_mode == 'equirectangular' and self.equirectangular_frame is not None:
                    # Write equirectangular frame
                    self.video_writer.write(self.equirectangular_frame)
                elif self.frame is not None:
                    # Write original frame
                    self.video_writer.write(self.frame)
                
                # Control frame rate for recording
                time.sleep(1.0 / self.config['fps'])
        except Exception as e:
            self.logger.error(f"Recording loop error: {str(e)}")
            self.stop_recording()
    
    def stop_recording(self):
        """Stop recording"""
        if not self.recording:
            self.logger.warning("Not recording")
            return
        
        try:
            # Stop recording
            self.recording = False
            
            # Wait for recording thread to finish
            if hasattr(self, 'recording_thread') and self.recording_thread:
                self.recording_thread.join(timeout=2.0)
            
            # Release video writer
            if hasattr(self, 'video_writer') and self.video_writer:
                self.video_writer.release()
            
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
            
            # Determine which frame to save based on display mode
            if self.display_mode == 'equirectangular' and self.equirectangular_frame is not None:
                # Save equirectangular photo
                photo_filename = f"equirectangular_{timestamp}{self.config['photo_extension']}"
                photo_path = os.path.join(photo_dir, photo_filename)
                cv2.imwrite(photo_path, self.equirectangular_frame)
            else:
                # Save original fisheye photo
                photo_filename = f"dualfisheye_{timestamp}{self.config['photo_extension']}"
                photo_path = os.path.join(photo_dir, photo_filename)
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
        if self.display_mode == 'equirectangular' and self.equirectangular_frame is not None:
            frame = self.equirectangular_frame
        elif self.frame is not None:
            frame = self.frame
        else:
            return None
        
        try:
            # Create a copy to avoid modifying the original frame
            frame = frame.copy()
            
            # Resize if needed
            if self.config['preview_width'] > 0 and self.config['preview_height'] > 0:
                frame = cv2.resize(frame, (self.config['preview_width'], self.config['preview_height']))
                
            return frame
        except Exception as e:
            self.logger.error(f"Preview frame error: {str(e)}")
            return None
    
    def set_display_mode(self, mode):
        """Set the display mode"""
        valid_modes = ['fisheye', 'equirectangular']
        
        if mode in valid_modes:
            self.display_mode = mode
            self.logger.info(f"Display mode set to: {mode}")
            return True
        else:
            self.logger.warning(f"Invalid display mode: {mode}. Valid modes are: {valid_modes}")
            return False
    
    def toggle_display_mode(self):
        """Toggle between available display modes"""
        modes = ['fisheye', 'equirectangular']
        current_index = modes.index(self.display_mode) if self.display_mode in modes else 0
        next_index = (current_index + 1) % len(modes)
        self.display_mode = modes[next_index]
        self.logger.info(f"Display mode toggled to: {self.display_mode}")
        return self.display_mode
