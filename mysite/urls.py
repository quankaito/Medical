from django.contrib import admin
from django.urls import path
from clinic import views

urlpatterns = [
    # --- ADMIN & AUTH ---
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # --- DASHBOARD & API GIẢI MÃ ---
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/decrypt-salary/', views.decrypt_salary, name='decrypt_salary'),
    path('api/decrypt-medical/', views.decrypt_medical, name='decrypt_medical'),

    # --- CRUD NHÂN VIÊN (STAFF) ---
    path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/edit/<str:manv>/', views.edit_staff, name='edit_staff'),
    path('staff/delete/<str:manv>/', views.delete_staff, name='delete_staff'), # <--- Dòng này đang thiếu nên gây lỗi

    # --- CRUD KHÁCH HÀNG (CUSTOMER) ---
    path('customer/add/', views.add_customer, name='add_customer'),
    path('customer/edit/<str:makh>/', views.edit_customer, name='edit_customer'),
    path('customer/delete/<str:makh>/', views.delete_customer, name='delete_customer'),

    # --- PHẦN 4: APP ENCRYPTION ---
    path('appt/add/', views.add_appointment, name='add_appointment'),
    path('appt/delete/<str:ma_lh>/', views.delete_appointment, name='delete_appointment'),
    path('api/decrypt-appt/', views.decrypt_appt_app, name='decrypt_appt_app'),

    path('record/add/', views.add_record, name='add_record'),
    path('record/delete/<str:ma_hs>/', views.delete_record, name='delete_record'),
    path('api/decrypt-record/', views.decrypt_record_app, name='decrypt_record_app'),

    # --- UPDATE LICH HEN ---
    path('appt/edit/<str:ma_lh>/', views.edit_appointment, name='edit_appointment'), # Mới

    # --- UPDATE HO SO ---
    path('record/edit/<str:ma_hs>/', views.edit_record, name='edit_record'), # Mới

    # --- CRUD Y KIEN BAC SI (RSA APP) ---
    path('opinion/add/', views.add_opinion, name='add_opinion'), # Mới
    path('opinion/delete/<str:ma_yk>/', views.delete_opinion, name='delete_opinion'), # Mới
    path('api/decrypt-opinion/', views.decrypt_opinion_app, name='decrypt_opinion_app'), # Mới
    path('opinion/edit/<str:ma_yk>/', views.edit_opinion, name='edit_opinion'),
    # --- PHẦN 5: ADMIN SYSTEM ---
    path('system-admin/', views.admin_panel, name='admin_panel'),
    path('system/kill-session/<str:sid>/<str:serial>/', views.kill_session, name='kill_session'),
    path('system/unlock-user/<str:username>/', views.unlock_user, name='unlock_user'),
    # --- PHẦN 6: RBAC ---
    path('rbac/', views.rbac_panel, name='rbac_panel'),
    path('rbac/grant/', views.grant_role, name='grant_role'),
    path('security/', views.security_dashboard, name='security_dashboard'),
    path('security/update_label/', views.update_user_label, name='update_user_label'),
    path('security/flashback/', views.flashback_recovery, name='flashback_recovery'),
]