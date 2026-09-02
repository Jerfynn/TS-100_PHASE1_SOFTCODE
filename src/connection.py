import time
import math
import random
from PySide6.QtCore import QThread, Signal
from src.crypto_link import SecureLink

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Computes the geodesic distance in meters between two GPS coordinates using the Haversine formula.
    """
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(d_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def geodesic_bearing(lat1, lon1, lat2, lon2):
    """
    Computes the bearing in degrees between two GPS coordinates.
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon_rad = math.radians(lon2 - lon1)
    
    y = math.sin(dlon_rad) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
    
    bearing = math.atan2(y, x)
    return math.degrees(bearing)


class MarineTelemetryThread(QThread):
    # Signals
    # data_received emits a dictionary of telemetry values
    data_received = Signal(dict)
    connection_status = Signal(bool, str)
    wp_ack_received = Signal()
    log_received = Signal(str)
    raw_line_received = Signal(str)

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        # In socket mode, baudrate contains the IP:Port string (e.g. "127.0.0.1:8888" or "8888")
        self.raw_target = str(baudrate)
        self.baudrate = 9600
        try:
            if port not in ("TCP CLIENT", "UDP CLIENT"):
                self.baudrate = int(baudrate)
        except Exception:
            pass
            
        self.running = False
        self.mission_active = False
        self.rth_active = False
        self.home_lat = None
        self.home_lon = None
        self.sim_pwm_rc1 = 1500
        self.sim_pwm_rc2 = 1500
        self.sim_pwm_rc3 = 1500
        self.target_waypoints = []
        self.current_wp_index = 0
        self.secure_link = SecureLink()
        self.use_security = False
        
        # Socket descriptors
        self.socket_conn = None
        self.udp_send_addr = None
        self.light_state = 0
        self.camera_state = 0

    def set_waypoints(self, wps):
        self.target_waypoints = wps
        self.current_wp_index = 0
        
    def start_mission(self):
        self.mission_active = True
        self.current_wp_index = 0
        
    def stop_mission(self):
        self.mission_active = False

    @staticmethod
    def get_available_ports():
        ports = []
        if SERIAL_AVAILABLE:
            system_ports = serial.tools.list_ports.comports()
            for p in system_ports:
                ports.append(p.device)
        # Always include network & simulator options
        ports.append("SIMULATOR")
        ports.append("TCP CLIENT")
        ports.append("UDP CLIENT")
        return ports

    def run(self):
        self.running = True
        
        if self.port == "SIMULATOR":
            self.run_simulation()
        elif self.port == "TCP CLIENT":
            self.run_tcp_client()
        elif self.port == "UDP CLIENT":
            self.run_udp_client()
        else:
            self.run_serial()

    def run_simulation(self):
        self.connection_status.emit(True, "Simulator Active")
        
        # Initial coordinates near Xera Robotics (coastal bay area)
        lat = 12.9716
        lon = 80.2454
        heading = 45.0  # Yaw degrees
        
        self.home_lat = lat
        self.home_lon = lon
        self.rth_active = False

        step = 0
        while self.running:
            # Simulate marine vessel dynamics
            # Roll (rocking left-right): sine wave + random swell noise
            roll = 5.0 * math.sin(step * 0.05) + random.uniform(-0.5, 0.5)
            # Pitch (rocking front-back): shifted cosine wave + swell noise
            pitch = 3.0 * math.cos(step * 0.03 + 0.5) + random.uniform(-0.3, 0.3)
            
            # Default thruster states
            pwm_rc1 = 1500
            pwm_rc2 = 1500
            pwm_rc3 = 1500

            # Target waypoint logic
            target_lat, target_lon = None, None
            if getattr(self, 'rth_active', False):
                target_lat = self.home_lat
                target_lon = self.home_lon
            elif self.mission_active and self.target_waypoints and self.current_wp_index < len(self.target_waypoints):
                target_lat, target_lon = self.target_waypoints[self.current_wp_index]

            if target_lat is not None and target_lon is not None:
                dist_m = haversine_distance(lat, lon, target_lat, target_lon)
                
                if dist_m < 4.0:  # Reached target threshold (approx 4 meters)
                    if getattr(self, 'rth_active', False):
                        self.rth_active = False
                        self.mission_active = False
                        print("[SIMULATOR] Reached Home position!")
                    else:
                        self.current_wp_index += 1
                        print(f"[SIMULATOR] Reached Waypoint {self.current_wp_index - 1}")
                    
                # Re-evaluate targets after potential index increments
                target_lat, target_lon = None, None
                if getattr(self, 'rth_active', False):
                    target_lat = self.home_lat
                    target_lon = self.home_lon
                elif self.mission_active and self.target_waypoints and self.current_wp_index < len(self.target_waypoints):
                    target_lat, target_lon = self.target_waypoints[self.current_wp_index]

                if target_lat is not None and target_lon is not None:
                    dist_m = haversine_distance(lat, lon, target_lat, target_lon)
                    
                    if dist_m > 0:
                        target_heading = geodesic_bearing(lat, lon, target_lat, target_lon)
                        heading_error = (target_heading - heading + 180) % 360 - 180
                        
                        abs_error = abs(heading_error)
                        
                        # 1. Advanced steering logic with turn-in-place and speed scaling
                        if abs_error > 30.0:
                            # Large heading error: Rotate in place
                            pwm_rc1 = 1500
                            pwm_rc2 = 1700 if heading_error > 0 else 1300
                            turn_rate = 4.0  # rotate faster in place (deg per step)
                            speed_m_s = 0.0
                        elif 10.0 <= abs_error <= 30.0:
                            # Medium error: Move slowly while steering
                            pwm_rc1 = 1580
                            pwm_rc2 = 1600 if heading_error > 0 else 1400
                            turn_rate = 2.0
                            speed_m_s = 0.5  # approx 1 knot
                        else:
                            # Small error (<10°): Go straight, scale speed based on distance
                            pwm_rc2 = 1500
                            turn_rate = 1.0
                            if dist_m > 20.0:
                                pwm_rc1 = 1700
                                speed_m_s = 2.0  # full speed (approx 4 knots)
                            elif dist_m >= 5.0:
                                pwm_rc1 = 1600
                                speed_m_s = 1.2  # medium approach speed
                            else:
                                pwm_rc1 = 1550
                                speed_m_s = 0.6  # slow dock approach speed
                        
                        # T3 remains strictly deactivated (1500)
                        pwm_rc3 = 1500
                        
                        # Simulate heading changes
                        if abs_error > turn_rate:
                            heading = (heading + turn_rate * (1.0 if heading_error > 0 else -1.0)) % 360.0
                        else:
                            heading = target_heading
                        
                        # Project movement coordinates along current heading vector (physically realistic)
                        # Simulator updates at 10Hz, so time step is 0.1s
                        step_dist = speed_m_s * 0.1
                        
                        # Convert meters step to latitude and longitude delta
                        # 1 degree of latitude is approx 111,000 meters
                        delta_lat = (step_dist * math.cos(math.radians(heading))) / 111000.0
                        # 1 degree of longitude is approx 111,000 * cos(lat) meters
                        delta_lon = (step_dist * math.sin(math.radians(heading))) / (111000.0 * math.cos(math.radians(lat)))
                        
                        lat += delta_lat
                        lon += delta_lon
                else:
                    self.mission_active = False  # Completed route!
                    self.rth_active = False
            else:
                # Normal yaw drift when not navigating autonomously
                heading = (heading + 0.1 * math.sin(step * 0.01) + random.uniform(-0.1, 0.1)) % 360.0
                
                # Normal GPS drift
                lat += 0.000005 * math.sin(math.radians(heading)) + random.uniform(-1e-7, 1e-7)
                lon += 0.000005 * math.cos(math.radians(heading)) + random.uniform(-1e-7, 1e-7)
                
                # In manual mode, display commanded joystick values from GUI
                pwm_rc1 = getattr(self, 'sim_pwm_rc1', 1500)
                pwm_rc2 = getattr(self, 'sim_pwm_rc2', 1500)
                pwm_rc3 = getattr(self, 'sim_pwm_rc3', 1500)
            
            # Satellites: minor fluctuations
            sats = int(12 + math.sin(step * 0.02) * 2 + random.randint(-1, 1))
            sats = max(4, min(18, sats)) # Keep between 4 and 18
            
            # Distance (obstacle/seabed)
            dist = 45.2 + 8.0 * math.sin(step * 0.02) + random.uniform(-0.1, 0.1)
            
            # Confidence (0 to 100 %)
            conf = 95.0 + 3.0 * math.sin(step * 0.05) + random.uniform(-1.0, 1.0)
            conf = max(0.0, min(100.0, conf))
            
            # Magnetic sensor values rotating with heading
            mx = 22.4 * math.cos(math.radians(heading)) + random.uniform(-0.4, 0.4)
            my = 22.4 * math.sin(math.radians(heading)) + random.uniform(-0.4, 0.4)
            mz = -38.6 + random.uniform(-0.3, 0.3)
            
            # Simulate chamber temperature (DS18B20 sensor)
            chamber_temp = 31.5 + 4.0 * math.sin(step * 0.01) + random.uniform(-0.05, 0.05)
            
            # Simulate BMS battery parameters
            bms_volt = 25.2 - (step * 0.0005) % 3.2
            bms_curr = 2.5 + (8.5 if (self.mission_active or getattr(self, 'rth_active', False)) else 0.0) + random.uniform(-0.3, 0.3)
            bms_soc = max(0, int(100 - (step * 0.002) % 100))
            bms_remaining_ah = 15.0 * bms_soc / 100.0
            bms_soh = 99
            bms_temp = 25.0 + math.sin(step * 0.05) * 2.0
            
            # Simulate MS5837 Bar30 pressure, temperature, and depth
            sim_depth = max(0.0, 5.0 + 4.5 * math.sin(step * 0.02))
            sim_press = 1.013 + sim_depth * 0.1
            sim_temp = 22.6 + math.sin(step * 0.04) * 0.5
            
            data = {
                "roll": round(roll, 2),
                "pitch": round(pitch, 2),
                "yaw": round(heading, 2),
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "satellites": sats,
                "distance": round(dist, 2),
                "confidence": round(conf, 1),
                "mx": round(mx, 1),
                "my": round(my, 1),
                "mz": round(mz, 1),
                "chamber_temp": round(chamber_temp, 2),
                "bms_volt": round(bms_volt, 2),
                "bms_curr": round(bms_curr, 2),
                "bms_soc": bms_soc,
                "bms_remaining_ah": round(bms_remaining_ah, 2),
                "bms_soh": bms_soh,
                "bms_temp": round(bms_temp, 2),
                "pwm_rc1": pwm_rc1,
                "pwm_rc2": pwm_rc2,
                "pwm_rc3": pwm_rc3,
                "ms5837_press": round(sim_press, 3),
                "ms5837_temp": round(sim_temp, 2),
                "ms5837_depth": round(sim_depth, 3),
                "mode": "Simulated"
            }
            
            self.data_received.emit(data)
            step += 1
            self.msleep(100) # Update at 10Hz
            
        self.connection_status.emit(False, "Simulator Stopped")

    def run_serial(self):
        if not SERIAL_AVAILABLE:
            self.connection_status.emit(False, "PySerial module unavailable")
            return

        self.serial_port = None
        try:
            self.serial_port = serial.Serial(self.port, self.baudrate, timeout=1.0)
            self.connection_status.emit(True, f"Connected to {self.port}")
            
            while self.running:
                if self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    self.raw_line_received.emit(line)
                    
                    parsed_data = self.parse_data(line)
                    if parsed_data:
                        self.data_received.emit(parsed_data)
                else:
                    self.msleep(5)
                
        except serial.SerialException as e:
            self.connection_status.emit(False, f"Serial Error: {str(e)}")
        except Exception as e:
            self.connection_status.emit(False, f"Error: {str(e)}")
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.serial_port = None
            self.connection_status.emit(False, "Disconnected")

    def write_data(self, data_str):
        # Format: [manual(0)orauto(1)orconfig(2),stop(0)orstart(1),no.of waypoints,[waypoints],[linearkp,ki,kd],[angularkp,ki,kd],pwm1,pwm2,pwm3,lightstatus,camera_status,ahrs_offset]
        if not (isinstance(data_str, str) and data_str.strip().startswith('[') and data_str.strip().endswith(']')):
            return False
            
        translated = data_str.strip()
            
        # 1. Check socket connection mode
        if self.port in ("TCP CLIENT", "UDP CLIENT") and self.socket_conn:
            try:
                packet = (translated + "\n").encode('utf-8')
                if self.port == "TCP CLIENT":
                    self.socket_conn.sendall(packet)
                elif self.port == "UDP CLIENT" and self.udp_send_addr:
                    self.socket_conn.sendto(packet, self.udp_send_addr)
                print(f"[Socket TX] Transmitted over {self.port}: {translated}")
                return True
            except Exception as e:
                print(f"[Socket TX Error] Failed: {e}")
            return False
            
        # 2. Check serial port connection mode
        if hasattr(self, 'serial_port') and self.serial_port and self.serial_port.is_open:
            try:
                payload = translated + "\n"
                self.serial_port.write(payload.encode('utf-8'))
                self.serial_port.flush()
                print(f"[Serial TX] Transmitted: {translated}")
                return True
            except Exception as e:
                print(f"[Serial TX Error] Failed to write: {e}")
        else:
            print(f"[Serial Simulator TX] {translated}")
        return False

    def send_heartbeat(self):
        if not hasattr(self, 'light_state'):
            self.light_state = 0
        if not hasattr(self, 'camera_state'):
            self.camera_state = 0
            
        packet = f"1500,1500,1500,{self.light_state},{self.camera_state}\n".encode('utf-8')
            
        if self.port in ("TCP CLIENT", "UDP CLIENT") and self.socket_conn:
            try:
                if self.port == "TCP CLIENT":
                    self.socket_conn.sendall(packet)
                elif self.port == "UDP CLIENT" and self.udp_send_addr:
                    self.socket_conn.sendto(packet, self.udp_send_addr)
            except:
                pass
        elif hasattr(self, 'serial_port') and self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(packet)
                self.serial_port.flush()
            except:
                pass

    def parse_data(self, line):
        """
        Parses incoming telemetry lines in Python list format:
        [pitch,roll,yaw,temp,humidity,lat,long,sats,volts,amps,watts,soc,soh,p1,p2,p3,light,camera]
        """
        import ast
        try:
            line_str = line.strip()
            if line_str.startswith('[') and line_str.endswith(']'):
                parts = ast.literal_eval(line_str)
                if isinstance(parts, list) and len(parts) == 18:
                    def to_float(val, default=0.0):
                        if val is None or val == 'None' or val == '':
                            return default
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return default

                    def to_int(val, default=0):
                        if val is None or val == 'None' or val == '':
                            return default
                        try:
                            return int(float(val))
                        except (ValueError, TypeError):
                            return default

                    pitch = to_float(parts[0])
                    roll = to_float(parts[1])
                    yaw = to_float(parts[2])
                    temp = to_float(parts[3])
                    hum = to_float(parts[4])
                    lat = to_float(parts[5], 0.0)
                    lon = to_float(parts[6], 0.0)
                    sats = to_int(parts[7], 0)
                    volts = to_float(parts[8])
                    amps = to_float(parts[9])
                    watts = to_float(parts[10])
                    soc = to_int(parts[11])
                    soh = to_int(parts[12], 100)
                    p1 = to_int(parts[13], 1500)
                    p2 = to_int(parts[14], 1500)
                    p3 = to_int(parts[15], 1500)
                    light = to_int(parts[16])
                    camera = to_int(parts[17])
                    
                    return {
                        "roll": roll,
                        "pitch": pitch,
                        "yaw": yaw,
                        "latitude": lat,
                        "longitude": lon,
                        "satellites": sats,
                        "distance": 0.0,
                        "confidence": 100.0,
                        "mx": 0.0,
                        "my": 0.0,
                        "mz": 0.0,
                        "chamber_temp": temp,
                        "chamber_hum": hum,
                        "bms_volt": volts,
                        "bms_curr": amps,
                        "bms_soc": soc,
                        "bms_remaining_ah": 15.0 * soc / 100.0,
                        "bms_soh": soh,
                        "bms_temp": 25.0,
                        "pwm_rc1": p1,
                        "pwm_rc2": p2,
                        "pwm_rc3": p3,
                        "light": light,
                        "camera": camera,
                        "mode": "Subsea List"
                    }
        except Exception as e:
            print(f"[List Parse Error] {e}")
            pass
        return None

    def run_tcp_client(self):
        import socket
        
        ip = "127.0.0.1"
        port = 8888
        
        # Parse target IP:PORT from raw_target
        if ":" in self.raw_target:
            try:
                parts = self.raw_target.split(":")
                ip = parts[0].strip()
                port = int(parts[1].strip())
            except:
                pass
                
        self.connection_status.emit(True, f"TCP Connecting...")
        
        while self.running:
            try:
                # Open TCP socket connection
                self.socket_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Disable Nagle's algorithm for low-latency telemetry streaming
                self.socket_conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.socket_conn.settimeout(2.0)
                self.socket_conn.connect((ip, port))
                self.connection_status.emit(True, f"TCP: {ip}")
                
                buffer = b""
                
                while self.running:
                    try:
                        data = self.socket_conn.recv(4096)
                    except socket.timeout:
                        continue
                        
                    if not data:
                        break # connection closed
                        
                    buffer += data
                    
                    # Split packets by newline for ASCII telemetry
                    latest_telemetry_line = None
                    while b"\n" in buffer:
                        line_bytes, buffer = buffer.split(b"\n", 1)
                        line = line_bytes.decode('utf-8', errors='ignore').strip()
                        if line:
                            # Keep track of the newest telemetry line, discarding older backlog states
                            latest_telemetry_line = line
                            
                    # Update GUI only with the newest received data to avoid flood lag
                    if latest_telemetry_line:
                        parsed_data = self.parse_data(latest_telemetry_line)
                        if parsed_data:
                            parsed_data["mode"] = "TCP Link"
                            self.data_received.emit(parsed_data)
                                
            except Exception as e:
                self.connection_status.emit(False, "TCP Offline")
                if self.socket_conn:
                    try:
                        self.socket_conn.close()
                    except:
                        pass
                    self.socket_conn = None
                time.sleep(1.0) # wait before retry

    def run_udp_client(self):
        import socket
        
        target_ip = "192.168.1.10"
        target_port = 8888
        
        # Parse target IP:PORT from raw_target input
        if ":" in self.raw_target:
            try:
                parts = self.raw_target.split(":")
                target_ip = parts[0].strip()
                target_port = int(parts[1].strip())
            except:
                pass
        else:
            try:
                target_port = int(self.raw_target.strip())
            except:
                pass
                
        self.udp_send_addr = (target_ip, target_port)
        self.connection_status.emit(True, f"UDP: {target_ip}")
        
        while self.running:
            try:
                # Open UDP client socket
                self.socket_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket_conn.settimeout(0.5)
                
                # Disable WSAECONNRESET on Windows (port unreachable ICMP triggers ConnectionResetError)
                import os
                if os.name == 'nt':
                    try:
                        self.socket_conn.ioctl(socket.SIO_UDP_CONNRESET, False)
                    except:
                        pass
                
                # Bind to local wildcard port to allow sending/receiving dynamically
                self.socket_conn.bind(('0.0.0.0', 0))
                
                while self.running:
                    # Drain all pending datagrams in OS queue to eliminate backlog visual sliding
                    latest_datagram = None
                    self.socket_conn.settimeout(0.1 if not latest_datagram else 0.0)
                    while self.running:
                        try:
                            data, addr = self.socket_conn.recvfrom(4096)
                            if data:
                                latest_datagram = data
                                # Temporarily make recv non-blocking to clear socket queue
                                self.socket_conn.settimeout(0.0)
                        except (socket.timeout, OSError):
                            break
                            
                    if latest_datagram:
                        line = latest_datagram.decode('utf-8', errors='ignore').strip()
                        if line:
                            self.raw_line_received.emit(line)
                            parsed_data = self.parse_data(line)
                            if parsed_data:
                                parsed_data["mode"] = "UDP Link"
                                self.data_received.emit(parsed_data)
                                
            except Exception as e:
                self.connection_status.emit(False, "UDP Error")
                if self.socket_conn:
                    try:
                        self.socket_conn.close()
                    except:
                        pass
                    self.socket_conn = None
                time.sleep(1.0)

    def stop(self):
        self.running = False
        if self.socket_conn:
            try:
                self.socket_conn.close()
            except:
                pass
            self.socket_conn = None
        self.wait()
