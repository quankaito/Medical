from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.backends import default_backend
import os
import base64

# --- CẤU HÌNH KHÓA RSA (PERSISTENT - LƯU FILE) ---
KEY_DIR = os.path.dirname(os.path.abspath(__file__)) # Thư mục chứa file này
PRI_KEY_FILE = os.path.join(KEY_DIR, 'app_private_key.pem')
PUB_KEY_FILE = os.path.join(KEY_DIR, 'app_public_key.pem')

def load_or_generate_keys():
    # 1. Nếu đã có file khóa -> Load lên dùng
    if os.path.exists(PRI_KEY_FILE) and os.path.exists(PUB_KEY_FILE):
        with open(PRI_KEY_FILE, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
        with open(PUB_KEY_FILE, "rb") as f:
            public_key = serialization.load_pem_public_key(
                f.read(), backend=default_backend()
            )
        return private_key, public_key
    
    # 2. Nếu chưa có -> Sinh mới và Lưu file
    else:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()

        # Lưu Private Key
        with open(PRI_KEY_FILE, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Lưu Public Key
        with open(PUB_KEY_FILE, "wb") as f:
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
            
        return private_key, public_key

# Khởi tạo khóa toàn cục
PRIVATE_KEY, PUBLIC_KEY = load_or_generate_keys()

# --- 1. MÃ HÓA ĐỐI XỨNG (AES) ---
class AppAES:
    @staticmethod
    def generate_key():
        return os.urandom(32) # AES-256

    @staticmethod
    def encrypt(data, key):
        if not data: return ""
        try:
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data.encode()) + padder.finalize()
            iv = os.urandom(16)
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            encryptor = cipher.encryptor()
            ct = encryptor.update(padded_data) + encryptor.finalize()
            return base64.b64encode(iv + ct).decode('utf-8')
        except Exception as e:
            return f"Error AES Encrypt: {str(e)}"

    @staticmethod
    def decrypt(enc_data, key):
        if not enc_data: return ""
        try:
            raw = base64.b64decode(enc_data)
            iv = raw[:16]
            ct = raw[16:]
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(ct) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            return data.decode('utf-8')
        except Exception as e:
            return f"Lỗi giải mã AES: {str(e)}"

# --- 2. MÃ HÓA BẤT ĐỐI XỨNG (RSA) ---
class AppRSA:
    @staticmethod
    def encrypt_key(aes_key):
        """Dùng RSA Public Key để mã hóa khóa AES (Hybrid)"""
        try:
            ciphertext = PUBLIC_KEY.encrypt(
                aes_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return base64.b64encode(ciphertext).decode('utf-8')
        except Exception as e:
            return None

    @staticmethod
    def decrypt_key(enc_aes_key):
        """Dùng RSA Private Key để giải mã lấy lại khóa AES"""
        try:
            raw_key = base64.b64decode(enc_aes_key)
            plaintext = PRIVATE_KEY.decrypt(
                raw_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return plaintext
        except Exception as e:
            print(f"DEBUG RSA DECRYPT KEY ERROR: {e}") # In lỗi ra console để debug
            return None

    @staticmethod
    def encrypt_data(text):
        """Mã hóa văn bản trực tiếp (Text ngắn)"""
        if not text: return ""
        try:
            ciphertext = PUBLIC_KEY.encrypt(
                text.encode('utf-8'),
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return base64.b64encode(ciphertext).decode('utf-8')
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def decrypt_data(enc_text):
        """Giải mã văn bản trực tiếp"""
        if not enc_text: return ""
        try:
            raw_data = base64.b64decode(enc_text)
            plaintext = PRIVATE_KEY.decrypt(
                raw_data,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return plaintext.decode('utf-8')
        except Exception as e:
            print(f"DEBUG RSA DECRYPT DATA ERROR: {e}")
            return "Lỗi khóa RSA (Key mismatch)"