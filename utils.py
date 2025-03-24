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
import logging
import subprocess
import time
from datetime import datetime
import shutil
import json

from config import STORAGE_CONFIG, APP_CONFIG

def setup_logging():
    """Setup logging configuration"""
    log_level = getattr(logging, APP_CONFIG['log_level'])
    
    # Create logs directory
    log_dir = os.path.join(STORAGE_CONFIG['base_path'], 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"360cam_gnss_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at level {APP_CONFIG['log_level']}")
    
    return logger

def check_dependencies():
    """Check if all required dependencies are installed"""
    logger = logging.getLogger(__name__)
    
    # Check OpenCV
    try:
        import cv2
        logger.info(f"OpenCV version: {cv2.__version__}")
    except ImportError:
        logger.error("OpenCV not found. Please install opencv-python")
        return False
    
    # Check GNSS libraries
    try:
        import pynmea2
        import gpxpy
        logger.info("GNSS libraries found")
    except ImportError:
        logger.error("GNSS libraries not found. Please install pynmea2 and gpxpy")
        return False
    
    # Check GPIO
    try:
        import RPi.GPIO as GPIO
        logger.info("RPi.GPIO found")
    except ImportError:
        logger.error("RPi.GPIO not found. Please install RPi.GPIO")
        return False
    
    # Check if Raspberry Pi
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
        if 'Raspberry Pi' in model:
            logger.info(f"Raspberry Pi detected: {model.strip()}")
        else:
            logger.warning(f"Not running on Raspberry Pi: {model.strip()}")
    except Exception as e:
        logger.warning(f"Could not detect Raspberry Pi: {str(e)}")
    
    return True

def get_system_info():
    """Get system information"""
    logger = logging.getLogger(__name__)
    info = {}
    
    # Get CPU temperature
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
        info['cpu_temp'] = temp
    except Exception as e:
        logger.warning(f"Could not read CPU temperature: {str(e)}")
    
    # Get CPU usage
    try:
        cpu_usage = subprocess.check_output(['top', '-bn1']).decode('utf-8').split('\n')[2]
        cpu_usage = cpu_usage.split(',')[0].split(':')[1].strip()
        info['cpu_usage'] = cpu_usage
    except Exception as e:
        logger.warning(f"Could not get CPU usage: {str(e)}")
    
    # Get memory info
    try:
        mem_info = subprocess.check_output(['free', '-m']).decode('utf-8').split('\n')[1].split()
        info['mem_total'] = int(mem_info[1])
        info['mem_used'] = int(mem_info[2])
        info['mem_free'] = int(mem_info[3])
    except Exception as e:
        logger.warning(f"Could not get memory info: {str(e)}")
    
    # Get disk space
    try:
        disk_info = subprocess.check_output(['df', '-h', STORAGE_CONFIG['base_path']]).decode('utf-8').split('\n')[1].split()
        info['disk_total'] = disk_info[1]
        info['disk_used'] = disk_info[2]
        info['disk_free'] = disk_info[3]
        info['disk_usage_percent'] = disk_info[4]
    except Exception as e:
        logger.warning(f"Could not get disk info: {str(e)}")
    
    # Get kernel version
    try:
        kernel = subprocess.check_output(['uname', '-r']).decode('utf-8').strip()
        info['kernel'] = kernel
    except Exception as e:
        logger.warning(f"Could not get kernel version: {str(e)}")
    
    return info

def check_storage_space():
    """Check available storage space and clean up if necessary"""
    logger = logging.getLogger(__name__)
    min_free_space_mb = 500  # Minimum 500MB free space
    
    try:
        # Check available space
        disk_info = subprocess.check_output(['df', '-m', STORAGE_CONFIG['base_path']]).decode('utf-8').split('\n')[1].split()
        free_space_mb = int(disk_info[3])
        
        logger.info(f"Available storage space: {free_space_mb}MB")
        
        if free_space_mb < min_free_space_mb:
            logger.warning(f"Low storage space: {free_space_mb}MB available, minimum required: {min_free_space_mb}MB")
            
            # Clean up old data if space is low
            clean_old_data(min_free_space_mb)
            
            # Check again
            disk_info = subprocess.check_output(['df', '-m', STORAGE_CONFIG['base_path']]).decode('utf-8').split('\n')[1].split()
            free_space_mb = int(disk_info[3])
            
            if free_space_mb < min_free_space_mb:
                logger.error(f"Still low on storage space after cleanup: {free_space_mb}MB available")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error checking storage space: {str(e)}")
        return False

def clean_old_data(min_free_space_mb):
    """Clean up old data to free up space"""
    logger = logging.getLogger(__name__)
    
    # Function to get directories sorted by date
    def get_date_sorted_dirs(parent_dir):
        dirs = []
        for item in os.listdir(parent_dir):
            item_path = os.path.join(parent_dir, item)
            if os.path.isdir(item_path):
                try:
                    # Try to parse folder name as date (YYYYMMDD format)
                    datetime.strptime(item, "%Y%m%d")
                    dirs.append(item_path)
                except ValueError:
                    pass
        return sorted(dirs)
    
    # Check if we have enough space after each directory removal
    def check_space():
        disk_info = subprocess.check_output(['df', '-m', STORAGE_CONFIG['base_path']]).decode('utf-8').split('\n')[1].split()
        return int(disk_info[3]) >= min_free_space_mb
    
    base_path = STORAGE_CONFIG['base_path']
    
    # List of directories to check, in order of priority (oldest first)
    check_dirs = [
        os.path.join(base_path, STORAGE_CONFIG['video_dir']),
        os.path.join(base_path, STORAGE_CONFIG['gnss_dir']),
        os.path.join(base_path, STORAGE_CONFIG['photo_dir']),
        os.path.join(base_path, STORAGE_CONFIG['sync_dir'])
    ]
    
    for parent_dir in check_dirs:
        if not os.path.exists(parent_dir):
            continue
        
        date_dirs = get_date_sorted_dirs(parent_dir)
        
        # Delete oldest directories first
        for date_dir in date_dirs:
            logger.warning(f"Removing old data directory: {date_dir}")
            
            try:
                shutil.rmtree(date_dir)
                
                # Check if we now have enough space
                if check_space():
                    logger.info(f"Freed up enough space after removing {date_dir}")
                    return True
            except Exception as e:
                logger.error(f"Error removing directory {date_dir}: {str(e)}")
    
    # If we get here, deleting directories didn't free up enough space
    return False

def backup_config():
    """Backup configuration file"""
    logger = logging.getLogger(__name__)
    
    try:
        config_path = "config.py"
        backup_dir = os.path.join(STORAGE_CONFIG['base_path'], 'backups')
        
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Create backup with timestamp
        timestamp = datetime.now().strftime(STORAGE_CONFIG['timestamp_format'])
        backup_path = os.path.join(backup_dir, f"config_{timestamp}.py")
        
        shutil.copy2(config_path, backup_path)
        logger.info(f"Configuration backup created: {backup_path}")
        
        return True
    except Exception as e:
        logger.error(f"Error backing up configuration: {str(e)}")
        return False

def format_timestamp(timestamp, format_str=None):
    """Format timestamp in a consistent way"""
    if format_str is None:
        format_str = STORAGE_CONFIG['timestamp_format']
    
    if isinstance(timestamp, datetime):
        return timestamp.strftime(format_str)
    elif isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp).strftime(format_str)
    else:
        return str(timestamp)
