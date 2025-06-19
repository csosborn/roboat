import time
import json
import os

class AvionicsLogger:
    def __init__(self, max_files=10, file_size_kb=32):
        self.max_files = max_files
        self.file_size = file_size_kb * 1024
        self.current_file = 0
        self.current_offset = 0
        self.logs_dir = "logs"
        self.index_file = self.logs_dir + "/log_index.json"
        self._init_filesystem()
        
    def _init_filesystem(self):
        # Create logs directory if it doesn't exist
        try:
            os.mkdir(self.logs_dir)
        except:
            pass  # Directory might already exist
            
        # Create index file if it doesn't exist
        try:
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
        except:
            self.index = {
                'current_file': 0,
                'files': {},
                'last_utc_time': None  # Will store last known UTC time
            }
            self._save_index()
        print(f"Initial log file is {self._get_log_filename(self.current_file)}.")
            
    def _save_index(self):
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f)
            
    def _get_log_filename(self, file_num):
        return self.logs_dir + "/log_{:03d}.csv".format(file_num)
        
    def _write_header(self, filename):
        header = "utc_timestamp,lat,lon,gps_heading,gps_speed,mag_heading,pitch,roll\n"
        with open(filename, 'w') as f:
            f.write(header)
            
    def _rotate_log_file(self):
        # Save current file info
        self.index['files'][self._get_log_filename(self.current_file)] = {
            'start_utc': self.index['last_utc_time'],
            'size': self.current_offset
        }
        
        # Move to next file
        self.current_file = (self.current_file + 1) % self.max_files
        self.current_offset = 0
        
        # Initialize new file
        new_filename = self._get_log_filename(self.current_file)
        self._write_header(new_filename)
        
        # Update and save index
        self.index['current_file'] = self.current_file
        self._save_index()

        print(f"Current log file is now {new_filename}.")
        
    def log_data(self, lat, lon, gps_heading, gps_speed, mag_heading, pitch, roll, utc_time=None):
        """
        Log data with UTC timestamp.
        utc_time should be a tuple of (year, month, day, hour, minute, second, millisecond)
        If utc_time is None, the last known UTC time will be used
        """
        if utc_time is not None:
            # Update the last known UTC time
            self.index['last_utc_time'] = utc_time
            
        if self.index['last_utc_time'] is None:
            # Can't log without UTC time
            return
            
        # Format UTC time as ISO8601 string
        year, month, day, hour, minute, second, ms = self.index['last_utc_time']
        utc_str = "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:03}Z".format(
            int(year), int(month), int(day),
            int(hour), int(minute), int(second),
            int(ms)
        )
        
        log_entry = f"{utc_str},{lat:.6f},{lon:.6f},{gps_heading:.1f},{gps_speed:.1f},{mag_heading:.1f},{pitch:.1f},{roll:.1f}\n"
        
        filename = self._get_log_filename(self.current_file)
        
        # Check if we need to rotate to a new file
        if self.current_offset + len(log_entry) > self.file_size:
            self._rotate_log_file()
            filename = self._get_log_filename(self.current_file)
            
        # Append the log entry
        with open(filename, 'a') as f:
            f.write(log_entry)
            
        self.current_offset += len(log_entry)
        
    def get_available_logs(self):
        """Returns a list of available log files and their metadata"""
        return self.index['files']
        
    def read_log_file(self, filename):
        """Reads and returns the contents of a specific log file"""
        try:
            with open(filename, 'r') as f:
                return f.read()
        except:
            return None 