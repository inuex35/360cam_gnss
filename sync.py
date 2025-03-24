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
    """Class for managing PPS synchronization between camera and GNSS"""
    
    def __init__(self):
        """Initialize SyncManager class"""
        self.logger = logging.getLogger('SyncManager')
        self.config = GNSS_CONFIG
        self.storage_config = STORAGE_CONFIG
        self.app_config = APP_CONFIG
        
        # PPS and synchronization variables
        self.pps_pin = self.config['pps_gpio_pin']
        self.pps_count = 0
        self.last_pps_time = None
        self.pps_timestamps = []
        self.max_pps_history = 100  # Store last 100 PPS events
        
        # Synchronization data
        self.sync_data = {
            'recordings': [],
            'photos': [],
            'gnss_events': [],
            'pps_events': []
        }
        self.current_sync_path = None
        
        # Thread-related
        self.running = False
        self.pps_thread = None
        self.stop_event = Event()
        self.lock = Lock()
        
        # Initialize GPIO
        self._setup_gpio()
        
        # Initialize storage directories
        self._init_directories()
    
    def _init_directories(self):
        """Initialize storage directories"""
        base_path = self.storage_config['base_path']
        sync_dir = os.path.join(base_path, self.storage_config['sync_dir'])
        
        if not os.path.exists(sync_dir):
            os.makedirs(sync_dir)
            self.logger.info(f"Created directory: {sync_dir}")
    
    def _setup_gpio(self):
        """Setup GPIO for PPS signal"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pps_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            self.logger.info(f"GPIO setup for PPS pin {self.pps_pin}")
        except Exception as e:
            self.logger.error(f"GPIO setup error: {str(e)}")
    
    def start(self):
        """Start PPS monitoring"""
        if self.running:
            self.logger.warning("SyncManager is already running")
            return
        
        if not self.app_config['enable_pps_sync']:
            self.logger.info("PPS synchronization is disabled in config")
            return
        
        self._init_sync_file()
        
        self.running = True
        self.stop_event.clear()
        
        # Start PPS monitoring thread
        self.pps_thread = Thread(target=self._pps_loop)
        self.pps_thread.daemon = True
        self.pps_thread.start()
        
        self.logger.info("Started PPS synchronization")
    
    def stop(self):
        """Stop PPS monitoring"""
        self.stop_event.set()
        
        if self.pps_thread:
            self.pps_thread.join(timeout=3.0)
        
        self._save_sync_data()
        
        self.running = False
        self.logger.info("Stopped PPS synchronization")
        
        try:
            GPIO.cleanup(self.pps_pin)
        except Exception as e:
            self.logger.error(f"GPIO cleanup error: {str(e)}")
    
    def _init_sync_file(self):
        """Initialize synchronization file"""
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
        
        self.current_sync_path = os.path.join(sync_dir, f"sync_{timestamp}.json")
        self.logger.info(f"Initialized sync file: {self.current_sync_path}")
    
    def _save_sync_data(self):
        """Save synchronization data to file"""
        if self.current_sync_path:
            try:
                with open(self.current_sync_path, 'w') as sync_file:
                    json.dump(self.sync_data, sync_file, indent=4, default=str)
                self.logger.info(f"Saved sync data to {self.current_sync_path}")
            except Exception as e:
                self.logger.error(f"Error saving sync data: {str(e)}")
    
    def _pps_loop(self):
        """PPS monitoring loop"""
        last_save_time = time.time()
        
        try:
            # Setup edge detection callback
            GPIO.add_event_detect(
                self.pps_pin,
                GPIO.RISING,
                callback=self._pps_callback,
                bouncetime=10
            )
            
            # Main loop to periodically save data and keep thread running
            while not self.stop_event.is_set():
                time.sleep(0.1)
                
                # Periodically save sync data
                current_time = time.time()
                if current_time - last_save_time > 60:  # Save every minute
                    self._save_sync_data()
                    last_save_time = current_time
        
        except Exception as e:
            self.logger.error(f"PPS loop error: {str(e)}")
        finally:
            try:
                GPIO.remove_event_detect(self.pps_pin)
            except Exception as e:
                self.logger.error(f"Error removing event detection: {str(e)}")
    
    def _pps_callback(self, channel):
        """Callback for PPS signal detection"""
        timestamp = datetime.now()
        
        with self.lock:
            self.pps_count += 1
            self.last_pps_time = timestamp
            
            # Add to history, maintaining maximum size
            self.pps_timestamps.append(timestamp)
            if len(self.pps_timestamps) > self.max_pps_history:
                self.pps_timestamps.pop(0)
            
            # Record PPS event
            pps_event = {
                'count': self.pps_count,
                'time': timestamp
            }
            self.sync_data['pps_events'].append(pps_event)
            
            # Log every 10th PPS event to reduce log volume
            if self.pps_count % 10 == 0:
                self.logger.debug(f"PPS signal #{self.pps_count} detected at {timestamp}")
    
    def get_last_pps_time(self):
        """Get the timestamp of the last PPS signal"""
        with self.lock:
            return self.last_pps_time
    
    def get_pps_count(self):
        """Get the count of PPS signals"""
        with self.lock:
            return self.pps_count
    
    def register_recording_start(self, video_path, timestamp):
        """Register the start of a video recording"""
        with self.lock:
            recording = {
                'event': 'start',
                'path': video_path,
                'time': timestamp,
                'pps_count': self.pps_count,
                'pps_time': self.last_pps_time
            }
            self.sync_data['recordings'].append(recording)
            self.logger.info(f"Registered recording start at PPS #{self.pps_count}")
    
    def register_recording_stop(self, video_path, timestamp):
        """Register the end of a video recording"""
        with self.lock:
            recording = {
                'event': 'stop',
                'path': video_path,
                'time': timestamp,
                'pps_count': self.pps_count,
                'pps_time': self.last_pps_time
            }
            self.sync_data['recordings'].append(recording)
            self.logger.info(f"Registered recording stop at PPS #{self.pps_count}")
    
    def register_photo_capture(self, photo_path, timestamp):
        """Register a photo capture"""
        with self.lock:
            photo = {
                'path': photo_path,
                'time': timestamp,
                'pps_count': self.pps_count,
                'pps_time': self.last_pps_time
            }
            self.sync_data['photos'].append(photo)
            self.logger.info(f"Registered photo capture at PPS #{self.pps_count}")
    
    def register_gnss_update(self, position, timestamp):
        """Register a significant GNSS update"""
        with self.lock:
            gnss_event = {
                'position': position,
                'time': timestamp,
                'pps_count': self.pps_count,
                'pps_time': self.last_pps_time
            }
            self.sync_data['gnss_events'].append(gnss_event)
            
            # Log every 10th GNSS event to reduce log volume
            if len(self.sync_data['gnss_events']) % 10 == 0:
                self.logger.debug(f"Registered GNSS update at PPS #{self.pps_count}")
