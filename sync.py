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

import os
import time
import json
import logging
import RPi.GPIO as GPIO
from datetime import datetime
from threading import Thread, Event, Lock
import queue

from config import GNSS_CONFIG, STORAGE_CONFIG, APP_CONFIG

class SyncManager:
    """Class for handling PPS signal synchronization between camera and GNSS"""
    
    def __init__(self):
        """Initialize SyncManager"""
        self.logger = logging.getLogger('SyncManager')
        self.gnss_config = GNSS_CONFIG
        self.storage_config = STORAGE_CONFIG
        self.app_config = APP_CONFIG
        
        # PPS related variables
        self.pps_pin = self.gnss_config['pps_gpio_pin']
        self.pps_edge = GPIO.RISING
        self.last_pps_time = None
        self.pps_counter = 0
        self.pps_intervals = []
        self.pps_stability = 0
        self.pps_running = False
        
        # PPS event queue and lock
        self.pps_queue = queue.Queue(maxsize=100)
        self.pps_lock = Lock()
        
        # Recording sync data
        self.recordings = {}
        self.photos = {}
        self.gnss_updates = []
        
        # Synchronization file
        self.sync_file_path = None
        
        # Thread related
        self.pps_thread = None
        self.stop_event = Event()
        
        # Initialize storage directories
        self._init_directories()
    
    def _init_directories(self):
        """Initialize storage directories"""
        base_path = self.storage_config['base_path']
        sync_dir = os.path.join(base_path, self.storage_config['sync_dir'])
        
        if not os.path.exists(sync_dir):
            os.makedirs(sync_dir)
            self.logger.info(f"Created directory: {sync_dir}")
        
        # Initialize sync file
        timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
        
        if self.storage_config['use_timestamp_subdir']:
            subdir = datetime.now().strftime("%Y%m%d")
            sync_dir = os.path.join(
                self.storage_config['base_path'],
                self.storage_config['sync_dir'],
                subdir
            )
            if not os.path.exists(sync_dir):
                os.makedirs(sync_dir)
        else:
            sync_dir = os.path.join(
                self.storage_config['base_path'],
                self.storage_config['sync_dir']
            )
        
        self.sync_file_path = os.path.join(sync_dir, f"sync_{timestamp}.json")
        self.logger.info(f"Initialized sync file: {self.sync_file_path}")
    
    def start(self):
        """Start PPS monitoring"""
        if self.pps_running:
            self.logger.warning("PPS monitoring is already running")
            return
            
        if not self.app_config['enable_pps_sync']:
            self.logger.info("PPS synchronization is disabled in config")
            return
        
        try:
            # Initialize GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pps_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            
            # Register callback for PPS signal
            GPIO.add_event_detect(self.pps_pin, self.pps_edge, callback=self._pps_callback)
            
            self.pps_running = True
            self.stop_event.clear()
            
            # Start PPS processing thread
            self.pps_thread = Thread(target=self._pps_process_loop)
            self.pps_thread.daemon = True
            self.pps_thread.start()
            
            self.logger.info(f"Started PPS monitoring on pin {self.pps_pin}")
            
        except Exception as e:
            self.logger.error(f"Error starting PPS monitoring: {str(e)}")
            GPIO.cleanup(self.pps_pin)
    
    def stop(self):
        """Stop PPS monitoring"""
        if not self.pps_running:
            return
            
        self.stop_event.set()
        
        if self.pps_thread:
            self.pps_thread.join(timeout=3.0)
        
        try:
            GPIO.cleanup(self.pps_pin)
        except:
            pass
        
        self._save_sync_data()
        
        self.pps_running = False
        self.logger.info("Stopped PPS monitoring")
    
    def _pps_callback(self, channel):
        """Callback for PPS GPIO signal"""
        pps_time = datetime.now()
        
        try:
            # Add to PPS queue
            self.pps_queue.put(pps_time)
        except queue.Full:
            pass
    
    def _pps_process_loop(self):
        """Process PPS signals from queue"""
        prev_pps_time = None
        
        while not self.stop_event.is_set():
            try:
                # Get PPS time from queue with timeout
                try:
                    pps_time = self.pps_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                with self.pps_lock:
                    # Store PPS time
                    self.last_pps_time = pps_time
                    self.pps_counter += 1
                    
                    # Calculate interval if we have previous PPS time
                    if prev_pps_time:
                        interval = (pps_time - prev_pps_time).total_seconds()
                        
                        # Keep last 10 intervals for stability calculation
                        self.pps_intervals.append(interval)
                        if len(self.pps_intervals) > 10:
                            self.pps_intervals.pop(0)
                        
                        # Calculate stability
                        if len(self.pps_intervals) >= 3:
                            avg = sum(self.pps_intervals) / len(self.pps_intervals)
                            max_deviation = max([abs(i - avg) for i in self.pps_intervals])
                            self.pps_stability = 1.0 - min(1.0, max_deviation)
                    
                    prev_pps_time = pps_time
                
                self.logger.debug(f"PPS pulse detected: {pps_time.strftime('%H:%M:%S.%f')}")
                
                # Periodically save sync data
                if self.pps_counter % 60 == 0:  # Save every 60 PPS pulses
                    self._save_sync_data()
                
            except Exception as e:
                self.logger.error(f"PPS process error: {str(e)}")
                time.sleep(0.1)
    
    def get_last_pps_time(self):
        """Get last PPS time"""
        with self.pps_lock:
            return self.last_pps_time
    
    def get_pps_stability(self):
        """Get PPS stability (0.0-1.0)"""
        with self.pps_lock:
            return self.pps_stability
    
    def register_recording_start(self, video_path, timestamp):
        """
        Register the start of a video recording
        
        Args:
            video_path: Path to the video file
            timestamp: Timestamp when recording started
        """
        with self.pps_lock:
            pps_time = self.last_pps_time
            pps_count = self.pps_counter
        
        self.recordings[video_path] = {
            'start_time': timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'),
            'start_pps_time': pps_time.strftime('%Y-%m-%d %H:%M:%S.%f') if pps_time else None,
            'start_pps_count': pps_count,
            'stop_time': None,
            'stop_pps_time': None,
            'stop_pps_count': None
        }
        
        self.logger.info(f"Registered recording start: {video_path}")
        
        # Save sync data
        self._save_sync_data()
    
    def register_recording_stop(self, video_path, timestamp):
        """
        Register the stop of a video recording
        
        Args:
            video_path: Path to the video file
            timestamp: Timestamp when recording stopped
        """
        with self.pps_lock:
            pps_time = self.last_pps_time
            pps_count = self.pps_counter
        
        if video_path in self.recordings:
            self.recordings[video_path].update({
                'stop_time': timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'stop_pps_time': pps_time.strftime('%Y-%m-%d %H:%M:%S.%f') if pps_time else None,
                'stop_pps_count': pps_count
            })
            
            self.logger.info(f"Registered recording stop: {video_path}")
            
            # Save sync data
            self._save_sync_data()
        else:
            self.logger.warning(f"Cannot register stop for unknown recording: {video_path}")
    
    def register_photo_capture(self, photo_path, timestamp):
        """
        Register a photo capture
        
        Args:
            photo_path: Path to the photo file
            timestamp: Timestamp when photo was captured
        """
        with self.pps_lock:
            pps_time = self.last_pps_time
            pps_count = self.pps_counter
        
        self.photos[photo_path] = {
            'capture_time': timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'),
            'pps_time': pps_time.strftime('%Y-%m-%d %H:%M:%S.%f') if pps_time else None,
            'pps_count': pps_count
        }
        
        self.logger.info(f"Registered photo capture: {photo_path}")
        
        # Save sync data
        self._save_sync_data()
    
    def register_gnss_update(self, position, timestamp):
        """
        Register a GNSS position update
        
        Args:
            position: Tuple of (latitude, longitude, altitude)
            timestamp: Timestamp of the update
        """
        with self.pps_lock:
            pps_time = self.last_pps_time
            pps_count = self.pps_counter
        
        # Only store periodic updates (every 5 seconds)
        if self.gnss_updates and time.time() - self.gnss_updates[-1]['time'] < 5:
            return
            
        lat, lon, alt = position
        
        update = {
            'time': time.time(),
            'timestamp': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f'),
            'position': {
                'latitude': lat,
                'longitude': lon,
                'altitude': alt
            },
            'pps_time': pps_time.strftime('%Y-%m-%d %H:%M:%S.%f') if pps_time else None,
            'pps_count': pps_count
        }
        
        self.gnss_updates.append(update)
        
        # Limit the number of stored GNSS updates
        if len(self.gnss_updates) > 1000:
            self.gnss_updates = self.gnss_updates[-1000:]
    
    def _save_sync_data(self):
        """Save synchronization data to file"""
        if not self.sync_file_path:
            return
            
        try:
            # Prepare sync data
            sync_data = {
                'recordings': self.recordings,
                'photos': self.photos,
                'gnss_updates': self.gnss_updates[-100:],  # Only save last 100 updates
                'pps_info': {
                    'pin': self.pps_pin,
                    'counter': self.pps_counter,
                    'stability': self.pps_stability,
                    'last_time': self.last_pps_time.strftime('%Y-%m-%d %H:%M:%S.%f') if self.last_pps_time else None
                }
            }
            
            # Write to file
            with open(self.sync_file_path, 'w') as f:
                json.dump(sync_data, f, indent=2)
                
            self.logger.debug(f"Saved sync data to {self.sync_file_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving sync data: {str(e)}")
