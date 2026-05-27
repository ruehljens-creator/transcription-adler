import subprocess
import json
import re
import os
from datetime import datetime

def reverse_geocode(lat, lon):
    """
    Translates lat/lon coordinates into a real city/country address using geopy Nominatim.
    """
    try:
        from geopy.geocoders import Nominatim
        # Nominatim requires a descriptive user agent to comply with usage terms
        geolocator = Nominatim(user_agent="transcriber_desktop_app")
        location = geolocator.reverse((lat, lon), timeout=5)
        if location:
            addr = location.raw.get('address', {})
            # Look for city/town/village/hamlet/suburb to form a clean short name
            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('hamlet') or addr.get('suburb')
            country = addr.get('country')
            if city and country:
                return f"{city}, {country}"
            # Fallback to a truncated address
            parts = location.address.split(', ')
            if len(parts) > 3:
                return ", ".join(parts[-3:])
            return location.address
    except Exception as e:
        print(f"Error reverse-geocoding {lat}, {lon}: {e}")
    return None

def get_metadata(file_path):
    """
    Extracts metadata (duration, creation date, GPS location) from audio/video files using ffprobe.
    """
    try:
        # Run ffprobe to get media details in JSON format
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_format',
            '-show_streams',
            '-of', 'json',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        format_info = data.get('format', {})
        tags = format_info.get('tags', {})
        
        # 1. Clip name
        clip_name = os.path.basename(file_path)
        
        # 2. Duration
        duration_sec = float(format_info.get('duration', 0.0))
        hours = int(duration_sec // 3600)
        minutes = int((duration_sec % 3600) // 60)
        seconds = int(duration_sec % 60)
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # 3. Creation Date
        # Look for creation_time in format tags or stream tags
        creation_time = tags.get('creation_time')
        if not creation_time:
            for stream in data.get('streams', []):
                s_tags = stream.get('tags', {})
                if 'creation_time' in s_tags:
                    creation_time = s_tags['creation_time']
                    break
        
        if creation_time:
            try:
                # Parse ISO time format (e.g. 2026-05-27T10:48:33.000000Z)
                dt = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
                creation_str = dt.strftime('%d.%m.%Y %H:%M:%S')
            except Exception:
                creation_str = creation_time
        else:
            # Fallback to filesystem timestamp
            try:
                mtime = os.path.getmtime(file_path)
                creation_str = datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M:%S')
            except Exception:
                creation_str = "Unbekannt"
                
        # 4. GPS Location
        # Standard key for location in QuickTime is com.apple.quicktime.location.ISO6709
        # or location, location-eng, etc.
        location_raw = None
        for key, val in tags.items():
            if 'location' in key.lower():
                location_raw = val
                break
                
        gps_coords = None
        google_maps_link = None
        
        if location_raw:
            # ISO 6709 format is typically like: +52.5200+013.4050/ or +52.5200+013.4050+120.000/
            match = re.match(r'([+-]\d+\.\d+)([+-]\d+\.\d+)', location_raw)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                address_name = reverse_geocode(lat, lon)
                gps_coords = {
                    'lat': lat,
                    'lon': lon,
                    'formatted': f"{lat:+.4f}, {lon:+.4f}",
                    'address': address_name if address_name else f"{lat:+.4f}, {lon:+.4f}"
                }
                google_maps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        
        return {
            'clip_name': clip_name,
            'duration_sec': duration_sec,
            'duration_str': duration_str,
            'creation_date': creation_str,
            'gps': gps_coords,
            'maps_link': google_maps_link
        }
    except Exception as e:
        print(f"Error extracting metadata from {file_path}: {e}")
        # Basic fallback using file system
        try:
            clip_name = os.path.basename(file_path)
            mtime = os.path.getmtime(file_path)
            creation_str = datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M:%S')
            return {
                'clip_name': clip_name,
                'duration_sec': 0.0,
                'duration_str': "00:00:00",
                'creation_date': creation_str,
                'gps': None,
                'maps_link': None
            }
        except Exception:
            return {
                'clip_name': os.path.basename(file_path),
                'duration_sec': 0.0,
                'duration_str': "Unbekannt",
                'creation_date': "Unbekannt",
                'gps': None,
                'maps_link': None
            }

if __name__ == '__main__':
    # Quick test command line interface
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(get_metadata(sys.argv[1]), indent=2, ensure_ascii=False))
    else:
        print("Usage: python metadata.py <path_to_media_file>")
