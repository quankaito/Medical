from django import forms

class LoginForm(forms.Form):
    username = forms.CharField(label="Tên đăng nhập (User Oracle)", max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput(attrs={'class': 'form-control'}))

class RegisterForm(forms.Form):
    # Thông tin tài khoản Oracle
    username = forms.CharField(label="Tên đăng nhập (Sẽ tạo User Oracle)", max_length=10, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    # Thông tin nhân viên (để lưu vào bảng NHAN_VIEN)
    hoten = forms.CharField(label="Họ và Tên", max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={'class': 'form-control'}))
    cccd = forms.CharField(label="CCCD", widget=forms.TextInput(attrs={'class': 'form-control'}))
    # Chức vụ tạm thời cho chọn (sau này sẽ quản lý chặt hơn)
    chucvu = forms.ChoiceField(choices=[('BacSi', 'Bác Sĩ'), ('YTa', 'Y Tá'), ('LeTan', 'Lễ Tân')], widget=forms.Select(attrs={'class': 'form-select'}))