import os
import json
import subprocess
import threading
import time
import copy
import base64
import requests
import sys
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import uuid
from db import Database

app = Flask(__name__)
CORS(app)

# Configuration
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')
CONFIG_DIR = os.path.join(os.path.dirname(__file__), 'config')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# Ensure directories exist
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

# Global state - using regular dicts without locks for reads
# Only lock during file writes
test_results = {}
tv_channels = {}  # Store successful channels
groups = {}  # Store channel groups
current_test_id = None
connectivity_tasks = {}  # Store connectivity test tasks status

# Initialize database
db = None



def load_config():
    """Load all configuration from file"""
    default_config = {}

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default_config
    return default_config


def save_config(config):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_channels():
    """Load TV channels from database"""
    global tv_channels
    try:
        tv_channels = db.get_all_channels()
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error loading channels: {str(e)}")
        tv_channels = {}
    return tv_channels


def save_channels():
    """Save TV channels to database"""
    try:
        db.save_channels(copy.deepcopy(tv_channels))
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error saving channels: {str(e)}")


def parse_m3u(content):
    """Parse M3U content and extract channel information"""
    import re

    channels = []
    lines = content.strip().split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for #EXTINF lines
        if line.startswith('#EXTINF:'):
            # Extract attributes from EXTINF line
            tvg_id = ''
            group_title = ''
            tvg_logo = ''
            catchup = ''
            catchup_source = ''
            channel_name = ''

            # Extract tvg-id
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            if tvg_id_match:
                tvg_id = tvg_id_match.group(1)

            # Extract group-title
            group_match = re.search(r'group-title="([^"]*)"', line)
            if group_match:
                group_title = group_match.group(1)

            # Extract tvg-logo
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            if logo_match:
                tvg_logo = logo_match.group(1)

            # Extract catchup
            catchup_match = re.search(r'catchup="([^"]*)"', line)
            if catchup_match:
                catchup = catchup_match.group(1)

            # Extract catchup-source
            catchup_source_match = re.search(r'catchup-source="([^"]*)"', line)
            if catchup_source_match:
                catchup_source = catchup_source_match.group(1)

            # Extract channel name (text after last comma)
            comma_pos = line.rfind(',')
            if comma_pos != -1:
                channel_name = line[comma_pos + 1:].strip()

            # Get URL from next line
            i += 1
            if i < len(lines):
                url = lines[i].strip()

                # Skip empty lines or comments
                while i < len(lines) and (not url or url.startswith('#')):
                    i += 1
                    if i < len(lines):
                        url = lines[i].strip()

                if url and not url.startswith('#'):
                    # Extract IP from URL
                    # Pattern: rtp://239.253.248.77:8000 or http://192.168.3.2:7788/rtp/239.253.248.77:8000
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', url)
                    if ip_match:
                        # Use the last IP found in URL (the actual stream IP)
                        all_ips = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', url)
                        if all_ips:
                            ip = all_ips[-1]  # Use the last IP (stream IP, not proxy IP)

                            channels.append({
                                'ip': ip,
                                'name': channel_name,
                                'tvg_id': tvg_id,
                                'url': url,
                                'group': group_title,
                                'logo': tvg_logo,
                                'catchup': catchup,
                                'playback': catchup_source
                            })

        i += 1

    return channels


def parse_markdown_channels(content):
    """Parse Markdown content and extract channel name to channel number mapping

    Supports two formats:
    1. Markdown table: | CCTV1 | 1 |
    2. Simple colon: CCTV1: 1
    """
    import re

    channels_map = {}
    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip markdown table headers and separators
        if line.startswith('|') and ('-' in line or '频道名称' in line or '频道号' in line):
            continue

        channel_name = None
        channel_number = None

        # Try to match Markdown table format: | channel_name | number |
        table_match = re.match(r'^\|\s*(.+?)\s*\|\s*(\d+)\s*\|', line)
        if table_match:
            channel_name = table_match.group(1).strip()
            channel_number = table_match.group(2).strip()
        else:
            # Try to match simple colon format: channel_name: number
            colon_match = re.match(r'^(.+?)[：:]\s*(\d+)\s*$', line)
            if colon_match:
                channel_name = colon_match.group(1).strip()
                channel_number = colon_match.group(2).strip()

        # Store in map if both name and number are found
        if channel_name and channel_number:
            channels_map[channel_name] = {
                'name': channel_name,
                'tvg_id': channel_number
            }

    return channels_map


def update_channel_library(ip, result):
    """Update channel library with test result (both successful and failed)"""
    global tv_channels

    # No lock needed for dictionary update - Python GIL handles this
    # Update or add channel (newer result overwrites older)
    # Preserve existing name if channel exists and has a name
    existing_name = ''
    if ip in tv_channels:
        # Channel exists, preserve its name (even if empty)
        existing_name = tv_channels[ip].get('name', '')

    # Preserve existing fields if channel exists
    if ip in tv_channels:
        existing_group = tv_channels[ip].get('group', '')
        existing_logo = tv_channels[ip].get('logo', '')
        existing_playback = tv_channels[ip].get('playback', '')
        existing_tvg_id = tv_channels[ip].get('tvg_id', '')
        existing_catchup = tv_channels[ip].get('catchup', '')
    else:
        existing_group = ''
        existing_logo = ''
        existing_playback = ''
        existing_tvg_id = ''
        existing_catchup = ''

    # Save both successful and failed tests
    test_status = result.get('status', 'unknown')

    # Set connectivity based on test status
    # - 'online': test passed
    # - 'failed': test failed from stream test
    # - 'offline': previously passed but now fails (will be set by connectivity test)
    # - 'untested': imported channels without testing
    if test_status == 'success':
        connectivity = 'online'
    elif test_status == 'failed':
        connectivity = 'failed'
    else:
        connectivity = 'untested'

    tv_channels[ip] = {
        'name': existing_name,  # Will be empty string for new channels, preserved for existing
        'url': result.get('url', ''),
        'screenshot': result.get('screenshot', ''),
        'timestamp': result.get('timestamp', datetime.now().isoformat()),
        'resolution': result.get('resolution', ''),
        'test_status': test_status,  # Track if test succeeded or failed
        'connectivity': connectivity,  # Set based on test result
        'group': existing_group,
        'logo': existing_logo,
        'playback': existing_playback,
        'tvg_id': existing_tvg_id,
        'catchup': existing_catchup
    }
    save_channels()


def load_results():
    """Load test results from database"""
    try:
        return db.get_all_results()
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error loading results: {str(e)}")
        return {}


def save_results():
    """Save test results to database"""
    try:
        db.save_results(copy.deepcopy(test_results))
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error in save_results: {str(e)}")
        import traceback
        traceback.print_exc()


def test_iptv_stream(base_url, ip, test_id, config, is_retry=False):
    """Test a single IPTV stream using FFmpeg"""
    global test_results  # Declare global at the beginning of function

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] test_iptv_stream called: ip={ip}, is_retry={is_retry}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] base_url template: {base_url}")

    # Replace {ip} placeholder in base_url with actual IP
    url = base_url.replace('{ip}', ip)
    ip_key = ip

    # Log the URL being tested
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {'='*50}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Testing Channel IP: {ip}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] URL: {url}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Mode: {'Retry' if is_retry else 'Initial Test'}")

    result = {
        "ip": ip,
        "url": url,
        "status": "testing",
        "timestamp": datetime.now().isoformat(),
        "screenshot": None,
        "error": None
    }

    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Setting initial status for {ip}: {result['status']}")

        # Check if test_id exists in test_results
        if test_id not in test_results:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Warning: test_id {test_id} not found in test_results, reloading from file")
            # Try to reload from file
            test_results = load_results()

        if test_id not in test_results:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: test_id {test_id} still not found after reload")
            return

        # Check if "results" key exists
        if "results" not in test_results[test_id]:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Warning: 'results' key not found, creating it")
            test_results[test_id]["results"] = {}

        # No lock needed - Python's GIL handles dictionary updates atomically
        test_results[test_id]["results"][ip_key] = result
        # Save immediately to update UI
        save_results()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initial 'testing' status saved for {ip}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error saving initial result: {str(e)}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] test_id: {test_id}, Available test_ids: {list(test_results.keys())}")
        import traceback
        traceback.print_exc()
        return  # Exit the function if we can't save initial result

    # Main try block with finally to ensure status update
    try:
        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{test_id}_{ip.replace('.', '_')}.jpg")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Screenshot path: {screenshot_path}")

        # Build FFmpeg command
        timeout = config.get("timeout") or 10  # Use 10 if timeout is None or empty
        if isinstance(timeout, str):
            try:
                timeout = int(timeout)
            except:
                timeout = 10
        custom_params = config.get("custom_params", "")

        cmd = ["ffmpeg", "-y"]

        # Add timeout parameter for network streams (in microseconds)
        cmd.extend(["-timeout", str(timeout * 1000000)])

        # Add network timeout and analysis parameters BEFORE input
        # These must come before -i flag
        cmd.extend([
            "-analyzeduration", "3000000",  # 3 seconds to analyze stream
            "-probesize", "5000000"  # 5MB probe size
        ])

        # Add RTP-specific timeout if it's an RTP URL
        if "rtp" in url.lower():
            # For RTP, we can use -rw_timeout (in microseconds)
            cmd.extend(["-rw_timeout", str(timeout * 1000000)])

        # Add custom parameters if specified (like hardware acceleration)
        if custom_params and custom_params.strip():
            # Use shlex to properly split shell-like strings
            import shlex
            try:
                custom_args = shlex.split(custom_params)
                cmd.extend(custom_args)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Custom params added: {custom_args}")
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error parsing custom params: {e}")

        # For 4K streams, we need to read more data before capturing
        # First, probe the stream to detect resolution
        probe_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-analyzeduration", "5000000",  # 5 seconds for 4K streams
            "-probesize", "10000000",       # 10MB probe size for 4K
            "-t", "3",  # Probe for 3 seconds
            "-i", url,
            "-f", "null",
            "-"
        ]

        # Quick probe to detect resolution
        detected_resolution = None
        is_4k = False
        try:
            probe_process = subprocess.Popen(
                probe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            probe_stdout, probe_stderr = probe_process.communicate(timeout=8)

            # Parse resolution from probe
            if probe_stderr:
                import re
                resolution_pattern = r'Stream.*Video.*\s(\d{3,4}x\d{3,4})'
                match = re.search(resolution_pattern, probe_stderr)
                if match:
                    detected_resolution = match.group(1)
                    width, height = map(int, detected_resolution.split('x'))
                    is_4k = width >= 3840  # 4K or higher
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Detected resolution: {detected_resolution} (4K: {is_4k})")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Probe failed, using default settings: {e}")

        # Add input URL
        cmd.extend(["-i", url])

        # For 4K streams, capture first frame without scaling (keep original resolution)
        # For other streams, capture the first frame and scale to 1080p
        if is_4k:
            cmd.extend([
                "-frames:v", "1",  # Capture 1 frame
                "-q:v", "1",       # Highest quality
                "-vf", "yadif",    # Deinterlace
                "-f", "image2",
                screenshot_path
            ])
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Using 4K capture mode (no scaling)")
        else:
            cmd.extend([
                "-frames:v", "1",  # Capture only 1 frame (first frame)
                "-q:v", "1",       # Highest quality (1-31, lower is better)
                "-vf", "yadif",    # Deinterlace for clearer image
                "-s", "1920x1080", # Full HD resolution for better OCR
                "-f", "image2",
                screenshot_path
            ])
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Using standard capture mode (1080p scaled)")

        # Log the FFmpeg command
        cmd_str = ' '.join(cmd)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] FFmpeg command: {cmd_str}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Timeout: {timeout}s")

        # Execute FFmpeg with timeout
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing FFmpeg...")
        start_time = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)
            elapsed_time = time.time() - start_time

            if process.returncode == 0 and os.path.exists(screenshot_path):
                # Successfully captured screenshot
                result["screenshot"] = f"/screenshots/{os.path.basename(screenshot_path)}"

                # Parse resolution from ffmpeg output - REQUIRED for success
                resolution = None
                if stderr:
                    # Look for Stream info in ffmpeg stderr
                    import re
                    # Pattern to match resolution like "1920x1080" or "720x576"
                    resolution_pattern = r'Stream.*Video.*\s(\d{3,4}x\d{3,4})'
                    match = re.search(resolution_pattern, stderr)
                    if match:
                        resolution = match.group(1)
                        # Validate resolution - must not be 0x0 or invalid
                        width, height = map(int, resolution.split('x'))
                        if width > 0 and height > 0:
                            result["resolution"] = resolution
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Resolution detected: {resolution}")
                        else:
                            resolution = None
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Invalid resolution detected: {match.group(1)}")

                # Only mark as success if valid resolution was detected
                if resolution:
                    result["status"] = "success"
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ SUCCESS: Channel {ip} captured successfully")
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Time taken: {elapsed_time:.2f} seconds")
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Screenshot saved: {screenshot_path}")
                else:
                    result["status"] = "failed"
                    result["error"] = "No resolution detected"
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ FAILED: Channel {ip} - No resolution detected")
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Screenshot was captured but no video resolution found")
            else:
                # First attempt failed, try just probing the stream
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Screenshot failed, trying stream probe with ffmpeg -i...")

                # Second fallback: just check if stream is accessible
                probe_cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-analyzeduration", "10000000",  # 10 seconds for better detection
                    "-probesize", "20000000",  # 20MB for better detection
                ]

                # Add timeout for RTP/UDP
                if "rtp" in url.lower() or "udp" in url.lower():
                    probe_cmd.extend(["-timeout", str(timeout * 2000000)])  # Double timeout

                # Just probe the input
                probe_cmd.extend(["-i", url])

                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Probe command: {' '.join(probe_cmd)}")

                try:
                    probe_process = subprocess.Popen(
                        probe_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )

                    probe_stdout, probe_stderr = probe_process.communicate(timeout=15)

                    # Combine stdout and stderr for checking (FFmpeg may output to either)
                    combined_output = (probe_stdout or "") + (probe_stderr or "")

                    # Check if we got stream information in either output
                    # Look for "Stream #" and "Video:" or "Input #" which indicates successful stream detection
                    # Note: ffmpeg -i returns exit code 1 even when successful (no output file specified)
                    # So we check the output content instead of return code
                    if combined_output and (("Stream #" in combined_output and "Video:" in combined_output) or
                                            ("Input #" in combined_output and ("Duration:" in combined_output or "mpegts" in combined_output))):
                        # Stream is accessible, even though screenshot failed
                        result["status"] = "success"
                        result["error"] = None
                        result["note"] = "Stream accessible but screenshot failed"

                        # Try to get resolution from probe
                        import re
                        resolution_pattern = r'Stream.*Video.*?(\d{3,4}x\d{3,4})'
                        match = re.search(resolution_pattern, combined_output)
                        if match:
                            result["resolution"] = match.group(1)
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Resolution detected: {match.group(1)}")

                        # Also check for codec info
                        if "hevc" in combined_output.lower():
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Codec: HEVC/H.265")
                        elif "h264" in combined_output.lower():
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Codec: H.264")

                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ SUCCESS (probe): Channel {ip} is accessible (no screenshot)")
                    else:
                        # Stream really is not accessible
                        result["status"] = "failed"
                        result["error"] = "Stream not accessible"
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ FAILED: Channel {ip} is not accessible")

                        # Log what we got for debugging
                        if combined_output:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Probe output: {combined_output[:200]}...")

                except (subprocess.TimeoutExpired, Exception) as probe_error:
                    # Even probe failed
                    result["status"] = "failed"
                    result["error"] = "Failed to probe stream"
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ FAILED: Channel {ip} probe failed")
                    if hasattr(locals().get('probe_process'), 'kill'):
                        try:
                            probe_process.kill()
                        except:
                            pass

        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏱ TIMEOUT: Channel {ip} exceeded {timeout} seconds")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Killing FFmpeg process...")
            process.kill()
            # Wait a bit for the process to terminate
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if it's still running
                process.terminate()
            result["status"] = "failed"
            result["error"] = f"Timeout after {timeout} seconds"
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Time elapsed: {elapsed_time:.2f} seconds")

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ Error: {url} - {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Always update the result status, no matter what happens
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {'='*50}")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Test completed for channel {ip}")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Final Status: {result['status'].upper()}")
            if result.get('error'):
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: {result['error']}")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {'='*50}")

            # Ensure we have valid test_results before updating
            if test_id in test_results and "results" in test_results[test_id]:
                # No lock needed for dictionary updates
                test_results[test_id]["results"][ip_key] = result
                # Only increment completed count if not a retry
                if not is_retry:
                    test_results[test_id]["completed"] += 1
                # Save immediately to update UI
                save_results()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Results saved to file")

                # Update channel library for all results (both successful and failed)
                update_channel_library(ip_key, result)
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] WARNING: Cannot save result - test_id {test_id} not found")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error in test_iptv_stream (final save): {str(e)}")
            import traceback
            traceback.print_exc()




def run_batch_test(base_url, start_ip, end_ip, test_id):
    """Run batch test for IP range"""
    config = load_config()

    # Get queue size from config, default to 5
    queue_size = config.get('queue_size', 5)
    if not isinstance(queue_size, int) or queue_size < 1:
        queue_size = 5

    # Parse IP range
    ip_parts = start_ip.split('.')
    base = '.'.join(ip_parts[:3])
    start_num = int(ip_parts[3])
    end_num = int(end_ip.split('.')[3])

    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting batch test")
    print(f"Test ID: {test_id}")
    print(f"Base URL: {base_url}")
    print(f"IP Range: {start_ip} to {end_ip}")
    print(f"Total IPs: {end_num - start_num + 1}")
    print(f"Queue Size: {queue_size}")
    print(f"{'='*60}\n")

    # Initialize test results without clearing old tests
    # Keep a maximum of 10 test results to avoid unlimited growth
    if len(test_results) >= 10:
        # Remove the oldest test (based on sorting by key which are UUIDs with timestamps)
        oldest_test_id = min(test_results.keys())
        del test_results[oldest_test_id]

    # Ensure base_url contains {ip} placeholder
    if '{ip}' not in base_url:
        print(f"Warning: base_url doesn't contain {{ip}} placeholder, using as-is: {base_url}")

    # No lock needed for dictionary update
    test_results[test_id] = {
        "base_url": base_url,
        "start_ip": start_ip,
        "end_ip": end_ip,
        "status": "running",
        "total": end_num - start_num + 1,
        "completed": 0,
        "results": {},
        "start_time": datetime.now().isoformat()
    }

    # Test each IP
    threads = []
    for i in range(start_num, end_num + 1):
        ip = f"{base}.{i}"
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting thread for IP: {ip}")
        thread = threading.Thread(target=test_iptv_stream, args=(base_url, ip, test_id, config))
        thread.daemon = True  # Make threads daemon so they don't block
        thread.start()
        threads.append(thread)

        # Limit concurrent threads to avoid overwhelming the system
        # Clean up completed threads
        if len(threads) >= queue_size:
            # Remove completed threads from list
            alive_threads = [t for t in threads if t.is_alive()]
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Active threads: {len(alive_threads)}/{queue_size}")
            threads = alive_threads

            # If still at capacity, wait briefly
            while len(threads) >= queue_size:
                time.sleep(0.1)
                threads = [t for t in threads if t.is_alive()]

    # Don't wait for all threads to complete - let them run in background
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] All {end_num - start_num + 1} test threads started")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Returning control to Flask - tests running in background")

    # Start a monitor thread to check completion
    def monitor_test_completion():
        """Monitor test completion in background"""
        total_ips = end_num - start_num + 1

        while True:
            time.sleep(1)  # Check every second

            # No lock needed for reading
            if test_id not in test_results:
                break  # Test was deleted

            completed = test_results[test_id].get("completed", 0)

            # Count actual results with final status (not "testing")
            results_dict = test_results[test_id].get("results", {})
            final_count = sum(1 for r in results_dict.values() if r.get("status") in ["success", "failed"])

            # Log progress periodically
            if completed % 5 == 0 or completed == total_ips:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Test progress: {completed}/{total_ips} completed, {final_count} with final status")

            # Check if all tests are completed
            if completed >= total_ips:
                test_results[test_id]["status"] = "completed"
                total_success = sum(1 for r in test_results[test_id]["results"].values() if r["status"] == "success")
                total_failed = sum(1 for r in test_results[test_id]["results"].values() if r["status"] == "failed")

                # Save results
                save_results()

                print(f"\n{'='*60}")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BATCH TEST COMPLETED")
                print(f"Test ID: {test_id}")
                print(f"Total Tested: {total_success + total_failed}")
                print(f"Success: {total_success} ✓")
                print(f"Failed: {total_failed} ✗")
                print(f"Success Rate: {(total_success / (total_success + total_failed) * 100) if (total_success + total_failed) > 0 else 0:.1f}%")
                print(f"{'='*60}\n")
                break

    monitor_thread = threading.Thread(target=monitor_test_completion, daemon=True)
    monitor_thread.start()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Monitor thread started for test {test_id}")


@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)


@app.route('/screenshots/<path:path>')
def serve_screenshot(path):
    """Serve screenshot files with no-cache headers"""
    response = send_from_directory(SCREENSHOTS_DIR, path)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """Get or update configuration"""
    if request.method == 'GET':
        config = load_config()
        return jsonify(config)

    elif request.method == 'POST':
        # Load existing config and update with new values
        config = load_config()
        config.update(request.json)
        save_config(config)
        return jsonify({"status": "success", "config": config})



@app.route('/api/test/start', methods=['POST'])
def start_test():
    """Start a new batch test"""
    data = request.json
    base_url = data.get('base_url')
    start_ip = data.get('start_ip')
    end_ip = data.get('end_ip')

    # Validate required fields
    if not base_url or not start_ip or not end_ip:
        return jsonify({"status": "error", "message": "Missing required fields: base_url, start_ip, end_ip"}), 400

    # Save the user's input to config
    config = load_config()
    config['base_url'] = base_url
    config['start_ip'] = start_ip
    config['end_ip'] = end_ip
    save_config(config)

    # Generate test ID
    test_id = str(uuid.uuid4())

    # Start test in background thread (daemon thread so it doesn't block shutdown)
    thread = threading.Thread(target=run_batch_test, args=(base_url, start_ip, end_ip, test_id))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started", "test_id": test_id})


@app.route('/api/test/status/<test_id>')
def get_test_status(test_id):
    """Get status of a running test"""
    # No lock needed for reading
    if test_id in test_results:
        # Make a copy to avoid issues during JSON serialization
        return jsonify(copy.deepcopy(test_results[test_id]))
    return jsonify({"error": "Test not found"}), 404


@app.route('/api/test/retry', methods=['POST'])
def retry_test():
    """Retry a failed test"""
    data = request.json
    test_id = data.get('test_id')
    ip = data.get('ip')

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Retry request for IP: {ip}, Test ID: {test_id}")

    # No lock needed for reading
    if test_id not in test_results:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: Test ID {test_id} not found")
        return jsonify({"error": "Test not found"}), 404

    # Get the original URL from the failed result
    if ip in test_results[test_id]["results"]:
        original_url = test_results[test_id]["results"][ip].get("url", "")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found original URL: {original_url}")
        # Simply use the base_url from the test data with {ip} placeholder
        base_url = test_results[test_id]["base_url"]
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Using base_url: {base_url}")
    else:
        # Fallback: construct base_url from saved base_url
        base_url = test_results[test_id]["base_url"]
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Using base_url from test: {base_url}")
        # Ensure base_url has proper format
        if '{ip}' not in base_url:
            if base_url.endswith('/'):
                base_url = base_url + '{ip}:8000'
            else:
                base_url = base_url + '/{ip}:8000'

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Final base_url template: {base_url}")

    config = load_config()

    try:
        # Run test in background thread with is_retry=True
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting retry thread for {ip}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Thread args: base_url={base_url}, ip={ip}, test_id={test_id}, config={config}")

        thread = threading.Thread(target=test_iptv_stream, args=(base_url, ip, test_id, config, True))
        thread.daemon = True  # Make thread daemon so it doesn't block shutdown
        thread.start()

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Retry thread started successfully for {ip}")

    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error starting retry thread: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500

    return jsonify({"status": "retrying", "test_id": test_id, "ip": ip})


@app.route('/api/test/delete/<test_id>', methods=['DELETE'])
def delete_test_history(test_id):
    """Delete a test history entry and its associated screenshots"""
    global test_results

    if test_id not in test_results:
        return jsonify({"status": "error", "message": "Test not found"}), 404

    # Get the test data before deletion
    test_data = test_results[test_id]

    # Delete associated screenshots
    screenshots_dir = SCREENSHOTS_DIR  # Use the same directory as where screenshots are saved
    deleted_files = []

    if "results" in test_data:
        for ip, result in test_data["results"].items():
            # Try two methods to find the screenshot
            screenshot_paths = []

            # Method 1: Extract filename from the stored screenshot path
            if "screenshot" in result and result["screenshot"]:
                screenshot_filename = os.path.basename(result["screenshot"])
                screenshot_paths.append(os.path.join(screenshots_dir, screenshot_filename))

            # Method 2: Construct filename based on naming pattern
            expected_filename = f"{test_id}_{ip.replace('.', '_')}.jpg"
            screenshot_paths.append(os.path.join(screenshots_dir, expected_filename))

            # Try to delete using both possible paths
            for screenshot_path in screenshot_paths:
                try:
                    if os.path.exists(screenshot_path):
                        os.remove(screenshot_path)
                        deleted_files.append(os.path.basename(screenshot_path))
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Deleted screenshot: {screenshot_path}")
                        break  # Stop after successfully deleting
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error deleting screenshot {screenshot_path}: {str(e)}")

    # Delete the test from results
    del test_results[test_id]

    # Save updated results
    save_results()

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Deleted test {test_id} and {len(deleted_files)} screenshots")

    return jsonify({
        "status": "success",
        "message": f"Test deleted successfully",
        "deleted_screenshots": len(deleted_files)
    })

@app.route('/api/results')
def get_all_results():
    """Get all test results"""
    # No lock needed for reading
    return jsonify(copy.deepcopy(test_results))


@app.route('/api/channels')
def get_channels():
    """Get all successful TV channels with group information and filtering"""
    # Get filter parameters
    group_filter = request.args.get('group', 'all')
    resolution_filter = request.args.get('resolution', 'all')
    connectivity_filter = request.args.get('connectivity', 'all')
    search_filter = request.args.get('search', '').lower()

    channels_with_groups = copy.deepcopy(tv_channels)

    # Add group information to each channel
    for ip, channel in channels_with_groups.items():
        channel_groups = []
        for group_id, group in groups.items():
            if ip in group.get('channels', []):
                channel_groups.append({
                    'id': group_id,
                    'name': group['name']
                })
        channel['groups'] = channel_groups

    # Calculate statistics BEFORE filtering (for filter counts)
    stats = {
        'total': len(channels_with_groups),
        'resolution': {
            '4k': 0,
            '1080': 0,
            '720': 0,
            'unknown': 0
        },
        'connectivity': {
            'online': 0,
            'offline': 0,
            'failed': 0,
            'testing': 0,
            'untested': 0
        },
        'groups': {}
    }

    for ip, channel in channels_with_groups.items():
        # Count resolutions
        resolution = channel.get('resolution', '')
        if resolution:
            try:
                width_str, height_str = resolution.split('x')
                width = int(width_str)
                height = int(height_str)
                is_720p = (width == 720 and height == 576) or (width >= 1280 and width < 1920)

                if width >= 3840:
                    stats['resolution']['4k'] += 1
                elif width >= 1920 and width < 3840:
                    stats['resolution']['1080'] += 1
                elif is_720p:
                    stats['resolution']['720'] += 1
            except:
                stats['resolution']['unknown'] += 1
        else:
            stats['resolution']['unknown'] += 1

        # Count connectivity
        connectivity = channel.get('connectivity', 'untested')
        if connectivity in stats['connectivity']:
            stats['connectivity'][connectivity] += 1

        # Count groups
        channel_groups = channel.get('groups', [])
        for group in channel_groups:
            group_id = group['id']
            if group_id not in stats['groups']:
                # Get sort_order from groups global variable
                sort_order = groups.get(group_id, {}).get('sort_order', 9999)
                stats['groups'][group_id] = {
                    'name': group['name'],
                    'count': 0,
                    'sort_order': sort_order
                }
            stats['groups'][group_id]['count'] += 1

    # Count ungrouped channels
    ungrouped_count = sum(1 for ch in channels_with_groups.values() if not ch.get('groups'))
    if ungrouped_count > 0:
        stats['groups']['ungrouped'] = {
            'name': 'Ungrouped',
            'count': ungrouped_count,
            'sort_order': 10000  # Ungrouped always last
        }

    # Apply filters
    filtered_list = []

    for ip, channel in channels_with_groups.items():
        # Group filter
        if group_filter != 'all':
            channel_group_ids = [g['id'] for g in channel.get('groups', [])]
            if group_filter == 'ungrouped':
                if len(channel_group_ids) > 0:
                    continue
            else:
                if group_filter not in channel_group_ids:
                    continue

        # Connectivity filter
        if connectivity_filter != 'all':
            connectivity = channel.get('connectivity', 'untested')
            if connectivity_filter == 'online' and connectivity != 'online':
                continue
            elif connectivity_filter == 'offline' and connectivity != 'offline':
                continue
            elif connectivity_filter == 'failed' and connectivity != 'failed':
                continue
            elif connectivity_filter == 'testing' and connectivity != 'testing':
                continue
            elif connectivity_filter == 'untested' and connectivity != 'untested':
                continue

        # Resolution filter
        if resolution_filter != 'all':
            resolution = channel.get('resolution', '')
            if resolution_filter == 'unknown':
                if resolution:
                    continue
            else:
                if not resolution:
                    continue
                try:
                    width_str, height_str = resolution.split('x')
                    width = int(width_str)
                    height = int(height_str)

                    is_720p = (width == 720 and height == 576) or (width >= 1280 and width < 1920)

                    if resolution_filter == '4k' and width < 3840:
                        continue
                    elif resolution_filter == '1080' and (width < 1920 or width >= 3840):
                        continue
                    elif resolution_filter == '720' and not is_720p:
                        continue
                except:
                    if resolution_filter != 'unknown':
                        continue

        # Search filter (IP or channel name)
        if search_filter:
            channel_name = channel.get('name', '').lower()
            if search_filter not in ip and search_filter not in channel_name:
                continue

        filtered_list.append((ip, channel))

    # Sort filtered channels
    # Sorting rules:
    # 1. Group sort order (grouped channels first, sorted by group order)
    # 2. Resolution (higher resolution first within same group)
    # 3. Channel name (natural sorting for names with numbers)
    # 4. Test status (test_status='failed' channels go to the bottom)
    def sort_key(item):
        ip, channel = item

        # 1. Group sort order - get minimum sort_order from all groups this channel belongs to
        min_sort_order = 9999
        for group in channel.get('groups', []):
            group_id = group['id']
            if group_id in groups:
                sort_order = groups[group_id].get('sort_order', 9999)
                if sort_order < min_sort_order:
                    min_sort_order = sort_order

        # 2. Resolution (descending - higher resolution first)
        resolution = channel.get('resolution', '')
        resolution_width = 0
        if resolution:
            try:
                resolution_width = -int(resolution.split('x')[0])
            except:
                resolution_width = 0

        # 3. Channel name (empty names go last within same group)
        # Use natural sorting for names with numbers (e.g., CCTV1, CCTV2, CCTV11)
        name = channel.get('name', '').strip()
        if not name:
            name_order = (1, [])  # Empty names go last
        else:
            # Split name into text and number parts for natural sorting
            import re
            parts = re.split(r'(\d+)', name.lower())
            # Convert numeric parts to integers for proper sorting
            sorted_parts = []
            for part in parts:
                if part.isdigit():
                    sorted_parts.append((0, int(part)))  # (0, num) for numbers
                else:
                    sorted_parts.append((1, part))  # (1, str) for text
            name_order = (0, sorted_parts)  # Names with content come first

        # 4. Test status - failed tests go last
        test_status = channel.get('test_status', 'success')
        test_status_order = 1 if test_status == 'failed' else 0

        return (min_sort_order, resolution_width, name_order, test_status_order)

    sorted_list = sorted(filtered_list, key=sort_key)

    # Convert to list of objects to preserve order (dict loses order in JSON)
    filtered_channels_list = [
        {"ip": ip, **channel} for ip, channel in sorted_list
    ]

    return jsonify({
        "status": "success",
        "channels": filtered_channels_list,
        "stats": stats
    })



@app.route('/api/channels/update', methods=['POST'])
def update_channel_name():
    """Update channel information"""
    data = request.json
    ip = data.get('ip')

    if not ip:
        return jsonify({"status": "error", "message": "IP required"}), 400

    # No lock needed for dictionary update
    if ip in tv_channels:
        # Update any provided fields
        if 'name' in data:
            tv_channels[ip]['name'] = data['name']
        if 'tvg_id' in data:
            tv_channels[ip]['tvg_id'] = data.get('tvg_id', '')
        if 'group' in data:
            tv_channels[ip]['group'] = data.get('group', '')
        if 'playback' in data:
            tv_channels[ip]['playback'] = data.get('playback', '')
        if 'catchup' in data:
            tv_channels[ip]['catchup'] = data.get('catchup', '')
        if 'logo' in data:
            tv_channels[ip]['logo'] = data.get('logo', '')

        save_channels()
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Channel not found"}), 404


@app.route('/api/channels/upload-logo', methods=['POST'])
def upload_channel_logo():
    """Upload logo for a channel"""
    ip = request.form.get('ip')

    if not ip:
        return jsonify({"status": "error", "message": "IP required"}), 400

    if 'logo' not in request.files:
        return jsonify({"status": "error", "message": "No logo file provided"}), 400

    file = request.files['logo']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400

    # Create logos directory if not exists
    logos_dir = os.path.join(os.path.dirname(__file__), 'logos')
    os.makedirs(logos_dir, exist_ok=True)

    # Save logo with IP-based filename
    ext = os.path.splitext(file.filename)[1] or '.png'
    filename = f"{ip.replace('.', '_')}{ext}"
    filepath = os.path.join(logos_dir, filename)
    file.save(filepath)

    # Update channel logo path
    if ip in tv_channels:
        tv_channels[ip]['logo'] = f"/logos/{filename}"
        save_channels()
        return jsonify({"status": "success", "logo": f"/logos/{filename}"})
    else:
        return jsonify({"status": "error", "message": "Channel not found"}), 404

@app.route('/logos/<path:filename>')
def serve_logo(filename):
    """Serve logo files"""
    logos_dir = os.path.join(os.path.dirname(__file__), 'logos')
    return send_from_directory(logos_dir, filename)

# Groups management functions
def load_groups():
    """Load groups from database"""
    try:
        return db.get_all_groups()
    except Exception as e:
        print(f"Error loading groups: {str(e)}")
        return {}

def save_groups():
    """Save groups to database"""
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Saving {len(groups)} groups to database...")
        # Log channel counts for debugging
        for gid, gdata in list(groups.items())[:3]:
            print(f"  Group {gdata.get('name', '')}: {len(gdata.get('channels', []))} channels")
        db.save_groups(groups)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Groups saved successfully")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error saving groups: {str(e)}")
        import traceback
        traceback.print_exc()

@app.route('/api/groups')
def get_groups():
    """Get all groups"""
    return jsonify({"status": "success", "groups": copy.deepcopy(groups)})

@app.route('/api/groups/create', methods=['POST'])
def create_group():
    """Create a new group"""
    data = request.json
    group_name = data.get('name')

    if not group_name:
        return jsonify({"status": "error", "message": "Group name required"}), 400

    # Generate unique ID
    group_id = str(uuid.uuid4())

    # Find max sort order
    max_sort = max([g.get('sort_order', 0) for g in groups.values()]) if groups else 0

    groups[group_id] = {
        'name': group_name,
        'channels': [],  # List of channel IPs
        'created': datetime.now().isoformat(),
        'sort_order': max_sort + 1
    }
    save_groups()

    return jsonify({"status": "success", "group_id": group_id})

@app.route('/api/groups/<group_id>', methods=['DELETE'])
def delete_group(group_id):
    """Delete a group"""
    if group_id not in groups:
        return jsonify({"status": "error", "message": "Group not found"}), 404

    del groups[group_id]
    save_groups()

    return jsonify({"status": "success"})

@app.route('/api/groups/<group_id>/rename', methods=['POST'])
def rename_group(group_id):
    """Rename a group"""
    if group_id not in groups:
        return jsonify({"status": "error", "message": "Group not found"}), 404

    data = request.json
    new_name = data.get('name')

    if not new_name:
        return jsonify({"status": "error", "message": "New name required"}), 400

    groups[group_id]['name'] = new_name
    save_groups()

    return jsonify({"status": "success"})

@app.route('/api/groups/reorder', methods=['POST'])
def reorder_groups():
    """Update groups sort order"""
    data = request.json
    order_list = data.get('order', [])

    if not order_list:
        return jsonify({"status": "error", "message": "Order list required"}), 400

    # Update sort order for each group
    for index, group_id in enumerate(order_list):
        if group_id in groups:
            groups[group_id]['sort_order'] = index + 1

    save_groups()

    return jsonify({"status": "success"})

@app.route('/api/groups/<group_id>/channels', methods=['POST'])
def add_channels_to_group(group_id):
    """Add channels to a group"""
    if group_id not in groups:
        return jsonify({"status": "error", "message": "Group not found"}), 404

    data = request.json
    channel_ips = data.get('channels', [])

    if not channel_ips:
        return jsonify({"status": "error", "message": "No channels provided"}), 400

    # Add unique channels only
    existing_channels = set(groups[group_id]['channels'])
    for ip in channel_ips:
        if ip not in existing_channels:
            groups[group_id]['channels'].append(ip)

    save_groups()

    return jsonify({"status": "success", "added": len(channel_ips)})

@app.route('/api/groups/<group_id>/channels', methods=['DELETE'])
def remove_channels_from_group(group_id):
    """Remove channels from a group"""
    if group_id not in groups:
        return jsonify({"status": "error", "message": "Group not found"}), 404

    data = request.json
    channel_ips = data.get('channels', [])

    if not channel_ips:
        return jsonify({"status": "error", "message": "No channels provided"}), 400

    # Remove specified channels
    groups[group_id]['channels'] = [ip for ip in groups[group_id]['channels'] if ip not in channel_ips]
    save_groups()

    return jsonify({"status": "success", "removed": len(channel_ips)})

@app.route('/api/channels/import', methods=['POST'])
def import_channels():
    """Import channels from M3U file"""
    global tv_channels, groups

    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No file selected"}), 400

        # Read M3U content
        content = file.read().decode('utf-8')

        # Parse M3U
        parsed_channels = parse_m3u(content)

        if not parsed_channels:
            return jsonify({"status": "error", "message": "No valid channels found in M3U file"}), 400

        # Import channels
        imported_count = 0
        updated_count = 0
        created_groups = []
        new_channel_ips = []  # Track new channels for highlighting

        for ch in parsed_channels:
            ip = ch['ip']
            is_new = ip not in tv_channels

            # Get existing channel data if exists
            existing = tv_channels.get(ip, {})

            # Smart merge: use imported value if not empty, otherwise keep existing
            tv_channels[ip] = {
                'name': ch['name'] if ch['name'] else existing.get('name', ''),
                'tvg_id': ch['tvg_id'] if ch['tvg_id'] else existing.get('tvg_id', ''),
                'url': ch['url'] if ch['url'] else existing.get('url', ''),
                'screenshot': existing.get('screenshot', ''),  # Always preserve screenshot
                'timestamp': datetime.now().isoformat(),
                'resolution': existing.get('resolution', ''),  # Always preserve resolution
                'group': ch['group'] if ch['group'] else existing.get('group', ''),
                'logo': ch['logo'] if ch['logo'] else existing.get('logo', ''),
                'catchup': ch['catchup'] if ch['catchup'] else existing.get('catchup', ''),
                'playback': ch['playback'] if ch['playback'] else existing.get('playback', '')
            }

            if is_new:
                imported_count += 1
                new_channel_ips.append(ip)
            else:
                updated_count += 1

            # Auto-create group if not exists
            if ch['group']:
                group_exists = False
                target_group_id = None

                for g_id, g_data in groups.items():
                    if g_data['name'] == ch['group']:
                        group_exists = True
                        target_group_id = g_id
                        break

                if not group_exists:
                    target_group_id = str(uuid.uuid4())
                    max_sort = max([g.get('sort_order', 0) for g in groups.values()]) if groups else 0
                    groups[target_group_id] = {
                        'name': ch['group'],
                        'channels': [],
                        'created': datetime.now().isoformat(),
                        'sort_order': max_sort + 1
                    }
                    created_groups.append(ch['group'])

                # Remove channel from all other groups first (覆盖逻辑)
                for g_id, g_data in groups.items():
                    if g_id != target_group_id and ip in g_data.get('channels', []):
                        g_data['channels'].remove(ip)

                # Add to target group
                if target_group_id and ip not in groups[target_group_id].get('channels', []):
                    groups[target_group_id]['channels'].append(ip)

        # Save all changes
        save_channels()
        save_groups()

        return jsonify({
            "status": "success",
            "imported": imported_count,
            "updated": updated_count,
            "total": len(parsed_channels),
            "groups_created": len(set(created_groups)),
            "new_channels": new_channel_ips  # Return list of new channel IPs for highlighting
        })

    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error importing M3U: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/metadata/sync', methods=['POST'])
def sync_metadata():
    """Sync metadata from multiple online sources (M3U, Markdown) by matching channel names"""
    global tv_channels

    try:
        # Load config to get metadata source URL(s)
        config = load_config()
        metadata_urls_str = config.get('metadata_source_url', '')

        if not metadata_urls_str:
            return jsonify({"status": "error", "message": "Metadata source URL not configured"}), 400

        # Split multiple URLs (support comma and newline as separators)
        metadata_urls = [url.strip() for url in metadata_urls_str.replace('\n', ',').split(',') if url.strip()]

        if not metadata_urls:
            return jsonify({"status": "error", "message": "No valid URLs found"}), 400

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting metadata sync from {len(metadata_urls)} URL(s)")

        # Merged metadata map: {channel_name_lower: {logo, catchup, playback, tvg_id, ...}}
        metadata_map = {}
        url_stats = []  # Track stats for each URL

        # Process each URL
        for url_index, metadata_url in enumerate(metadata_urls, 1):
            try:
                # Convert GitHub URL to raw URL if needed
                original_url = metadata_url
                if 'github.com' in metadata_url and '/blob/' in metadata_url:
                    metadata_url = metadata_url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')

                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{url_index}/{len(metadata_urls)}] Downloading from: {metadata_url}")

                # Download content
                response = requests.get(metadata_url, timeout=30)
                response.raise_for_status()
                content = response.text

                # Skip XML files (EPG data)
                if '.xml' in metadata_url.lower():
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Format: XML (EPG) - skipping metadata sync")
                    url_stats.append({
                        'url': original_url,
                        'format': 'XML (EPG)',
                        'parsed': 0
                    })
                    continue

                # Detect format: M3U or Markdown
                is_m3u = False
                is_markdown = False

                # Check by URL extension
                if '.m3u' in metadata_url.lower() or '.m3u8' in metadata_url.lower():
                    is_m3u = True
                elif '.md' in metadata_url.lower() or 'readme' in metadata_url.lower():
                    is_markdown = True
                else:
                    # Detect by content
                    if '#EXTINF' in content or '#EXTM3U' in content:
                        is_m3u = True
                    elif re.search(r'.+?[：:]\s*\d+', content):  # Pattern: "name: number"
                        is_markdown = True

                # Parse based on detected format
                parsed_count = 0
                if is_m3u:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Format: M3U")
                    parsed_channels = parse_m3u(content)

                    for ch in parsed_channels:
                        name_lower = ch['name'].lower().strip()
                        if name_lower:
                            # Only add fields that don't exist yet (first URL wins)
                            if name_lower not in metadata_map:
                                metadata_map[name_lower] = {}

                            # Update only if field is empty
                            if not metadata_map[name_lower].get('name'):
                                metadata_map[name_lower]['name'] = ch.get('name', '')
                            if not metadata_map[name_lower].get('logo') and ch.get('logo'):
                                metadata_map[name_lower]['logo'] = ch.get('logo', '')
                            if not metadata_map[name_lower].get('catchup') and ch.get('catchup'):
                                metadata_map[name_lower]['catchup'] = ch.get('catchup', '')
                            if not metadata_map[name_lower].get('playback') and ch.get('playback'):
                                metadata_map[name_lower]['playback'] = ch.get('playback', '')
                            if not metadata_map[name_lower].get('tvg_id') and ch.get('tvg_id'):
                                metadata_map[name_lower]['tvg_id'] = ch.get('tvg_id', '')
                            if not metadata_map[name_lower].get('group') and ch.get('group'):
                                metadata_map[name_lower]['group'] = ch.get('group', '')

                            parsed_count += 1

                    url_stats.append({
                        'url': original_url,
                        'format': 'M3U',
                        'parsed': len(parsed_channels)
                    })

                elif is_markdown:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Format: Markdown")
                    channels_map = parse_markdown_channels(content)

                    for name, ch_data in channels_map.items():
                        name_lower = name.lower().strip()
                        if name_lower:
                            # Only add fields that don't exist yet (first URL wins)
                            if name_lower not in metadata_map:
                                metadata_map[name_lower] = {}

                            # Update only if field is empty
                            if not metadata_map[name_lower].get('name'):
                                metadata_map[name_lower]['name'] = ch_data.get('name', '')
                            if not metadata_map[name_lower].get('tvg_id') and ch_data.get('tvg_id'):
                                metadata_map[name_lower]['tvg_id'] = ch_data.get('tvg_id', '')

                            parsed_count += 1

                    url_stats.append({
                        'url': original_url,
                        'format': 'Markdown',
                        'parsed': len(channels_map)
                    })

                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Format: Unknown - skipping")
                    url_stats.append({
                        'url': original_url,
                        'format': 'Unknown',
                        'parsed': 0
                    })

                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Parsed: {parsed_count} entries")

            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]   Error processing URL: {str(e)}")
                url_stats.append({
                    'url': original_url,
                    'format': 'Error',
                    'parsed': 0,
                    'error': str(e)
                })
                continue

        # Match and update existing channels by name
        matched_count = 0
        updated_count = 0
        matched_names = set()

        for ip, channel in tv_channels.items():
            channel_name = channel.get('name', '').lower().strip()

            if channel_name and channel_name in metadata_map:
                matched_count += 1
                matched_names.add(channel_name)
                metadata = metadata_map[channel_name]

                # Track if any field was actually updated
                updated = False
                updated_fields = []

                # Update logo
                if metadata.get('logo') and metadata['logo'] != channel.get('logo', ''):
                    channel['logo'] = metadata['logo']
                    updated = True
                    updated_fields.append('logo')

                # Update catchup
                if metadata.get('catchup') and metadata['catchup'] != channel.get('catchup', ''):
                    channel['catchup'] = metadata['catchup']
                    updated = True
                    updated_fields.append('catchup')

                # Update playback (catchup-source)
                if metadata.get('playback') and metadata['playback'] != channel.get('playback', ''):
                    channel['playback'] = metadata['playback']
                    updated = True
                    updated_fields.append('playback')

                # Update tvg_id (NEW)
                if metadata.get('tvg_id') and metadata['tvg_id'] != channel.get('tvg_id', ''):
                    channel['tvg_id'] = metadata['tvg_id']
                    updated = True
                    updated_fields.append('tvg_id')

                if updated:
                    updated_count += 1
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updated channel '{channel.get('name')}' ({ip}): {', '.join(updated_fields)}")

        # Save updated channels to database
        save_channels()

        # Print unmatched channels from metadata
        unmatched_from_url = set(metadata_map.keys()) - matched_names
        if unmatched_from_url:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unmatched channels in metadata (not in local): {len(unmatched_from_url)}")

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Metadata sync completed: {matched_count} matched, {updated_count} updated")

        return jsonify({
            "status": "success",
            "urls_processed": len(metadata_urls),
            "url_stats": url_stats,
            "total_metadata": len(metadata_map),
            "matched": matched_count,
            "updated": updated_count,
            "unmatched": len(tv_channels) - matched_count
        })

    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error syncing metadata: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


def generate_m3u_content(use_external_url=False):
    """Generate M3U content for ONLINE channels, sorted same as frontend list

    Args:
        use_external_url: If True, replace internal URLs with external URLs
    """
    # Load config to get EPG URL and URL replacement settings
    config = load_config()
    epg_url = config.get('epg_url', '')
    base_url = config.get('base_url', '')
    external_base_url = config.get('external_base_url', '')

    # Build M3U header with EPG URL if configured
    if epg_url:
        # Add .gz to the EPG URL
        epg_url_gz = epg_url + '.gz'
        m3u_content = f'#EXTM3U url-tvg="{epg_url_gz}"\n\n'
    else:
        m3u_content = "#EXTM3U\n\n"

    # Filter: Only export channels with connectivity='online'
    filtered_list = []
    for ip, channel in tv_channels.items():
        connectivity = channel.get('connectivity', 'untested')
        if connectivity == 'online':
            filtered_list.append((ip, channel))

    # Sort channels using the SAME logic as frontend list
    # Sorting rules:
    # 1. Group sort order (grouped channels first, sorted by group order)
    # 2. Resolution (higher resolution first within same group)
    # 3. Channel name (natural sorting for names with numbers)
    # 4. Test status (test_status='failed' channels go to the bottom)
    def sort_key(item):
        ip, channel = item

        # 1. Group sort order - get minimum sort_order from all groups this channel belongs to
        min_sort_order = 9999
        for group_id, group in groups.items():
            if ip in group.get('channels', []):
                sort_order = group.get('sort_order', 9999)
                if sort_order < min_sort_order:
                    min_sort_order = sort_order

        # 2. Resolution (descending - higher resolution first)
        resolution = channel.get('resolution', '')
        resolution_width = 0
        if resolution:
            try:
                resolution_width = -int(resolution.split('x')[0])
            except:
                resolution_width = 0

        # 3. Channel name (empty names go last within same group)
        # Use natural sorting for names with numbers (e.g., CCTV1, CCTV2, CCTV11)
        name = channel.get('name', '').strip()
        if not name:
            name_order = (1, [])  # Empty names go last
        else:
            # Split name into text and number parts for natural sorting
            import re
            parts = re.split(r'(\d+)', name.lower())
            # Convert numeric parts to integers for proper sorting
            sorted_parts = []
            for part in parts:
                if part.isdigit():
                    sorted_parts.append((0, int(part)))  # (0, num) for numbers
                else:
                    sorted_parts.append((1, part))  # (1, str) for text
            name_order = (0, sorted_parts)  # Names with content come first

        # 4. Test status - failed tests go last
        test_status = channel.get('test_status', 'success')
        test_status_order = 1 if test_status == 'failed' else 0

        return (min_sort_order, resolution_width, name_order, test_status_order)

    sorted_list = sorted(filtered_list, key=sort_key)

    # Generate M3U content
    for ip, channel in sorted_list:
        name = channel.get('name', 'Unknown')
        url = channel.get('url', '')

        if url:
            # Replace with external base URL if requested
            if use_external_url and external_base_url:
                # Simply replace {ip} in external_base_url with the IP from channels table
                if '{ip}' in external_base_url:
                    url = external_base_url.replace('{ip}', ip)

            # Build EXTINF line with all available metadata
            extinf_parts = ["#EXTINF:-1"]

            # Add tvg-id if available
            tvg_id = channel.get('tvg_id', '')
            if tvg_id:
                extinf_parts.append(f'tvg-id="{tvg_id}"')

            # Use group from channel data, or find from groups
            group = channel.get('group', '')
            if not group:
                # Check if channel is in any group
                for group_id, group_data in groups.items():
                    if ip in group_data.get('channels', []):
                        group = group_data['name']
                        break

            if group:
                extinf_parts.append(f'group-title="{group}"')

            # Add tvg-logo if available
            logo = channel.get('logo', '')
            if logo:
                extinf_parts.append(f'tvg-logo="{logo}"')

            # Add catchup if available
            catchup = channel.get('catchup', '')
            if catchup:
                extinf_parts.append(f'catchup="{catchup}"')

            # Add catchup-source if available
            playback = channel.get('playback', '')
            if playback:
                extinf_parts.append(f'catchup-source="{playback}"')

            # Join parts and add channel name
            extinf_line = ' '.join(extinf_parts) + f",{name}"

            m3u_content += f"{extinf_line}\n{url}\n\n"

    return m3u_content


@app.route('/api/channels/export')
def export_channels():
    """Export ONLINE channels as M3U file (download)"""
    m3u_content = generate_m3u_content()

    response = app.response_class(
        response=m3u_content,
        status=200,
        mimetype='text/plain'
    )
    response.headers['Content-Disposition'] = f'attachment; filename=channels_{datetime.now().strftime("%Y%m%d")}.m3u'
    return response


@app.route('/m3u')
def get_m3u():
    """Get M3U content (direct view, not download)"""
    m3u_content = generate_m3u_content()

    response = app.response_class(
        response=m3u_content,
        status=200,
        mimetype='text/plain; charset=utf-8'
    )
    return response


@app.route('/net')
def get_net():
    """Get M3U content with external URLs (direct view, not download)"""
    m3u_content = generate_m3u_content(use_external_url=True)

    response = app.response_class(
        response=m3u_content,
        status=200,
        mimetype='text/plain; charset=utf-8'
    )
    return response


@app.route('/epg')
def get_epg():
    """Get EPG XML content from configured URL"""
    config = load_config()
    epg_url = config.get('epg_url', '')

    if not epg_url:
        return app.response_class(
            response='<?xml version="1.0" encoding="UTF-8"?>\n<tv></tv>',
            status=200,
            mimetype='application/xml; charset=utf-8'
        )

    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching EPG from: {epg_url}")

        # Fetch EPG XML from the configured URL with longer timeout for large files
        response = requests.get(epg_url, timeout=60)
        response.raise_for_status()

        xml_content = response.text

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] EPG fetched successfully, size: {len(xml_content)} bytes")

        return app.response_class(
            response=xml_content,
            status=200,
            mimetype='text/plain; charset=utf-8'
        )
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error fetching EPG: {str(e)}")
        error_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<tv><!-- Error fetching EPG: {str(e)} --></tv>'
        return app.response_class(
            response=error_xml,
            status=200,
            mimetype='application/xml; charset=utf-8'
        )


@app.route('/api/channels/test-connectivity', methods=['POST'])
def test_channel_connectivity():
    """Start background task to test connectivity of channels"""
    global tv_channels, connectivity_tasks

    data = request.json
    ips = data.get('ips', [])  # Can be single IP or list of IPs

    if not ips:
        return jsonify({"status": "error", "message": "No IPs provided"}), 400

    # Ensure ips is a list
    if isinstance(ips, str):
        ips = [ips]

    config = load_config()

    # Generate a test ID for this connectivity test batch
    task_id = f"connectivity_{str(uuid.uuid4())}"

    # Initialize task status
    connectivity_tasks[task_id] = {
        "status": "running",
        "total": len(ips),
        "completed": 0,
        "results": {},
        "start_time": datetime.now().isoformat()
    }

    # Function to test a single channel connectivity with full stream test
    def test_single_connectivity(ip, task_id):
        if ip not in tv_channels:
            tv_channels[ip]['connectivity'] = 'offline'
            tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
            tv_channels[ip]['timestamp'] = datetime.now().isoformat()
            return {"ip": ip, "connectivity": "offline", "timestamp": tv_channels[ip]['timestamp'], "message": "Channel not found"}

        channel = tv_channels[ip]
        url = channel.get('url', '')

        if not url:
            tv_channels[ip]['connectivity'] = 'offline'
            tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
            tv_channels[ip]['timestamp'] = datetime.now().isoformat()
            return {"ip": ip, "connectivity": "offline", "timestamp": tv_channels[ip]['timestamp'], "message": "No URL"}

        try:
            timeout = config.get("timeout") or 10
            if isinstance(timeout, str):
                try:
                    timeout = int(timeout)
                except:
                    timeout = 10

            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"connectivity_{ip.replace('.', '_')}.jpg")

            # Build FFmpeg command for full stream test
            cmd = ["ffmpeg", "-y"]

            # Add timeout parameter for network streams (in microseconds)
            cmd.extend(["-timeout", str(timeout * 1000000)])

            # Add network timeout and analysis parameters BEFORE input
            cmd.extend([
                "-analyzeduration", "3000000",  # 3 seconds to analyze stream
                "-probesize", "5000000"  # 5MB probe size
            ])

            # Add RTP-specific timeout if it's an RTP URL
            if "rtp" in url.lower():
                cmd.extend(["-rw_timeout", str(timeout * 1000000)])

            # Add custom parameters if specified
            custom_params = config.get("custom_params", "")
            if custom_params and custom_params.strip():
                import shlex
                try:
                    custom_args = shlex.split(custom_params)
                    cmd.extend(custom_args)
                except Exception as e:
                    print(f"[Connectivity Test] Error parsing custom params: {e}")

            # Probe stream to detect resolution for 4K optimization
            probe_cmd = [
                "ffmpeg",
                "-hide_banner",
                "-analyzeduration", "5000000",
                "-probesize", "10000000",
                "-t", "3",
                "-i", url,
                "-f", "null",
                "-"
            ]

            detected_resolution = None
            is_4k = False
            try:
                probe_process = subprocess.Popen(
                    probe_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                probe_stdout, probe_stderr = probe_process.communicate(timeout=8)

                if probe_stderr:
                    import re
                    resolution_pattern = r'Stream.*Video.*\s(\d{3,4}x\d{3,4})'
                    match = re.search(resolution_pattern, probe_stderr)
                    if match:
                        detected_resolution = match.group(1)
                        width, height = map(int, detected_resolution.split('x'))
                        is_4k = width >= 3840
                        print(f"[Connectivity Test] Detected resolution: {detected_resolution} (4K: {is_4k})")
            except Exception as e:
                print(f"[Connectivity Test] Probe failed, using default settings: {e}")

            # Add input URL
            cmd.extend(["-i", url])

            # For 4K streams, capture first frame without scaling (keep original resolution)
            if is_4k:
                cmd.extend([
                    "-frames:v", "1",
                    "-q:v", "1",
                    "-vf", "yadif",
                    "-f", "image2",
                    screenshot_path
                ])
                print(f"[Connectivity Test] Using 4K capture mode (no scaling)")
            else:
                cmd.extend([
                    "-frames:v", "1",
                    "-q:v", "1",
                    "-vf", "yadif",
                    "-s", "1920x1080",
                    "-f", "image2",
                    screenshot_path
                ])
                print(f"[Connectivity Test] Using standard capture mode (1080p)")

            # Execute FFmpeg with timeout
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)

                # Parse resolution from stderr first
                resolution = None
                if stderr:
                    import re
                    resolution_pattern = r'Stream.*Video.*\s(\d{3,4}x\d{3,4})'
                    match = re.search(resolution_pattern, stderr)
                    if match:
                        resolution = match.group(1)
                        try:
                            width, height = map(int, resolution.split('x'))
                            if width > 0 and height > 0:
                                print(f"[Connectivity Test] Detected resolution from FFmpeg: {resolution}")
                            else:
                                resolution = None
                        except:
                            resolution = None

                # For 4K streams, if we detected resolution in stderr, consider it successful even without screenshot
                if is_4k and resolution and not os.path.exists(screenshot_path):
                    print(f"[Connectivity Test] 4K stream: FFmpeg detected stream info, marking as online even without screenshot")
                    tv_channels[ip]['connectivity'] = 'online'
                    tv_channels[ip]['resolution'] = resolution
                    tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                    tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                    return {
                        "ip": ip,
                        "connectivity": "online",
                        "screenshot": None,
                        "resolution": resolution,
                        "timestamp": tv_channels[ip]['timestamp'],
                        "message": "4K stream detected (no screenshot)"
                    }

                if process.returncode == 0 and os.path.exists(screenshot_path):
                    # Successfully captured screenshot
                    tv_channels[ip]['screenshot'] = f"/screenshots/{os.path.basename(screenshot_path)}"

                    # Only mark as online if valid resolution was detected
                    if resolution:
                        tv_channels[ip]['resolution'] = resolution
                        tv_channels[ip]['connectivity'] = 'online'
                        tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                        tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                        return {
                            "ip": ip,
                            "connectivity": "online",
                            "screenshot": tv_channels[ip]['screenshot'],
                            "resolution": resolution,
                            "timestamp": tv_channels[ip]['timestamp']
                        }
                    else:
                        # No resolution detected - mark as failed
                        previous_connectivity = channel.get('connectivity', 'untested')
                        if previous_connectivity == 'online':
                            new_connectivity = 'offline'
                        else:
                            new_connectivity = previous_connectivity
                        tv_channels[ip]['connectivity'] = new_connectivity
                        tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                        tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                        return {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp'], "message": "No resolution detected"}
                else:
                    # Try lightweight probe as fallback
                    probe_cmd = [
                        "ffprobe",
                        "-v", "error",
                        "-show_entries", "stream=codec_type,width,height",
                        "-of", "default=noprint_wrappers=1"
                    ]

                    if "rtp" in url.lower() or "udp" in url.lower() or "http" in url.lower():
                        probe_cmd.extend(["-timeout", str(timeout * 1000000)])

                    probe_cmd.append(url)

                    try:
                        probe_process = subprocess.Popen(
                            probe_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            universal_newlines=True
                        )

                        probe_stdout, probe_stderr = probe_process.communicate(timeout=timeout)
                        combined_output = (probe_stdout or "") + (probe_stderr or "")

                        if "codec_type=video" in combined_output or "Video:" in combined_output:
                            # Stream is accessible but screenshot failed
                            tv_channels[ip]['connectivity'] = 'online'
                            tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                            tv_channels[ip]['timestamp'] = datetime.now().isoformat()

                            # Try to extract resolution
                            import re
                            width_match = re.search(r'width=(\d+)', combined_output)
                            height_match = re.search(r'height=(\d+)', combined_output)
                            if width_match and height_match:
                                resolution = f"{width_match.group(1)}x{height_match.group(1)}"
                                tv_channels[ip]['resolution'] = resolution

                            return {"ip": ip, "connectivity": "online", "timestamp": tv_channels[ip]['timestamp'], "note": "Screenshot failed but stream accessible"}
                        else:
                            # Test failed - set offline if previously online, otherwise keep current status
                            previous_connectivity = channel.get('connectivity', 'untested')
                            if previous_connectivity == 'online':
                                new_connectivity = 'offline'
                            else:
                                new_connectivity = previous_connectivity
                            tv_channels[ip]['connectivity'] = new_connectivity
                            tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                            tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                            return {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp']}

                    except (subprocess.TimeoutExpired, Exception):
                        if hasattr(locals().get('probe_process'), 'kill'):
                            try:
                                probe_process.kill()
                            except:
                                pass
                        # Test failed - set offline if previously online
                        previous_connectivity = channel.get('connectivity', 'untested')
                        if previous_connectivity == 'online':
                            new_connectivity = 'offline'
                        else:
                            new_connectivity = previous_connectivity
                        tv_channels[ip]['connectivity'] = new_connectivity
                        tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                        tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                        return {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp']}

            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.terminate()
                # Test failed - set offline if previously online
                previous_connectivity = channel.get('connectivity', 'untested')
                if previous_connectivity == 'online':
                    new_connectivity = 'offline'
                else:
                    new_connectivity = previous_connectivity
                tv_channels[ip]['connectivity'] = new_connectivity
                tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                return {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp'], "message": "Timeout"}

        except Exception as e:
            print(f"[Connectivity Test] Error testing {ip}: {str(e)}")
            # Test failed - set offline if previously online
            previous_connectivity = channel.get('connectivity', 'untested')
            if previous_connectivity == 'online':
                new_connectivity = 'offline'
            else:
                new_connectivity = previous_connectivity
            tv_channels[ip]['connectivity'] = new_connectivity
            tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
            tv_channels[ip]['timestamp'] = datetime.now().isoformat()
            return {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp'], "message": str(e)}

    # Background task to test all channels
    def run_connectivity_tests():
        """Run connectivity tests in background"""
        try:
            for i, ip in enumerate(ips):
                # Update testing status
                connectivity_tasks[task_id]["results"][ip] = {"status": "testing"}

                # Test the channel
                result = test_single_connectivity(ip, task_id)

                # Update task status
                connectivity_tasks[task_id]["results"][ip] = result
                connectivity_tasks[task_id]["completed"] = i + 1

                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connectivity test progress: {i + 1}/{len(ips)}")

            # Save updated channels
            save_channels()

            # Mark task as completed
            connectivity_tasks[task_id]["status"] = "completed"
            connectivity_tasks[task_id]["end_time"] = datetime.now().isoformat()

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connectivity test task {task_id} completed")

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error in connectivity test task: {str(e)}")
            connectivity_tasks[task_id]["status"] = "failed"
            connectivity_tasks[task_id]["error"] = str(e)
            connectivity_tasks[task_id]["end_time"] = datetime.now().isoformat()

    # Start background thread
    test_thread = threading.Thread(target=run_connectivity_tests, daemon=True)
    test_thread.start()

    # Return task ID immediately
    return jsonify({
        "status": "success",
        "task_id": task_id,
        "total": len(ips),
        "message": "Connectivity test started in background"
    })


@app.route('/api/channels/test-connectivity/status/<task_id>', methods=['GET'])
def get_connectivity_task_status(task_id):
    """Get status of connectivity test task"""
    global connectivity_tasks

    if task_id not in connectivity_tasks:
        return jsonify({"status": "error", "message": "Task not found"}), 404

    task = connectivity_tasks[task_id]

    # Return task status
    return jsonify({
        "status": "success",
        "task": {
            "task_id": task_id,
            "status": task.get("status"),
            "total": task.get("total"),
            "completed": task.get("completed"),
            "results": task.get("results", {}),
            "start_time": task.get("start_time"),
            "end_time": task.get("end_time"),
            "error": task.get("error")
        }
    })


@app.route('/api/channels/test-connectivity-sync', methods=['POST'])
def test_channel_connectivity_sync():
    """Synchronously test connectivity of a single channel - returns result immediately"""
    global tv_channels

    data = request.json
    ip = data.get('ip', '')

    if not ip:
        return jsonify({"status": "error", "message": "No IP provided"}), 400

    if ip not in tv_channels:
        return jsonify({"status": "error", "message": "Channel not found"}), 404

    config = load_config()
    channel = tv_channels[ip]
    url = channel.get('url', '')
    channel_name = channel.get('name', ip)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Testing channel: {channel_name} ({ip})")
    sys.stdout.flush()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] URL: {url}")
    sys.stdout.flush()

    if not url:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] No URL for {ip}")
        sys.stdout.flush()
        tv_channels[ip]['connectivity'] = 'offline'
        tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
        tv_channels[ip]['timestamp'] = datetime.now().isoformat()
        save_channels()
        return jsonify({"status": "success", "result": {"ip": ip, "connectivity": "offline", "timestamp": tv_channels[ip]['timestamp'], "message": "No URL"}})

    try:
        timeout = config.get("timeout") or 10
        if isinstance(timeout, str):
            try:
                timeout = int(timeout)
            except:
                timeout = 10

        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"connectivity_{ip.replace('.', '_')}.jpg")

        # Build FFmpeg command
        cmd = ["ffmpeg", "-y"]

        # Add timeout parameter for network streams (in microseconds)
        cmd.extend(["-timeout", str(timeout * 1000000)])

        cmd.extend([
            "-analyzeduration", "3000000",
            "-probesize", "5000000"
        ])

        if "rtp" in url.lower():
            cmd.extend(["-rw_timeout", str(timeout * 1000000)])

        custom_params = config.get("custom_params", "")
        if custom_params and custom_params.strip():
            import shlex
            try:
                custom_args = shlex.split(custom_params)
                cmd.extend(custom_args)
            except Exception as e:
                print(f"[Connectivity Test Sync] Error parsing custom params: {e}")

        # Probe for 4K detection
        probe_cmd = [
            "ffmpeg", "-hide_banner",
            "-analyzeduration", "5000000",
            "-probesize", "10000000",
            "-t", "3", "-i", url,
            "-f", "null", "-"
        ]

        detected_resolution = None
        is_4k = False
        try:
            probe_process = subprocess.Popen(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            probe_stdout, probe_stderr = probe_process.communicate(timeout=8)

            if probe_stderr:
                import re
                resolution_pattern = r'Stream.*Video.*\s(\d{3,4}x\d{3,4})'
                match = re.search(resolution_pattern, probe_stderr)
                if match:
                    detected_resolution = match.group(1)
                    width, height = map(int, detected_resolution.split('x'))
                    is_4k = width >= 3840
        except Exception as e:
            print(f"[Connectivity Test Sync] Probe failed: {e}")

        cmd.extend(["-i", url])

        if is_4k:
            # For 4K streams, capture first frame without scaling (keep original resolution)
            cmd.extend(["-frames:v", "1", "-q:v", "1", "-vf", "yadif", "-f", "image2", screenshot_path])
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Using 4K capture mode (no scaling)")
            sys.stdout.flush()
        else:
            # For standard streams, scale to 1080p
            cmd.extend(["-frames:v", "1", "-q:v", "1", "-vf", "yadif", "-s", "1920x1080", "-f", "image2", screenshot_path])
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Using standard capture mode (1080p)")
            sys.stdout.flush()

        # Print the actual command for debugging
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] FFmpeg command: {' '.join(cmd)}")
        sys.stdout.flush()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Executing FFmpeg command...")
        sys.stdout.flush()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        try:
            stdout, stderr = process.communicate(timeout=timeout)

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] FFmpeg return code: {process.returncode}")
            sys.stdout.flush()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Screenshot exists: {os.path.exists(screenshot_path)}")
            sys.stdout.flush()

            # Parse resolution from stderr first
            resolution = None
            if stderr:
                import re
                resolution_pattern = r'Stream.*Video.*\s(\d{3,4}x\d{3,4})'
                match = re.search(resolution_pattern, stderr)
                if match:
                    resolution = match.group(1)
                    try:
                        width, height = map(int, resolution.split('x'))
                        if width > 0 and height > 0:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Detected resolution from FFmpeg: {resolution}")
                            sys.stdout.flush()
                        else:
                            resolution = None
                    except:
                        resolution = None

            # For 4K streams, if we detected resolution in stderr, consider it successful even without screenshot
            if is_4k and resolution and not os.path.exists(screenshot_path):
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] 4K stream: FFmpeg detected stream info, marking as online even without screenshot")
                sys.stdout.flush()
                tv_channels[ip]['connectivity'] = 'online'
                tv_channels[ip]['resolution'] = resolution
                tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                save_channels()
                return jsonify({
                    "status": "success",
                    "result": {
                        "ip": ip,
                        "connectivity": "online",
                        "screenshot": None,
                        "resolution": resolution,
                        "name": tv_channels[ip].get('name', ''),
                        "timestamp": tv_channels[ip]['timestamp'],
                        "message": "4K stream detected (no screenshot)"
                    }
                })

            if process.returncode == 0 and os.path.exists(screenshot_path):
                tv_channels[ip]['screenshot'] = f"/screenshots/{os.path.basename(screenshot_path)}"

                # Use the resolution we already parsed above
                if resolution:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Success! Resolution: {resolution}")
                    sys.stdout.flush()
                    tv_channels[ip]['connectivity'] = 'online'
                    tv_channels[ip]['resolution'] = resolution
                    tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                    tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                    save_channels()
                    return jsonify({
                        "status": "success",
                        "result": {
                            "ip": ip,
                            "connectivity": "online",
                            "screenshot": tv_channels[ip]['screenshot'],
                            "resolution": resolution,
                            "name": tv_channels[ip].get('name', ''),
                            "timestamp": tv_channels[ip]['timestamp']
                        }
                    })
                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Screenshot captured but no resolution detected")
                    sys.stdout.flush()
                    if stderr:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] FFmpeg stderr (first 500 chars): {stderr[:500]}")
                        sys.stdout.flush()
                    previous_connectivity = channel.get('connectivity', 'untested')
                    new_connectivity = 'offline' if previous_connectivity == 'online' else previous_connectivity
                    tv_channels[ip]['connectivity'] = new_connectivity
                    tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                    tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                    save_channels()
                    return jsonify({"status": "success", "result": {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp'], "message": "No resolution detected"}})
            else:
                # FFmpeg failed or screenshot not created
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] FFmpeg failed or screenshot not created")
                sys.stdout.flush()
                if stderr:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] FFmpeg stderr:\n{stderr}")
                    sys.stdout.flush()
                previous_connectivity = channel.get('connectivity', 'untested')
                new_connectivity = 'offline' if previous_connectivity == 'online' else previous_connectivity
                tv_channels[ip]['connectivity'] = new_connectivity
                tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
                tv_channels[ip]['timestamp'] = datetime.now().isoformat()
                save_channels()
                return jsonify({"status": "success", "result": {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp'], "message": "FFmpeg failed"}})

        except subprocess.TimeoutExpired:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Test timed out after {timeout} seconds")
            sys.stdout.flush()
            process.kill()
            previous_connectivity = channel.get('connectivity', 'untested')
            new_connectivity = 'offline' if previous_connectivity == 'online' else previous_connectivity
            tv_channels[ip]['connectivity'] = new_connectivity
            tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
            tv_channels[ip]['timestamp'] = datetime.now().isoformat()
            save_channels()
            return jsonify({"status": "success", "result": {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp'], "message": "Timeout"}})

    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Connectivity Sync] Error testing {ip}: {str(e)}")
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        previous_connectivity = channel.get('connectivity', 'untested')
        new_connectivity = 'offline' if previous_connectivity == 'online' else previous_connectivity
        tv_channels[ip]['connectivity'] = new_connectivity
        tv_channels[ip]['connectivity_time'] = datetime.now().isoformat()
        tv_channels[ip]['timestamp'] = datetime.now().isoformat()
        save_channels()
        return jsonify({"status": "success", "result": {"ip": ip, "connectivity": new_connectivity, "timestamp": tv_channels[ip]['timestamp'], "message": str(e)}})


@app.route('/api/channels/clear-names', methods=['POST'])
def clear_channel_names():
    """Clear all channel names"""
    global tv_channels

    cleared_count = 0
    for ip in tv_channels:
        if tv_channels[ip].get('name'):
            tv_channels[ip]['name'] = ''
            cleared_count += 1

    save_channels()

    return jsonify({
        "status": "success",
        "cleared": cleared_count,
        "total": len(tv_channels)
    })

@app.route('/api/channels/recognize', methods=['POST'])
def recognize_channels():
    """Start AI recognition of channel names in background"""
    # Load configuration
    config = load_config()
    ai_config = config.get('ai_model', {})

    if not ai_config.get('enabled'):
        return jsonify({"status": "error", "message": "AI model not configured"})

    if not ai_config.get('api_url') or not ai_config.get('api_key'):
        return jsonify({"status": "error", "message": "Please configure AI model API URL and key"})

    # Find channels without names but with screenshots
    channels_to_recognize = []
    for ip, channel in tv_channels.items():
        if not channel.get('name') and channel.get('screenshot'):
            channels_to_recognize.append((ip, channel))

    if not channels_to_recognize:
        return jsonify({"status": "success", "message": "No channels need recognition", "recognized": 0, "total": 0})

    # Start background recognition
    def run_recognition():
        recognized_count = 0
        errors = []
        total = len(channels_to_recognize)

        print(f"[AI Recognition] Starting background recognition for {total} channels")

        for idx, (ip, channel) in enumerate(channels_to_recognize, 1):
            print(f"[AI Recognition] Processing {idx}/{total}: IP {ip}")
            try:
                # Read the screenshot file
                screenshot_path = os.path.join(os.path.dirname(__file__), channel['screenshot'].lstrip('/'))
                if not os.path.exists(screenshot_path):
                    errors.append(f"Screenshot not found for {ip}")
                    continue

                with open(screenshot_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')

                # Prepare the request to AI model
                headers = {
                    'Authorization': f'Bearer {ai_config["api_key"]}',
                    'Content-Type': 'application/json'
                }

                # Prepare payload for OpenRouter or other APIs
                # OpenRouter uses OpenAI-compatible format for all models
                if 'openrouter' in ai_config.get('api_url', '').lower():
                    # OpenRouter format (works for Claude, GPT-4V, etc.)
                    payload = {
                        "model": ai_config['model'],
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "观察图片中的台标或文字，识别这是哪个电视频道。只返回频道名称，如：CCTV1、湖南卫视、东方卫视等。有文字的以台标+文字为准，没有文字的以台标为准。如果无法识别，请返回'未知频道'。"
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}"
                                    }
                                }
                            ]
                        }],
                        "max_tokens": 20
                    }
                elif 'anthropic' in ai_config.get('api_url', '').lower():
                    # Native Anthropic API format
                    payload = {
                        "model": ai_config['model'],
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "观察图片中的台标或文字，识别这是哪个电视频道。只返回频道名称，如：CCTV1、湖南卫视、东方卫视等。有文字的以台标+文字为准，没有文字的以台标为准。如果无法识别，请返回'未知频道'。"
                                },
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": image_data
                                    }
                                }
                            ]
                        }],
                        "max_tokens": 20
                    }
                else:
                    # OpenAI API format (default)
                    payload = {
                        "model": ai_config.get('model', 'gpt-4-vision-preview'),
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "观察图片中的台标或文字，识别这是哪个电视频道。只返回频道名称，如：CCTV1、湖南卫视、东方卫视等。有文字的以台标+文字为准，没有文字的以台标为准。如果无法识别，请返回'未知频道'。"
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}"
                                    }
                                }
                            ]
                        }],
                        "max_tokens": 20
                    }

                # Send request to AI model
                print(f"[AI Recognition] Sending request for IP {ip}")
                response = requests.post(ai_config['api_url'], headers=headers, json=payload, timeout=30)

                if response.status_code == 200:
                    result = response.json()
                    print(f"[AI Recognition] Response for {ip}: {json.dumps(result, ensure_ascii=False)[:200]}")

                    # Extract channel name from response
                    channel_name = "未知频道"
                    if 'choices' in result and result['choices']:
                        # OpenAI/OpenRouter format
                        channel_name = result['choices'][0]['message']['content'].strip()
                    elif 'content' in result and isinstance(result['content'], list) and result['content']:
                        # Claude format
                        channel_name = result['content'][0].get('text', '').strip()
                    elif 'content' in result and isinstance(result['content'], str):
                        # Alternative format
                        channel_name = result['content'].strip()

                    print(f"[AI Recognition] Extracted channel name for {ip}: {channel_name}")

                    # Update channel name if valid
                    if channel_name and channel_name != "未知频道" and channel_name != "":
                        tv_channels[ip]['name'] = channel_name
                        recognized_count += 1
                        print(f"[AI Recognition] Successfully set channel name for {ip}: {channel_name}")
                    else:
                        print(f"[AI Recognition] Could not recognize channel for {ip}")
                else:
                    error_msg = f"AI API error for {ip}: {response.status_code} - {response.text[:200]}"
                    print(f"[AI Recognition] {error_msg}")
                    errors.append(error_msg)

            except Exception as e:
                print(f"[AI Recognition] Error recognizing {ip}: {str(e)}")
                errors.append(f"Error recognizing {ip}: {str(e)}")

        # Save updated channels
        if recognized_count > 0:
            save_channels()

        print(f"[AI Recognition] Completed: {recognized_count}/{total} channels recognized")
        if errors:
            print(f"[AI Recognition] Errors: {errors}")

    # Start background thread
    thread = threading.Thread(target=run_recognition)
    thread.daemon = True
    thread.start()

    # Return immediately
    return jsonify({
        "status": "started",
        "message": f"正在后台识别 {len(channels_to_recognize)} 个频道，请稍后刷新查看结果",
        "total": len(channels_to_recognize)
    })
if __name__ == '__main__':
    # Initialize database
    config = load_config()
    db = Database(config)

    # Load previous results and channels
    test_results = load_results()
    tv_channels = load_channels()
    groups = load_groups()

    print(f"\n{'='*60}")
    print(f"IPTV Stream Sniffer Server")
    print(f"{'='*60}")
    print(f"Server URL: http://0.0.0.0:9833")
    print(f"Database: {config.get('database', {}).get('type', 'json').upper()}")
    print(f"Loaded {len(test_results)} previous test(s)")
    print(f"Loaded {len(tv_channels)} channel(s) in library")
    print(f"Loaded {len(groups)} group(s)")
    print(f"Debug mode: ON (auto-reload enabled)")
    print(f"{'='*60}\n")

    # Start Flask server
    app.run(host='0.0.0.0', port=9833, debug=True, threaded=True)