from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    # Dashboard jest teraz pod /documents/home/
    path('home/', views.HomeView.as_view(), name='home'),  # <<< KLUCZOWA ZMIANA
    path('folder/<int:folder_id>/', views.HomeView.as_view(), name='folder_view'),
    
    # Reszta URL-i bez zmian
    
    path('documents/upload/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('documents/upload/<int:folder_id>/', views.DocumentUploadView.as_view(), name='document_upload_to_folder'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/<int:pk>/edit/', views.DocumentEditView.as_view(), name='document_edit'),
    path('documents/<int:pk>/delete/', views.DocumentDeleteView.as_view(), name='document_delete'),
    path('documents/<int:pk>/download/', views.document_download, name='document_download'),
    path('documents/<int:pk>/preview/', views.document_preview, name='document_preview'),
    path('documents/<int:pk>/version/upload/', views.document_version_upload, name='document_version_upload'),
    
    # Folders (admin only)
    
    path('folders/create/', views.FolderCreateView.as_view(), name='folder_create'),
    path('folders/create/<int:parent_id>/', views.FolderCreateView.as_view(), name='folder_create_in_parent'),
    path('folder/<int:pk>/detail/', views.FolderDetailView.as_view(), name='folder_detail'),
    path('folders/<int:pk>/edit/', views.FolderEditView.as_view(), name='folder_edit'),
    path('folders/<int:pk>/delete/', views.FolderDeleteView.as_view(), name='folder_delete'),
    path('folders/<int:pk>/download/zip/', views.folder_download_zip, name='folder_download_zip'),
    path('folders/<int:pk>/download/zip/', views.folder_download_zip, name='folder_download_zip'),
    path('documents/<int:document_pk>/version/<int:version_pk>/download/', views.document_version_download, name='document_version_download'),
    
    # Search and API
    path('search/', views.search_results, name='search_results'),
]