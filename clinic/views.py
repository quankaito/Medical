from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection
from django.http import JsonResponse
from .forms import LoginForm, RegisterForm
import oracledb
from .utils import AppAES, AppRSA # Import module vừa tạo
import datetime
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import binascii
# --- BIẾN TOÀN CỤC GIẢ LẬP KHÓA AES CHO LỊCH HẸN ---
# (Thực tế nên lưu vào bảng Keystore, nhưng để đơn giản ta dùng biến tĩnh cho demo)
LICH_HEN_AES_KEY = b'ThisIsASecretKeyForAppointments!' # 32 bytes
# --- HÀM HỖ TRỢ GỌI PROCEDURE ---
def call_oracle_create_user(username, password):
    with connection.cursor() as cursor:
        # Gọi procedure USP_TAO_USER_APP đã viết
        cursor.callproc('USP_TAO_USER_APP', [username, password])

def load_rsa_key_from_db(key_name):
    """Hàm phụ trợ để lấy Key từ bảng KEY_STORE"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT KEY_VALUE FROM KEY_STORE WHERE KEY_NAME = %s", [key_name])
            row = cursor.fetchone()
            if row:
                # Xử lý LOB nếu Oracle trả về LOB object
                return row[0].read() if hasattr(row[0], 'read') else row[0]
    except Exception as e:
        print(f"Error loading key: {e}")
    return None
# --- VIEWS ---

def home_view(request):
    return render(request, 'clinic/home.html')

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['username'].upper() # Oracle user thường viết hoa
            pwd = form.cleaned_data['password']
            
            # Thông tin nhân viên
            hoten = form.cleaned_data['hoten']
            email = form.cleaned_data['email']
            cccd = form.cleaned_data['cccd']
            chucvu = form.cleaned_data['chucvu']
            luong = '0' # Mặc định tạm, admin sẽ sửa sau

            try:
                # 1. Tạo User Oracle thực (Gọi Procedure)
                call_oracle_create_user(user, pwd)

                # 2. Lưu thông tin vào bảng NHAN_VIEN (Dùng SQL trực tiếp để chắc chắn)
                with connection.cursor() as cursor:
                    sql = """
                        INSERT INTO NHAN_VIEN (MANV, HOTEN, EMAIL, LUONG, CCCD, CHUCVU)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql, [user, hoten, email, luong, cccd, chucvu])
                
                messages.success(request, f"Đã tạo user Oracle '{user}' và hồ sơ nhân viên thành công!")
                return redirect('login')
                
            except Exception as e:
                messages.error(request, f"Lỗi tạo user: {str(e)}")
    else:
        form = RegisterForm()
    return render(request, 'clinic/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].upper()
            password = form.cleaned_data['password']
            dsn = '172.17.81.140:1521/orclpdb'

            try:
                # 1. Thử kết nối Oracle
                test_conn = oracledb.connect(user=username, password=password, dsn=dsn)
                
                # 2. Lấy Role của User hiện tại
                user_role = "USER" # Mặc định
                try:
                    with test_conn.cursor() as cursor:
                        # Kiểm tra trong session roles
                        cursor.execute("SELECT ROLE FROM SESSION_ROLES WHERE ROLE LIKE 'ROLE_%'")
                        row = cursor.fetchone()
                        if row:
                            user_role = row[0] # Ví dụ: ROLE_BACSI
                        elif username == 'CLINIC_ADMIN':
                            user_role = 'ADMIN'
                except Exception:
                    pass
                
                test_conn.close()

                # 3. Lưu vào Session Django
                request.session['db_user'] = username
                request.session['db_password'] = password
                request.session['user_role'] = user_role # <--- LƯU ROLE VÀO SESSION
                
                messages.success(request, f"Xin chào {username} ({user_role})")
                return redirect('home')

            except oracledb.Error as e:
                messages.error(request, "Sai tài khoản hoặc mật khẩu!")
    else:
        form = LoginForm()
    return render(request, 'clinic/login.html', {'form': form})

def logout_view(request):
    if 'db_user' in request.session:
        del request.session['db_user']
    if 'db_password' in request.session:
        del request.session['db_password']
    messages.info(request, "Đã đăng xuất.")
    return redirect('login')

# --- CÁC VIEW MỚI CHO DASHBOARD & GIẢI MÃ ---

def is_oracle_logged_in(request):
    """Kiểm tra xem user đã login chưa (dựa vào session)"""
    return 'db_user' in request.session

# Trong clinic/views.py

# --- CẬP NHẬT dashboard_view TRONG clinic/views.py ---

# --- TRONG clinic/views.py ---

def dashboard_view(request):
    if not is_oracle_logged_in(request):
        return redirect('login')
    
    db_user = request.session.get('db_user', '')
    db_password = request.session.get('db_password', '')
    user_role = request.session.get('user_role', '')
    
    # --- CẬP NHẬT LẠI PERMISSIONS ---
    permissions = {
        'is_admin': db_user == 'CLINIC_ADMIN',
        'is_bacsi': user_role == 'ROLE_BACSI',
        'is_yta': user_role == 'ROLE_YTA',
        'is_letan': user_role == 'ROLE_LETAN',
        'is_ketoan': user_role == 'ROLE_KETOAN',
        'is_quanly': user_role == 'ROLE_QUANLY',
        
        # Xem lương: Ai cũng được xem (VPD sẽ tự lọc dòng của ai người nấy thấy)
        'can_view_salary': True, 
        
        # Quản lý nhân sự: ADMIN và KẾ TOÁN được Thêm/Sửa/Xóa
        'can_manage_staff': db_user == 'CLINIC_ADMIN' or user_role == 'ROLE_KETOAN', 
        
        # Các quyền khác giữ nguyên
        'can_view_medical': db_user == 'CLINIC_ADMIN' or user_role in ['ROLE_BACSI', 'ROLE_YTA', 'ROLE_QUANLY'],
        'can_view_opinion': db_user == 'CLINIC_ADMIN' or user_role in ['ROLE_BACSI', 'ROLE_QUANLY'],
        'can_add_appt': user_role != 'ROLE_KETOAN',
    }

    nhanviens = []
    khachhangs = []
    lichhens = []
    hosos = []
    ykiens = []

    # --- KHỞI TẠO KẾT NỐI RIÊNG ĐỂ KÍCH HOẠT VPD ---
    target_conn = None
    cursor = None
    
    try:
        # Nếu là Admin -> Dùng kết nối chung (nhanh)
        if db_user == 'CLINIC_ADMIN':
            cursor = connection.cursor()
        else:
            # Nếu là User thường -> Connect bằng chính user đó để Oracle nhận diện (Kích hoạt VPD)
            dsn = '172.17.81.140/orclpdb' # Đảm bảo DSN đúng với máy bạn
            target_conn = oracledb.connect(user=db_user, password=db_password, dsn=dsn)
            cursor = target_conn.cursor()

        # --- THỰC HIỆN TRUY VẤN (Dùng cursor vừa tạo) ---
        
        # 1. Nhân viên (VPD sẽ chạy ở đây)
        cursor.execute("SELECT MANV, HOTEN, EMAIL, CHUCVU, LUONG FROM CLINIC_ADMIN.NHAN_VIEN")
        for r in cursor.fetchall():
            chucvu_db = r[3]
            nhanviens.append({
                'manv': r[0], 'hoten': r[1], 'email': r[2], 'chucvu': chucvu_db, 'luong_enc': r[4],
                'is_bacsi': chucvu_db == 'BacSi', 'is_yta': chucvu_db == 'YTa', 'is_letan': chucvu_db == 'LeTan'
            })

        # 2. Khách hàng
        cursor.execute("SELECT MAKH, HOTEN, SDT, BENHAN FROM CLINIC_ADMIN.KHACH_HANG")
        for r in cursor.fetchall():
            khachhangs.append({'makh': r[0], 'hoten': r[1], 'sdt': r[2], 'benhan_enc': r[3]})

        # 3. Lịch hẹn
        cursor.execute("SELECT L.MA_LH, L.NGAY_HEN, L.GHI_CHU, K.HOTEN, N.HOTEN FROM CLINIC_ADMIN.LICH_HEN L JOIN CLINIC_ADMIN.KHACH_HANG K ON L.MA_KH=K.MAKH JOIN CLINIC_ADMIN.NHAN_VIEN N ON L.MANV=N.MANV")
        for r in cursor.fetchall():
            lichhens.append({'ma_lh': r[0], 'ngay_hen': r[1], 'ghi_chu_enc': r[2], 'kh_ten': r[3], 'bs_ten': r[4]})

        # 4. Hồ sơ (Chỉ query nếu có quyền web, DB sẽ chặn thêm lớp nữa nếu cần)
        if permissions['can_view_medical']:
            cursor.execute("SELECT H.MA_HS, H.NGAY_KHAM, H.CHAN_DOAN, K.HOTEN FROM CLINIC_ADMIN.HO_SO_BENH_AN H JOIN CLINIC_ADMIN.KHACH_HANG K ON H.MA_KH=K.MAKH")
            for r in cursor.fetchall():
                hosos.append({'ma_hs': r[0], 'ngay': r[1], 'chan_doan_enc': r[2].read() if hasattr(r[2], 'read') else r[2], 'kh_ten': r[3]})

        # 5. Ý kiến
        if permissions['can_view_opinion']:
            cursor.execute("SELECT Y.MA_YK, Y.NGAY_YK, Y.NOI_DUNG, K.HOTEN, N.HOTEN FROM CLINIC_ADMIN.YK_BAC_SI Y JOIN CLINIC_ADMIN.KHACH_HANG K ON Y.MA_KH=K.MAKH JOIN CLINIC_ADMIN.NHAN_VIEN N ON Y.MANV=N.MANV")
            for r in cursor.fetchall():
                ykiens.append({'ma_yk': r[0], 'ngay': r[1], 'noi_dung_enc': r[2].read() if hasattr(r[2], 'read') else r[2], 'kh_ten': r[3], 'bs_ten': r[4]})

    except Exception as e:
        messages.error(request, f"Lỗi truy vấn: {str(e)}")
    finally:
        # Đóng kết nối riêng nếu có
        if target_conn:
            target_conn.close()

    return render(request, 'clinic/dashboard.html', {
        'nhanviens': nhanviens, 'khachhangs': khachhangs, 'lichhens': lichhens, 'hosos': hosos, 'ykiens': ykiens,
        'db_user': db_user,
        'perms': permissions
    })

def decrypt_salary(request):
    """API: Giải mã Lương (Gọi PKG_SECURITY.DECRYPT_AES)"""
    if not is_oracle_logged_in(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    encrypted_val = request.GET.get('val', '')
    if not encrypted_val:
        return JsonResponse({'decrypted': ''})

    decrypted_val = ""
    try:
        with connection.cursor() as cursor:
            # Gọi hàm Oracle
            cursor.execute("SELECT PKG_SECURITY.DECRYPT_AES(%s) FROM DUAL", [encrypted_val])
            row = cursor.fetchone()
            if row:
                decrypted_val = row[0]
            else:
                decrypted_val = "Không có dữ liệu"
    except Exception as e:
        decrypted_val = f"Lỗi Oracle: {str(e)}"

    return JsonResponse({'decrypted': decrypted_val})

def decrypt_medical(request):
    """API: Giải mã Bệnh Án (Gọi PKG_SECURITY.DECRYPT_RSA)"""
    if not is_oracle_logged_in(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    encrypted_val = request.GET.get('val', '')
    if not encrypted_val:
        return JsonResponse({'decrypted': ''})
    
    decrypted_val = ""
    try:
        with connection.cursor() as cursor:
            # Gọi hàm Oracle
            cursor.execute("SELECT PKG_SECURITY.DECRYPT_RSA(%s) FROM DUAL", [encrypted_val])
            row = cursor.fetchone()
            if row:
                decrypted_val = row[0]
            else:
                decrypted_val = "Không có dữ liệu"
    except Exception as e:
        decrypted_val = f"Lỗi Oracle: {str(e)}"

    return JsonResponse({'decrypted': decrypted_val})

# --- CRUD NHÂN VIÊN ---

def add_staff(request):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            manv = request.POST['manv']
            hoten = request.POST['hoten']
            email = request.POST['email']
            chucvu = request.POST['chucvu']
            luong_raw = request.POST['luong'] # Lương chưa mã hóa
            cccd = request.POST['cccd'] # Tạm thời chưa mã hóa CCCD theo yêu cầu cũ, hoặc mã hóa nếu muốn

            with connection.cursor() as cursor:
                # INSERT gọi hàm Mã hóa AES cho Lương
                sql = """
                    INSERT INTO NHAN_VIEN (MANV, HOTEN, EMAIL, LUONG, CCCD, CHUCVU)
                    VALUES (%s, %s, %s, PKG_SECURITY.ENCRYPT_AES(%s), %s, %s)
                """
                cursor.execute(sql, [manv, hoten, email, luong_raw, cccd, chucvu])
            messages.success(request, f"Đã thêm nhân viên {manv} thành công!")
        except Exception as e:
            messages.error(request, f"Lỗi thêm nhân viên: {str(e)}")
    return redirect('dashboard')

def edit_staff(request, manv):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            hoten = request.POST['hoten']
            email = request.POST['email']
            chucvu = request.POST['chucvu']
            luong_raw = request.POST['luong']

            with connection.cursor() as cursor:
                # UPDATE gọi hàm Mã hóa AES cho Lương mới
                sql = """
                    UPDATE NHAN_VIEN 
                    SET HOTEN=%s, EMAIL=%s, CHUCVU=%s, 
                        LUONG=PKG_SECURITY.ENCRYPT_AES(%s)
                    WHERE MANV=%s
                """
                cursor.execute(sql, [hoten, email, chucvu, luong_raw, manv])
            messages.success(request, f"Cập nhật nhân viên {manv} thành công!")
        except Exception as e:
            messages.error(request, f"Lỗi cập nhật: {str(e)}")
    return redirect('dashboard')

def delete_staff(request, manv):
    if is_oracle_logged_in(request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM NHAN_VIEN WHERE MANV=%s", [manv])
            messages.success(request, f"Đã xóa nhân viên {manv}.")
        except Exception as e:
            messages.error(request, f"Lỗi xóa: {str(e)}")
    return redirect('dashboard')

# --- CRUD KHÁCH HÀNG ---

def add_customer(request):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            makh = request.POST['makh']
            hoten = request.POST['hoten']
            ngaysinh = request.POST['ngaysinh'] # YYYY-MM-DD
            sdt = request.POST['sdt']
            benhan_raw = request.POST['benhan'] # Bệnh án chưa mã hóa

            with connection.cursor() as cursor:
                # INSERT gọi hàm Mã hóa RSA cho Bệnh án
                sql = """
                    INSERT INTO KHACH_HANG (MAKH, HOTEN, NGAYSINH, SDT, BENHAN)
                    VALUES (%s, %s, TO_DATE(%s, 'YYYY-MM-DD'), %s, PKG_SECURITY.ENCRYPT_RSA(%s))
                """
                cursor.execute(sql, [makh, hoten, ngaysinh, sdt, benhan_raw])
            messages.success(request, f"Đã thêm hồ sơ {makh} thành công!")
        except Exception as e:
            messages.error(request, f"Lỗi thêm hồ sơ: {str(e)}")
    return redirect('dashboard')

def edit_customer(request, makh):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            hoten = request.POST['hoten']
            sdt = request.POST['sdt']
            benhan_raw = request.POST['benhan']

            with connection.cursor() as cursor:
                # UPDATE gọi hàm Mã hóa RSA cho Bệnh án mới
                sql = """
                    UPDATE KHACH_HANG 
                    SET HOTEN=%s, SDT=%s, 
                        BENHAN=PKG_SECURITY.ENCRYPT_RSA(%s)
                    WHERE MAKH=%s
                """
                cursor.execute(sql, [hoten, sdt, benhan_raw, makh])
            messages.success(request, f"Cập nhật hồ sơ {makh} thành công!")
        except Exception as e:
            messages.error(request, f"Lỗi cập nhật: {str(e)}")
    return redirect('dashboard')

def delete_customer(request, makh):
    if is_oracle_logged_in(request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM KHACH_HANG WHERE MAKH=%s", [makh])
            messages.success(request, f"Đã xóa hồ sơ {makh}.")
        except Exception as e:
            messages.error(request, f"Lỗi xóa: {str(e)}")
    return redirect('dashboard')

# --- CRUD LỊCH HẸN (MÃ HÓA AES PYTHON) ---
def add_appointment(request):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            ma_lh = request.POST['ma_lh']
            ma_kh = request.POST['ma_kh']
            manv = request.POST['manv']
            ngay_hen = request.POST['ngay_hen']
            ghi_chu_raw = request.POST['ghi_chu']

            # 1. Mã hóa AES tại Python
            ghi_chu_enc = AppAES.encrypt(ghi_chu_raw, LICH_HEN_AES_KEY)

            with connection.cursor() as cursor:
                sql = """INSERT INTO LICH_HEN (MA_LH, MA_KH, MANV, NGAY_HEN, GHI_CHU) 
                         VALUES (%s, %s, %s, TO_DATE(%s, 'YYYY-MM-DD'), %s)"""
                cursor.execute(sql, [ma_lh, ma_kh, manv, ngay_hen, ghi_chu_enc])
            messages.success(request, f"Đã tạo lịch hẹn {ma_lh}")
        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)}")
    return redirect('dashboard')

def delete_appointment(request, ma_lh):
    if is_oracle_logged_in(request):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM LICH_HEN WHERE MA_LH=%s", [ma_lh])
        messages.success(request, f"Đã xóa lịch hẹn {ma_lh}")
    return redirect('dashboard')

# API Giải mã AES Python (Cho Lịch Hẹn)
def decrypt_appt_app(request):
    val = request.GET.get('val', '')
    decrypted = AppAES.decrypt(val, LICH_HEN_AES_KEY)
    return JsonResponse({'decrypted': decrypted})

# --- CRUD HỒ SƠ BỆNH ÁN (MÃ HÓA LAI - HYBRID) ---
def add_record(request):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            ma_hs = request.POST['ma_hs']
            ma_kh = request.POST['ma_kh']
            chan_doan_raw = request.POST['chan_doan']

            # QUY TRÌNH MÃ HÓA LAI:
            # 1. Sinh khóa AES ngẫu nhiên cho hồ sơ này
            session_key = AppAES.generate_key()
            
            # 2. Dùng khóa AES này mã hóa dữ liệu bệnh án
            data_enc = AppAES.encrypt(chan_doan_raw, session_key)
            
            # 3. Dùng khóa RSA Public để mã hóa cái khóa AES kia
            key_enc = AppRSA.encrypt_key(session_key)

            with connection.cursor() as cursor:
                sql = """INSERT INTO HO_SO_BENH_AN (MA_HS, MA_KH, CHAN_DOAN, KEY_AES_ENCRYPTED) 
                         VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, [ma_hs, ma_kh, data_enc, key_enc])
            messages.success(request, "Đã tạo hồ sơ bệnh án (Mã hóa Lai)")
        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)}")
    return redirect('dashboard')

def delete_record(request, ma_hs):
    if is_oracle_logged_in(request):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM HO_SO_BENH_AN WHERE MA_HS=%s", [ma_hs])
        messages.success(request, f"Đã xóa hồ sơ {ma_hs}")
    return redirect('dashboard')

# API Giải mã Hybrid (Cho Hồ Sơ)
def decrypt_record_app(request):
    # Lấy data mã hóa và key mã hóa từ request
    # Thực tế phải query DB để lấy Key Encrypted dựa vào ID, nhưng để nhanh ta truyền từ client
    try:
        ma_hs = request.GET.get('id', '')
        with connection.cursor() as cursor:
            cursor.execute("SELECT CHAN_DOAN, KEY_AES_ENCRYPTED FROM HO_SO_BENH_AN WHERE MA_HS=%s", [ma_hs])
            row = cursor.fetchone()
            if row:
                data_enc = row[0].read() if hasattr(row[0], 'read') else row[0] # Handle CLOB
                key_enc = row[1]
                
                # 1. Giải mã RSA để lấy lại khóa AES
                aes_key = AppRSA.decrypt_key(key_enc)
                if not aes_key: return JsonResponse({'decrypted': 'Lỗi RSA Key'})
                
                # 2. Dùng khóa AES giải mã dữ liệu
                decrypted = AppAES.decrypt(data_enc, aes_key)
                return JsonResponse({'decrypted': decrypted})
            
    except Exception as e:
        return JsonResponse({'decrypted': f'Lỗi: {str(e)}'})
    
    return JsonResponse({'decrypted': 'Không tìm thấy'})

# --- 1. LOGIC SỬA LỊCH HẸN (AES APP) ---
def edit_appointment(request, ma_lh):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            ngay_hen = request.POST['ngay_hen']
            ghi_chu_raw = request.POST['ghi_chu']

            # Mã hóa lại ghi chú mới
            ghi_chu_enc = AppAES.encrypt(ghi_chu_raw, LICH_HEN_AES_KEY)

            with connection.cursor() as cursor:
                sql = "UPDATE LICH_HEN SET NGAY_HEN=TO_DATE(%s, 'YYYY-MM-DD'), GHI_CHU=%s WHERE MA_LH=%s"
                cursor.execute(sql, [ngay_hen, ghi_chu_enc, ma_lh])
            messages.success(request, f"Cập nhật lịch hẹn {ma_lh} thành công")
        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)}")
    return redirect('dashboard')

# --- 2. LOGIC SỬA HỒ SƠ BỆNH ÁN (HYBRID) ---
def edit_record(request, ma_hs):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            chan_doan_raw = request.POST['chan_doan']

            # QUY TRÌNH MÃ HÓA LAI LẠI TỪ ĐẦU
            # 1. Sinh khóa Session mới
            session_key = AppAES.generate_key()
            # 2. Mã hóa Data mới bằng Session Key mới
            data_enc = AppAES.encrypt(chan_doan_raw, session_key)
            # 3. Mã hóa Session Key mới bằng RSA Public Key
            key_enc = AppRSA.encrypt_key(session_key)

            with connection.cursor() as cursor:
                sql = "UPDATE HO_SO_BENH_AN SET CHAN_DOAN=%s, KEY_AES_ENCRYPTED=%s WHERE MA_HS=%s"
                cursor.execute(sql, [data_enc, key_enc, ma_hs])
            messages.success(request, f"Cập nhật hồ sơ {ma_hs} thành công")
        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)}")
    return redirect('dashboard')

# --- 3. CRUD CHO BẢNG MỚI: Ý KIẾN BÁC SĨ (RSA APP DIRECT) ---
def add_opinion(request):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            ma_yk = request.POST['ma_yk']
            ma_kh = request.POST['ma_kh']
            manv = request.POST['manv']
            noi_dung_raw = request.POST['noi_dung']

            # MÃ HÓA RSA TRỰC TIẾP (TEXT NGẮN)
            noi_dung_enc = AppRSA.encrypt_data(noi_dung_raw)

            with connection.cursor() as cursor:
                sql = "INSERT INTO YK_BAC_SI (MA_YK, MA_KH, MANV, NOI_DUNG) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, [ma_yk, ma_kh, manv, noi_dung_enc])
            messages.success(request, f"Đã thêm ý kiến {ma_yk}")
        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)}")
    return redirect('dashboard')

def delete_opinion(request, ma_yk):
    if is_oracle_logged_in(request):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM YK_BAC_SI WHERE MA_YK=%s", [ma_yk])
        messages.success(request, f"Đã xóa ý kiến {ma_yk}")
    return redirect('dashboard')

def decrypt_opinion_app(request):
    val = request.GET.get('val', '')
    decrypted = AppRSA.decrypt_data(val)
    return JsonResponse({'decrypted': decrypted})

def edit_opinion(request, ma_yk):
    if request.method == 'POST' and is_oracle_logged_in(request):
        try:
            noi_dung_raw = request.POST['noi_dung']

            # Mã hóa lại nội dung mới bằng RSA App
            noi_dung_enc = AppRSA.encrypt_data(noi_dung_raw)

            with connection.cursor() as cursor:
                sql = "UPDATE YK_BAC_SI SET NOI_DUNG=%s WHERE MA_YK=%s"
                cursor.execute(sql, [noi_dung_enc, ma_yk])
            messages.success(request, f"Cập nhật ý kiến {ma_yk} thành công")
        except Exception as e:
            messages.error(request, f"Lỗi cập nhật: {str(e)}")
    return redirect('dashboard')

# --- PHẦN 5: ADMIN PANEL (SYSTEM MONITOR) ---

def admin_panel(request):
    """Trang quản trị hệ thống Oracle"""
    # Chỉ cho phép user đặc biệt vào (ví dụ user quản trị DB)
    if not is_oracle_logged_in(request):
        return redirect('login')
    
    sessions = []
    users = []
    tablespaces = []

    try:
        with connection.cursor() as cursor:
            # 1. Lấy danh sách Session đang hoạt động (trừ các process hệ thống)
            cursor.execute("""
                SELECT SID, SERIAL#, USERNAME, STATUS, OSUSER, MACHINE, PROGRAM 
                FROM V$SESSION 
                WHERE TYPE = 'USER' AND USERNAME IS NOT NULL
            """)
            for r in cursor.fetchall():
                sessions.append({'sid': r[0], 'serial': r[1], 'username': r[2], 'status': r[3], 'osuser': r[4], 'machine': r[5], 'program': r[6]})

            # 2. Lấy danh sách User và Trạng thái khóa (Chỉ lấy user của App mình tạo)
            cursor.execute("""
                SELECT USERNAME, ACCOUNT_STATUS, LOCK_DATE, PROFILE 
                FROM DBA_USERS 
                WHERE USERNAME IN (SELECT MANV FROM NHAN_VIEN) OR USERNAME = 'CLINIC_ADMIN'
            """)
            for r in cursor.fetchall():
                users.append({'username': r[0], 'status': r[1], 'lock_date': r[2], 'profile': r[3]})

            # 3. Thông tin Tablespace
            cursor.execute("""
                SELECT T.TABLESPACE_NAME, 
                       ROUND(SUM(F.BYTES) / 1024 / 1024, 2) AS SIZE_MB,
                       T.STATUS
                FROM DBA_TABLESPACES T
                JOIN DBA_DATA_FILES F ON T.TABLESPACE_NAME = F.TABLESPACE_NAME
                GROUP BY T.TABLESPACE_NAME, T.STATUS
            """)
            for r in cursor.fetchall():
                tablespaces.append({'name': r[0], 'size': r[1], 'status': r[2]})

    except Exception as e:
        messages.error(request, f"Lỗi truy vấn Admin: {str(e)}")

    return render(request, 'clinic/admin_panel.html', {
        'sessions': sessions,
        'users': users,
        'tablespaces': tablespaces,
        'db_user': request.session.get('db_user')
    })

def kill_session(request, sid, serial):
    """Hành động: Ngắt kết nối một session"""
    if is_oracle_logged_in(request):
        try:
            with connection.cursor() as cursor:
                # Lệnh ALTER SYSTEM cần quyền cao
                sql = f"ALTER SYSTEM KILL SESSION '{sid},{serial}' IMMEDIATE"
                cursor.execute(sql)
            messages.success(request, f"Đã kill session {sid},{serial}")
        except Exception as e:
            messages.error(request, f"Không thể kill session: {str(e)}")
    return redirect('admin_panel')

def unlock_user(request, username):
    """Hành động: Mở khóa tài khoản bị lock"""
    if is_oracle_logged_in(request):
        try:
            with connection.cursor() as cursor:
                sql = f"ALTER USER {username} ACCOUNT UNLOCK"
                cursor.execute(sql)
            messages.success(request, f"Đã mở khóa tài khoản {username}")
        except Exception as e:
            messages.error(request, f"Lỗi mở khóa: {str(e)}")
    return redirect('admin_panel')

# --- PHẦN 6: RBAC MANAGEMENT ---

def rbac_panel(request):
    """Giao diện phân quyền cho Admin"""
    if not is_oracle_logged_in(request) or request.session.get('db_user') != 'CLINIC_ADMIN':
        messages.warning(request, "Chỉ Admin mới có quyền truy cập trang này!")
        return redirect('home')

    users_roles = []
    try:
        with connection.cursor() as cursor:
            # === CẬP NHẬT SQL TẠI ĐÂY ===
            # Thêm 'ROLE_KETOAN', 'ROLE_QUANLY' vào điều kiện lọc
            sql = """
                SELECT NV.MANV, NV.HOTEN, NV.CHUCVU, 
                       (SELECT GRANTED_ROLE FROM DBA_ROLE_PRIVS 
                        WHERE GRANTEE = NV.MANV 
                        AND GRANTED_ROLE IN ('ROLE_BACSI', 'ROLE_YTA', 'ROLE_LETAN', 'ROLE_KETOAN', 'ROLE_QUANLY') 
                        AND ROWNUM=1) AS CURRENT_ROLE
                FROM NHAN_VIEN NV
            """
            cursor.execute(sql)
            for r in cursor.fetchall():
                users_roles.append({
                    'username': r[0],
                    'fullname': r[1],
                    'job_title': r[2], 
                    'role_db': r[3] 
                })
    except Exception as e:
        messages.error(request, f"Lỗi lấy dữ liệu RBAC: {str(e)}")

    return render(request, 'clinic/rbac.html', {'users': users_roles})

def grant_role(request):
    """API: Gọi Procedure cấp quyền"""
    if request.method == 'POST' and request.session.get('db_user') == 'CLINIC_ADMIN':
        username = request.POST.get('username')
        role = request.POST.get('role')
        
        try:
            with connection.cursor() as cursor:
                # Gọi thủ tục USP_CAP_QUYEN
                cursor.callproc('USP_CAP_QUYEN', [username, role])
            messages.success(request, f"Đã cấp quyền {role} cho user {username}")
        except Exception as e:
            messages.error(request, f"Lỗi cấp quyền: {str(e)}")
            
    return redirect('rbac_panel')

# --- CẬP NHẬT HÀM security_dashboard ---
def security_dashboard(request):
    if not is_oracle_logged_in(request) or request.session.get('db_user') != 'CLINIC_ADMIN':
        messages.warning(request, "Chỉ Admin mới được vào khu vực an ninh!")
        return redirect('home')

    ols_data = []
    doctor_labels = []
    audit_logs = [] 
    deleted_items = []

    try:
        with connection.cursor() as cursor:
            # 1. Lấy dữ liệu OLS (Giữ nguyên code cũ)
            sql_data = """
                SELECT MAKH, HOTEN, 
                       CASE OLS_LABEL WHEN 2000 THEN 'CONF' WHEN 1000 THEN 'PUB' ELSE 'UNKNOWN' END
                FROM KHACH_HANG ORDER BY MAKH
            """
            cursor.execute(sql_data)
            for r in cursor.fetchall():
                ols_data.append({'makh': r[0], 'hoten': r[1], 'label': r[2]})

            # 2. Lấy danh sách Bác sĩ (Giữ nguyên code cũ)
            sql_users = """
                SELECT N.MANV, N.HOTEN,
                       NVL((SELECT MAX_READ_LABEL FROM DBA_SA_USERS 
                            WHERE POLICY_NAME = 'OLS_BENH_AN' AND USER_NAME = N.MANV), 'CHƯA GÁN')
                FROM NHAN_VIEN N WHERE N.CHUCVU IN ('BacSi', 'QuanLy') ORDER BY N.MANV
            """
            cursor.execute(sql_users)
            for r in cursor.fetchall():
                raw_label = r[2]
                display_label = 'PUB (Thường)'
                if 'CONF' in str(raw_label): display_label = 'CONF (VIP)'
                doctor_labels.append({'manv': r[0], 'hoten': r[1], 'current_label': display_label, 'is_vip': 'CONF' in str(raw_label)})

            # 3. === LẤY DỮ LIỆU FGA AUDIT (MỚI THÊM) ===
            # Lấy 10 hành động gần nhất truy cập vào Lương
            sql_audit = """
                SELECT DB_USER, TIMESTAMP, SQL_TEXT, STATEMENT_TYPE 
                FROM DBA_FGA_AUDIT_TRAIL 
                WHERE OBJECT_NAME = 'NHAN_VIEN' AND POLICY_NAME = 'AUDIT_XEM_LUONG'
                ORDER BY TIMESTAMP DESC 
                FETCH FIRST 10 ROWS ONLY
            """
            cursor.execute(sql_audit)
            for r in cursor.fetchall():
                audit_logs.append({
                    'user': r[0],
                    'time': r[1],
                    'sql': r[2], # Câu lệnh SQL thực thi
                    'action': r[3] # SELECT hay UPDATE
                })

            # 4. === TÌM DỮ LIỆU ĐÃ BỊ XÓA (DÙNG FLASHBACK VERSIONS QUERY) ===
            # Cách này mạnh hơn: Tìm tất cả các dòng có hành động Xóa (D) trong 15 phút qua
            try:
                sql_deleted = """
                    SELECT MA_LH, MA_KH, MANV, NGAY_HEN 
                    FROM LICH_HEN 
                    VERSIONS BETWEEN TIMESTAMP (SYSTIMESTAMP - INTERVAL '15' MINUTE) AND SYSTIMESTAMP
                    WHERE VERSIONS_OPERATION = 'D'  -- Chỉ lấy hành động DELETE
                    AND MA_LH NOT IN (SELECT MA_LH FROM LICH_HEN) -- Đảm bảo nó chưa được khôi phục
                """
                cursor.execute(sql_deleted)
                for r in cursor.fetchall():
                    # Kiểm tra xem ID này đã có trong danh sách chưa để tránh trùng lặp
                    # (Vì 1 ID có thể bị xóa đi tạo lại nhiều lần)
                    if not any(item['ma_lh'] == r[0] for item in deleted_items):
                        deleted_items.append({
                            'ma_lh': r[0], 'ma_kh': r[1], 'manv': r[2], 'ngay_hen': r[3]
                        })
            except Exception as e:
                if 'ORA-01466' in str(e):
                    print("Flashback không khả dụng do cấu trúc bảng thay đổi.")
                else:
                    print(f"Lỗi Flashback View: {e}")

    except Exception as e:
        messages.error(request, f"Lỗi Security Dashboard: {str(e)}")

    return render(request, 'clinic/security_dashboard.html', {
        'ols_data': ols_data,
        'doctor_labels': doctor_labels,
        'audit_logs': audit_logs,
        'deleted_items': deleted_items # Truyền sang template
    })

# --- THÊM HÀM MỚI: update_user_label ---
def update_user_label(request):
    """Hàm xử lý gán quyền VIP/THƯỜNG cho Bác sĩ"""
    if request.method == 'POST':
        manv = request.POST.get('manv')
        level_code = request.POST.get('level_code') # 'CONF' hoặc 'PUB'
        
        try:
            with connection.cursor() as cursor:
                # Gọi thủ tục gán nhãn của OLS
                # Set tất cả (Read/Write/Def/Row) về cùng 1 level để đồng bộ
                sql = """
                BEGIN
                    SA_USER_ADMIN.SET_USER_LABELS (
                        policy_name    => 'OLS_BENH_AN',
                        user_name      => %s, 
                        max_read_label => %s,
                        max_write_label=> %s,
                        def_label      => %s,
                        row_label      => %s
                    );
                END;
                """
                cursor.execute(sql, [manv, level_code, level_code, level_code, level_code])
            
            label_text = "VIP (Xem hết)" if level_code == 'CONF' else "THƯỜNG (Chỉ xem thường)"
            messages.success(request, f"Đã cấp quyền {label_text} cho {manv}")
            
        except Exception as e:
            messages.error(request, f"Lỗi cấp quyền OLS: {str(e)}")
            
    return redirect('security_dashboard')

# --- TRONG clinic/views.py ---

def flashback_recovery(request):
    """Hàm khôi phục dữ liệu Lịch Hẹn đã xóa (Phiên bản nâng cấp Versions Query)"""
    if not is_oracle_logged_in(request) or request.session.get('db_user') != 'CLINIC_ADMIN':
        return redirect('home')

    if request.method == 'POST':
        target_id = request.POST.get('target_id')
        
        try:
            with connection.cursor() as cursor:
                # 1. Kiểm tra tồn tại
                cursor.execute("SELECT COUNT(*) FROM LICH_HEN WHERE MA_LH = %s", [target_id])
                if cursor.fetchone()[0] > 0:
                    messages.warning(request, f"Lịch hẹn {target_id} đã tồn tại!")
                    return redirect('security_dashboard')

                # 2. LẤY DỮ LIỆU TỪ PHIÊN BẢN ĐÃ BỊ XÓA
                # Chúng ta tìm phiên bản 'D' (Delete) gần nhất của ID này
                sql_flashback = """
                    SELECT MA_LH, MA_KH, MANV, NGAY_HEN, GHI_CHU 
                    FROM LICH_HEN 
                    VERSIONS BETWEEN TIMESTAMP (SYSTIMESTAMP - INTERVAL '15' MINUTE) AND SYSTIMESTAMP
                    WHERE MA_LH = %s 
                    AND VERSIONS_OPERATION = 'D'
                    ORDER BY VERSIONS_ENDTIME DESC
                    FETCH FIRST 1 ROWS ONLY
                """
                cursor.execute(sql_flashback, [target_id])
                row = cursor.fetchone()

                if row:
                    # 3. INSERT LẠI VÀO BẢNG
                    ghi_chu_val = row[4].read() if hasattr(row[4], 'read') else row[4]
                    
                    sql_restore = """
                        INSERT INTO LICH_HEN (MA_LH, MA_KH, MANV, NGAY_HEN, GHI_CHU)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql_restore, [row[0], row[1], row[2], row[3], ghi_chu_val])
                    messages.success(request, f"Khôi phục thành công {target_id} (Dữ liệu từ phiên bản xóa gần nhất)!")
                else:
                    messages.error(request, f"Không tìm thấy dữ liệu gốc của {target_id} trong bộ nhớ Flashback.")

        except Exception as e:
            messages.error(request, f"Lỗi Flashback: {str(e)}")

    return redirect('security_dashboard')