from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('google/login/', views.google_login, name='google_login'),
    path('google/callback/', views.google_callback, name='google_callback'),
    path('loading/', views.loading_preview, name='loading_preview'),
    path('preview/', views.preview_matrix, name='preview_matrix'),
    path('sync/', views.sync_esse3, name='sync_esse3'),
    # path('', views.sync_esse3, name='sync_esse3'),
]