from django.db import models

class NhanVien(models.Model):
    manv = models.CharField(max_length=10, primary_key=True)
    hoten = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    luong = models.CharField(max_length=200)
    cccd = models.CharField(max_length=200)
    chucvu = models.CharField(max_length=50)

    class Meta:
        managed = False # Django không được sửa cấu trúc bảng này
        db_table = 'NHAN_VIEN'
        verbose_name = 'Nhân Viên'
        verbose_name_plural = 'Nhân Viên'

class KhachHang(models.Model):
    makh = models.CharField(max_length=10, primary_key=True)
    hoten = models.CharField(max_length=100)
    ngaysinh = models.DateField()
    sdt = models.CharField(max_length=20)
    benhan = models.CharField(max_length=2000)

    class Meta:
        managed = False
        db_table = 'KHACH_HANG'
        verbose_name = 'Khách Hàng'
        verbose_name_plural = 'Khách Hàng'