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
    
    def start(self):
        """Start GNSS data collection"""
        if self.running:
            self.logger.warning("GNSS is already running")
            return
        
        if not self.serial:
            if not self.open():
                return
        
        self._init_gpx()
        self._init_nmea_file()
        
        self.running = True
        self.stop_event.clear()
        
        # Start GNSS data collection thread
        self.gnss_thread = Thread(target=self._gnss_loop)
        self.gnss_thread.daemon = True
        self.gnss_thread.start()
        
        # Start data processing thread
        self.process_thread = Thread(target=self._process_loop)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        self.logger.info("Started GNSS data collection")
    
    def stop(self):
        """Stop GNSS data collection"""
        self.stop_event.set()
        
        if self.gnss_thread:
            self.gnss_thread.join(timeout=3.0)
        
        if self.process_thread:
            self.process_thread.join(timeout=3.0)
        
        if self.serial:
            self.serial.close()
            self.serial = None
        
        self._save_gpx()
        self._close_nmea_file()
        
        self.running = False
        self.logger.info("Stopped GNSS data collection")
    
    def _init_gpx(self):
        """Initialize GPX file"""
        # Create new GPX object
        self.gpx = gpxpy.gpx.GPX()
        
        # Add metadata
        self.gpx.name = "360cam_gnss GPS Track"
        self.gpx.description = f"Recorded with 360cam_gnss on {datetime.now().strftime('%Y-%m-%d')}"
        
        # Add track
        self.gpx_track = gpxpy.gpx.GPXTrack()
        self.gpx.tracks.append(self.gpx_track)
        
        # Add segment
        self.gpx_segment = gpxpy.gpx.GPXTrackSegment()
        self.gpx_track.segments.append(self.gpx_segment)
        
        # Set file path
        timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
        
        if self.storage_config['use_timestamp_subdir']:
            subdir = datetime.now().strftime("%Y%m%d")
            gnss_dir = os.path.join(
                self.storage_config['base_path'],
                self.storage_config['gnss_dir'],
                subdir
            )
            if not os.path.exists(gnss_dir):
                os.makedirs(gnss_dir)
        else:
            gnss_dir = os.path.join(
                self.storage_config['base_path'],
                self.storage_config['gnss_dir']
            )
        
        self.current_gpx_path = os.path.join(gnss_dir, f"track_{timestamp}{self.config['gpx_extension']}")
        self.logger.info(f"Initialized GPX track: {self.current_gpx_path}")
    
    def _init_nmea_file(self):
        """Initialize NMEA file"""
        timestamp = datetime.now().strftime(self.storage_config['timestamp_format'])
        
        if self.storage_config['use_timestamp_subdir']:
            subdir = datetime.now().strftime("%Y%m%d")
            gnss_dir = os.path.join(
                self.storage_config['base_path'],
                self.storage_config['gnss_dir'],
                subdir
            )
            if not os.path.exists(gnss_dir):
                os.makedirs(gnss_dir)
        else:
            gnss_dir = os.path.join(
                self.storage_config['base_path'],
                self.storage_config['gnss_dir']
            )
        
        self.current_nmea_path = os.path.join(gnss_dir, f"nmea_{timestamp}{self.config['nmea_extension']}")
        self.nmea_file = open(self.current_nmea_path, "w")
        self.logger.info(f"Initialized NMEA file: {self.current_nmea_path}")
    
    def _save_gpx(self):
        """Save GPX file"""
        if self.gpx and self.current_gpx_path:
            try:
                with open(self.current_gpx_path, 'w') as gpx_file:
                    gpx_file.write(self.gpx.to_xml())
                self.logger.info(f"Saved GPX track with {len(self.gpx_segment.points)} points to {self.current_gpx_path}")
            except Exception as e:
                self.logger.error(f"Error saving GPX file: {str(e)}")
    
    def _close_nmea_file(self):
        """Close NMEA file"""
        if self.nmea_file:
            try:
                self.nmea_file.close()
                self.logger.info(f"Closed NMEA file: {self.current_nmea_path}")
            except Exception as e:
                self.logger.error(f"Error closing NMEA file: {str(e)}")
            self.nmea_file = None
    
    def _gnss_loop(self):
        """GNSS serial data collection loop"""
        last_read_time = time.time()
        
        try:
            while not self.stop_event.is_set():
                # Read data from serial port
                if self.serial.in_waiting:
                    try:
                        line = self.serial.readline().decode('ascii', errors='replace').strip()
                        if line:
                            # Put data in queue for processing
                            self.data_queue.put((time.time(), line))
                    except Exception as e:
                        self.logger.error(f"Serial read error: {str(e)}")
                else:
                    # Sleep to prevent CPU overload
                    time.sleep(0.01)
        except Exception as e:
            self.logger.error(f"GNSS loop error: {str(e)}")
    
    def _process_loop(self):
        """Process GNSS data from queue"""
        last_save_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                # Get data from queue with timeout
                try:
                    timestamp, line = self.data_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Write raw NMEA to file
                if self.nmea_file:
                    try:
                        self.nmea_file.write(f"{datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} {line}\n")
                        self.nmea_file.flush()
                    except Exception as e:
                        self.logger.error(f"NMEA write error: {str(e)}")
                
                # Parse NMEA sentence
                try:
                    msg = pynmea2.parse(line)
                    
                    # Store specific message types
                    if isinstance(msg, pynmea2.GGA):
                        self.last_gga = msg
                        
                        # Update position if valid
                        if msg.latitude and msg.longitude:
                            # Create GPX point
                            point = gpxpy.gpx.GPXTrackPoint(
                                latitude=msg.latitude,
                                longitude=msg.longitude,
                                elevation=msg.altitude,
                                time=datetime.combine(
                                    datetime.now().date(),
                                    datetime.strptime(msg.timestamp.strftime('%H%M%S.%f'), '%H%M%S.%f').time()
                                )
                            )
                            
                            # Add extended data
                            point.extensions = {
                                'fix_quality': msg.gps_qual,
                                'num_sats': msg.num_sats,
                                'hdop': msg.horizontal_dil,
                                'geoid_sep': msg.geo_sep
                            }
                            
                            # Add to track
                            self.gpx_segment.points.append(point)
                            
                            # Update current position
                            self.current_position = (msg.latitude, msg.longitude, msg.altitude)
                            
                            # Notify sync manager if PPS is enabled
                            if self.sync_manager and self.app_config['enable_pps_sync']:
                                self.sync_manager.register_gnss_update(
                                    position=self.current_position,
                                    timestamp=timestamp
                                )
                    
                    elif isinstance(msg, pynmea2.RMC):
                        self.last_rmc = msg
                        self.current_time = msg.datetime
                    
                    elif isinstance(msg, pynmea2.GSA):
                        self.last_gsa = msg
                
                except Exception as e:
                    # Not all lines are valid NMEA sentences
                    pass
                
                # Periodically save GPX file
                current_time = time.time()
                if current_time - last_save_time > 30:  # Save every 30 seconds
                    self._save_gpx()
                    last_save_time = current_time
                    
            except Exception as e:
                self.logger.error(f"Process loop error: {str(e)}")
                time.sleep(0.1)
    
    def get_current_position(self):
        """Get current position (latitude, longitude, altitude)"""
        return self.current_position
    
    def get_current_time(self):
        """Get current time from GNSS data"""
        return self.current_time
    
    def get_fix_info(self):
        """Get current fix information"""
        fix_info = {
            'valid': False,
            'satellites': 0,
            'quality': 0,
            'hdop': 0,
            'speed': 0,
            'track': 0
        }
        
        if self.last_gga:
            fix_info['valid'] = self.last_gga.gps_qual > 0
            fix_info['satellites'] = int(self.last_gga.num_sats) if self.last_gga.num_sats else 0
            fix_info['quality'] = int(self.last_gga.gps_qual) if self.last_gga.gps_qual else 0
            fix_info['hdop'] = float(self.last_gga.horizontal_dil) if self.last_gga.horizontal_dil else 0
            
        if self.last_rmc:
            fix_info['speed'] = float(self.last_rmc.spd_over_grnd) if self.last_rmc.spd_over_grnd else 0
            fix_info['track'] = float(self.last_rmc.true_course) if self.last_rmc.true_course else 0
            
        return fix_info
    
    def add_waypoint(self, name=None, description=None):
        """
        Add a waypoint at the current position
        
        Args:
            name: Name of the waypoint (default: timestamp)
            description: Description of the waypoint (optional)
            
        Returns:
            str: Waypoint ID if successful, None otherwise
        """
        if not self.current_position:
            self.logger.warning("Cannot add waypoint: No valid position")
            return None
        
        try:
            lat, lon, ele = self.current_position
            
            if not name:
                name = f"WP_{datetime.now().strftime('%H%M%S')}"
                
            waypoint = gpxpy.gpx.GPXWaypoint(
                latitude=lat,
                longitude=lon,
                elevation=ele,
                time=datetime.now(),
                name=name,
                description=description
            )
            
            self.gpx.waypoints.append(waypoint)
            self.waypoints.append(waypoint)
            
            # Save GPX after adding waypoint
            self._save_gpx()
            
            self.logger.info(f"Added waypoint: {name} at {lat}, {lon}")
            return name
            
        except Exception as e:
            self.logger.error(f"Error adding waypoint: {str(e)}")
            return None
