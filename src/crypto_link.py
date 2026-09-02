import hmac
import hashlib

SECRET_KEY = b"XERA_ROBOTICS_ASV_SECURE_LINK_KEY_2026"

class SecureLink:
    def __init__(self):
        self.last_rx_seq = -1
        self.tx_seq = 0

    @staticmethod
    def sign_packet(payload, seq):
        msg = f"{payload}|{seq}".encode('utf-8')
        sig = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()
        return f"{payload}|{seq}|{sig}"

    def verify_packet(self, signed_packet):
        try:
            parts = signed_packet.strip().split('|')
            if len(parts) != 3:
                return None
            
            payload, seq_str, sig = parts
            seq = int(seq_str)
            
            # Verify sequence number to prevent replay attacks
            if seq <= self.last_rx_seq:
                print(f"[SecureLink Warning] Replay packet dropped. Seq: {seq} <= Last: {self.last_rx_seq}")
                return None
                
            # Verify signature integrity
            msg = f"{payload}|{seq}".encode('utf-8')
            expected_sig = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()
            
            if hmac.compare_digest(sig, expected_sig):
                self.last_rx_seq = seq
                return payload
            else:
                print("[SecureLink Warning] HMAC signature mismatch. Packet dropped.")
        except Exception as e:
            # Drop malformed packets silently
            pass
        return None

    def wrap_payload(self, payload):
        self.tx_seq += 1
        return self.sign_packet(payload, self.tx_seq)
