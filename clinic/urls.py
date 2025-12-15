from django.contrib import admin
from django.urls import path
from clinic import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard & API Giải mã
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/decrypt-salary/', views.decrypt_salary, name='decrypt_salary'),
    path('api/decrypt-medical/', views.decrypt_medical, name='decrypt_medical'),

    # --- CRUD NHÂN VIÊN ---
    path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/edit/<str:manv>/', views.edit_staff, name='edit_staff'),
    path('staff/delete/<str:manv>/', views.delete_staff, name='delete_staff'),

    # --- CRUD KHÁCH HÀNG ---
    path('customer/add/', views.add_customer, name='add_customer'),
    path('customer/edit/<str:makh>/', views.edit_customer, name='edit_customer'),
    path('customer/delete/<str:makh>/', views.delete_customer, name='delete_customer'),
]