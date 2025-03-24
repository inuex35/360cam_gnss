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
import serial
import pynmea2
import gpxpy
import gpxpy.gpx
import logging
from datetime import datetime
from threading import Thread, Event
import queue

from config import GNSS_CONFIG, STORAGE_CONFIG, APP_CONFIG

class GNSS:
    """Class for processing GNSS data and saving in GPX and NMEA formats"""
    
    def __init__(self, sync_manager=None):
        """
        Initialize GNSS class
        
        Args:
            sync_manager: Instance of sync manager (optional)
        """
        self.logger = logging.getLogger('GNSS')
        self.config = GNSS_CONFIG
        self.storage_config = STORAGE_CONFIG
        self.app_config = APP_CONFIG
        
        # GNSS data processing variables
        self.serial = None
        self.running = False
        self.waypoints = []
        self.nmea_data = []
        self.current_position = None
        self.current_time = None
        self.sync_manager = sync_manager
        
        # Latest GGA, RMC, GSA data
        self.last_gga = None
        self.last_rmc = None
        self.last_gsa = None
        
        # Thread-related
        self.gnss_thread = None
        self.process_thread = None
        self.stop_event = Event()
        self.data_queue = queue.Queue(maxsize=1000)
        
        # Initialize storage directories
        self._init_directories()
        
        # Initialize GPX file
        self.gpx = None
        self.gpx_track = None
        self.gpx_segment = None
        self.current_gpx_path = None
        self.current_nmea_path = None
        self.nmea_file = None
    
    def _init_directories(self):
        """Initialize storage directories"""
        base_path = self.storage_config['base_path']
        gnss_dir = os.path.join(base_path, self.storage_config['gnss_dir'])
        
        if not os.path.exists(gnss_dir):
            os.makedirs(gnss_dir)
            self.logger.info(f"Created directory: {gnss_dir}")
    
    def open(self):
        """Open serial port"""
        try:
            self.serial = serial.Serial(
                port=self.config['port'],
                baudrate=self.config['baudrate'],
                parity=self.config['parity'],
                stopbits=self.config['stopbits'],
                timeout=self.config['timeout']
            )
            
            self.logger.info(f"Opened GNSS serial port: {self.config['port']}")
            return True
        except Exception as e:
            self.logger.error(f"GNSS serial port initialization error: {str(e)}")
            return False
