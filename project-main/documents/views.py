# documents/views.py

import os
import mimetypes
from datetime import datetime
import logging
from itertools import chain

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q, Count, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import (CreateView, FormView,
                                  ListView, UpdateView)
from django.views.generic.detail import SingleObjectMixin
from django import forms

from guardian.shortcuts import assign_perm, get_objects_for_user

from users.permissions import (user_can_comment_on_document,
                               user_can_create_document,
                               user_can_create_folder,
                               user_can_delete_document,
                               user_can_delete_folder, user_can_edit_document,
                               user_can_edit_folder,
                               user_can_share_document,
                               user_can_view_document, user_can_view_folder)

from .forms import (CommentForm, DocumentUpdateForm, DocumentUploadForm,
                    DocumentVersionUploadForm, FolderCreateForm,
                    FolderDeleteForm, FolderUpdateForm)
from .models import (ActivityLog, Comment, Document, DocumentVersion, Folder,
                     Tag)

# --- Logger ---
logger = logging.getLogger(__name__)
# Added a comment to force reload

# --- Helper Functions ---

def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def _log_activity(user, action_type, document=None, folder=None, details="", ip_address=""):
    """Helper to create an ActivityLog entry."""
    ActivityLog.objects.create(
        uzytkownik=user,
        typ_aktywnosci=action_type,
        dokument=document,
        folder=folder,
        szczegoly=details,
        adres_ip=ip_address
    )
# --- Main Views (Class-Based) ---

class HomeView(LoginRequiredMixin, ListView):
    template_name = 'documents/home.html'
    context_object_name = 'items'

    def get_queryset(self):
        folder_id = self.kwargs.get('folder_id')
        self.current_folder = None
        user = self.request.user

        if folder_id:
            self.current_folder = get_object_or_404(Folder, pk=folder_id)
            if not user_can_view_folder(user, self.current_folder):
                raise PermissionDenied("You do not have permission to view this folder.")

        browseable_folders = get_objects_for_user(user, 'documents.browse_folder', klass=Folder)
        browseable_documents = get_objects_for_user(user, 'documents.browse_document', klass=Document)

        folder_qs = browseable_folders.filter(rodzic=self.current_folder)
        document_qs = browseable_documents.filter(folder=self.current_folder, usunieto=False)
        
        folder_qs = folder_qs.annotate(
            doc_count=Count('documents', filter=Q(documents__usunieto=False)),
            subfolder_count=Count('podkatalogi')
        ).select_related('wlasciciel__profile').prefetch_related('tagi')

        document_qs = document_qs.select_related('wlasciciel__profile', 'folder').prefetch_related('tagi')
        
        return list(folder_qs) + list(document_qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        all_items = context['items']
        folders = [item for item in all_items if isinstance(item, Folder)]
        documents = [item for item in all_items if isinstance(item, Document)]
        
        for item in folders:
            item.current_user_can_edit = user_can_edit_folder(user, item)
            item.current_user_can_delete = user_can_delete_folder(user, item)
        for item in documents:
            item.current_user_can_edit = user_can_edit_document(user, item)
            item.current_user_can_delete = user_can_delete_document(user, item)
            
        context['folders'] = sorted(folders, key=lambda f: f.nazwa)
        context['documents'] = sorted(documents, key=lambda d: d.nazwa)

        context['current_folder'] = self.current_folder
        context['is_root'] = self.current_folder is None
        context['user_can_create_documents'] = user_can_create_document(user, self.current_folder)
        context['user_can_create_folders'] = user_can_create_folder(user, self.current_folder)

        breadcrumbs = []
        if self.current_folder:
            temp_folder = self.current_folder
            while temp_folder:
                breadcrumbs.insert(0, temp_folder)
                temp_folder = temp_folder.rodzic
        context['breadcrumbs'] = breadcrumbs

        if context['is_root']:
            user_docs = get_objects_for_user(user, 'documents.browse_document', klass=Document).filter(usunieto=False)
            user_folders = get_objects_for_user(user, 'documents.browse_folder', klass=Folder)
            stats = user_docs.aggregate(total_size=Sum('rozmiar_pliku'))
            
            context['total_documents'] = user_docs.count()
            context['total_folders'] = user_folders.count()
            context['total_size'] = self._human_readable_size(stats['total_size'] or 0)
            
        return context

    def _human_readable_size(self, size_bytes):
        if size_bytes is None or size_bytes == 0: return "0 B"
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0: return f"{size:3.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

class DocumentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'page_obj'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_superuser or (hasattr(self.request.user, 'profile') and self.request.user.profile.is_admin)

    def get_queryset(self):
        queryset = get_objects_for_user(self.request.user, 'documents.browse_document', klass=Document)
        queryset = queryset.filter(usunieto=False).select_related('wlasciciel__profile', 'folder').prefetch_related('tagi')
        self.name_query = self.request.GET.get('name', '')
        self.file_type_query = self.request.GET.get('file_type', '')

        if self.name_query:
            queryset = queryset.filter(nazwa__icontains=self.name_query)
        if self.file_type_query:
            queryset = queryset.filter(typ_pliku__icontains=self.file_type_query)
            
        return queryset.order_by('-ostatnia_modyfikacja')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        for doc_item in context['page_obj']:
            doc_item.current_user_can_edit = user_can_edit_document(user, doc_item)
            doc_item.current_user_can_delete = user_can_delete_document(user, doc_item)
        context['name_query'] = self.name_query
        context['file_type_query'] = self.file_type_query
        return context

@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document.objects.prefetch_related(
        'tagi',
        'wersje__utworzony_przez__profile',
        'metadane',
        Prefetch('komentarze', queryset=Comment.objects.filter(aktywny=True, wersja_dokumentu__isnull=True).select_related('uzytkownik__profile').order_by('data_utworzenia'))
    ).select_related('wlasciciel__profile', 'folder'), pk=pk, usunieto=False)

    if not user_can_view_document(request.user, document):
        raise PermissionDenied("You do not have permission to view this document.")

    # Handle comment submission
    # Fetch all comments related to this document, including those linked to versions
    all_comments = Comment.objects.filter(
        Q(dokument=document) | Q(wersja_dokumentu__dokument=document),
        aktywny=True
    ).select_related('uzytkownik__profile', 'wersja_dokumentu').order_by('data_utworzenia')

    # Initialize the main comment form
    # Default to commenting on the document itself, or the latest version if available
    latest_version = document.wersje.order_by('-numer_wersji').first()
    initial_comment_data = {'dokument': document.pk}
    if latest_version:
        initial_comment_data['wersja_dokumentu'] = latest_version.pk
    
    comment_form = CommentForm(initial=initial_comment_data)

    # Handle comment submission (existing logic, but ensure wersja_dokumentu is handled)
    if request.method == 'POST':
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            new_comment = comment_form.save(commit=False)
            new_comment.uzytkownik = request.user
            new_comment.dokument = document # Ensure this is always set

            # The form should now handle wersja_dokumentu if it's in cleaned_data
            # If wersja_dokumentu is not provided by the form, it will be None, meaning a document-level comment
            
            version_pk_from_form = comment_form.cleaned_data.get('wersja_dokumentu')
            if version_pk_from_form:
                # If a DocumentVersion object is returned, get its primary key
                if hasattr(version_pk_from_form, 'pk'):
                    version_pk_from_form = version_pk_from_form.pk
                version = get_object_or_404(DocumentVersion, pk=version_pk_from_form, dokument=document)
                new_comment.wersja_dokumentu = version
                log_details = f"Skomentował wersję {version.numer_wersji} dokumentu '{document.nazwa}'"
            else:
                log_details = f"Skomentował dokument '{document.nazwa}'"

            new_comment.save()
            _log_activity(request.user, 'komentowanie', document=document, details=log_details, ip_address=get_client_ip(request))
            messages.success(request, 'Komentarz dodany pomyślnie.')
            return redirect('documents:document_detail', pk=document.pk)

    context = {
        'document': document,
        'all_comments': all_comments, # New context variable
        'comment_form': comment_form,
        'can_edit_this_document': user_can_edit_document(request.user, document),
        'can_delete_this_document': user_can_delete_document(request.user, document),
        'can_comment_on_this_document': user_can_comment_on_document(request.user, document),
        'can_download_this_document': request.user.has_perm('documents.download_document', document),
        'can_preview_this_document': document.can_preview(),
        'versions': document.wersje.all().order_by('-numer_wersji'), # Still need versions for history display
    }

    # Add version-specific comments to each version object for template display
    for version in context['versions']:
        version.comments = version.komentarze.filter(aktywny=True).select_related('uzytkownik__profile').order_by('data_utworzenia')
    return render(request, 'documents/document_detail.html', context)

@login_required
def document_download(request, pk):
    document = get_object_or_404(Document, pk=pk)
    if not user_can_view_document(request.user, document):
        raise PermissionDenied("You do not have permission to download this document.")
    
    file_path = document.plik.path
    if not os.path.exists(file_path):
        raise Http404("Document file not found.")

    _log_activity(request.user, 'pobieranie', document=document, details=f"Pobrał dokument '{document.nazwa}'", ip_address=get_client_ip(request))
    
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'
    
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{document.nazwa}.{document.typ_pliku}"'
    return response

@login_required
def document_preview(request, pk):
    document = get_object_or_404(Document, pk=pk)
    if not user_can_view_document(request.user, document):
        raise PermissionDenied("You do not have permission to preview this document.")

    file_path = document.plik.path
    if not os.path.exists(file_path):
        raise Http404("Document file not found.")

    content_type, encoding = mimetypes.guess_type(file_path)
    
    # For simplicity, let's assume we can preview text files directly
    # For other types, we might just show a message or link to download
    if content_type and content_type.startswith('text/'):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        _log_activity(request.user, 'podglad', document=document, details=f"Wyświetlił podgląd dokumentu '{document.nazwa}'", ip_address=get_client_ip(request))
        return render(request, 'documents/document_preview.html', {'document': document, 'content': content, 'is_text': True})
    else:
        _log_activity(request.user, 'podglad', document=document, details=f"Próbował wyświetlić podgląd dokumentu '{document.nazwa}' (nieobsługiwany typ)", ip_address=get_client_ip(request))
        messages.info(request, "Podgląd dla tego typu pliku nie jest obsługiwany. Możesz pobrać plik.")
        return redirect('documents:document_detail', pk=document.pk)

@login_required
def document_version_upload(request, pk):
    document = get_object_or_404(Document, pk=pk)
    if not user_can_edit_document(request.user, document):
        raise PermissionDenied("You do not have permission to upload new versions for this document.")

    if request.method == 'POST':
        form = DocumentVersionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            new_version_file = form.cleaned_data['plik']
            # Determine the next version number
            last_version = document.wersje.order_by('-numer_wersji').first()
            if last_version:
                next_version_number = last_version.numer_wersji + 1
            else:
                next_version_number = 1

            # Determine the next version number
            last_version = document.wersje.order_by('-numer_wersji').first()
            if last_version:
                next_version_number = last_version.numer_wersji + 1
            else:
                next_version_number = 1

            DocumentVersion.objects.create(
                dokument=document,
                numer_wersji=next_version_number,
                plik=new_version_file,
                rozmiar_pliku=new_version_file.size,
                utworzony_przez=request.user
            )
            # Update main document's file to the latest version
            document.plik = new_version_file
            document.nazwa_pliku = new_version_file.name
            document.rozmiar_pliku = new_version_file.size
            document.typ_pliku = mimetypes.guess_type(new_version_file.name)[0] or 'application/octet-stream'
            document.ostatnia_modyfikacja = datetime.now()
            document.save()

            _log_activity(request.user, 'nowa_wersja', document=document, details=f"Przesłał nową wersję dokumentu '{document.nazwa}'", ip_address=get_client_ip(request))
            messages.success(request, 'Nowa wersja dokumentu została pomyślnie przesłana.')
            return redirect('documents:document_detail', pk=document.pk)
    else:
        form = DocumentVersionUploadForm()
    
    context = {'document': document, 'form': form}
    return render(request, 'documents/document_version_upload.html', context)

@login_required
def document_version_download(request, document_pk, version_pk):
    document = get_object_or_404(Document, pk=document_pk)
    if not user_can_view_document(request.user, document):
        raise PermissionDenied("You do not have permission to download this document version.")

    version = get_object_or_404(DocumentVersion, pk=version_pk, dokument=document)
    
    file_path = version.plik.path
    if not os.path.exists(file_path):
        raise Http404("Document version file not found.")

    _log_activity(request.user, 'pobieranie_wersji', document=document, details=f"Pobrał wersję {version.nazwa_pliku} dokumentu '{document.nazwa}'", ip_address=get_client_ip(request))
    
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'
    
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{version.nazwa_pliku}"'
    return response

class DocumentUploadView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Document
    form_class = DocumentUploadForm
    template_name = 'documents/document_upload.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        return user_can_create_document(self.request.user)

    def form_valid(self, form):
        form.instance.wlasciciel = self.request.user
        self.object = form.save()
        assign_perm('documents.browse_document', self.request.user, self.object) # Explicitly assign browse permission to owner
        _log_activity(self.request.user, 'tworzenie', document=self.object, details=f"Utworzył dokument '{self.object.nazwa}'", ip_address=get_client_ip(self.request))
        messages.success(self.request, f'Dokument "{self.object.nazwa}" został przesłany pomyślnie.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('documents:document_detail', kwargs={'pk': self.object.pk})

class DocumentEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Document
    form_class = DocumentUpdateForm
    template_name = 'documents/document_edit.html'
    def test_func(self):
        return user_can_edit_document(self.request.user, self.get_object())
    def form_valid(self, form):
        _log_activity(self.request.user, 'edycja', document=self.object, details=f"Zaktualizował dokument '{self.object.nazwa}'", ip_address=get_client_ip(self.request))
        messages.success(self.request, f'Dokument "{self.object.nazwa}" został zaktualizowany.')
        return super().form_valid(form)
    def get_success_url(self):
        return reverse('documents:document_detail', kwargs={'pk': self.object.pk})

class DocumentDeleteView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'documents/document_delete.html'
    form_class = type('EmptyForm', (forms.Form,), {})
    def test_func(self):
        return user_can_delete_document(self.request.user, get_object_or_404(Document, pk=self.kwargs['pk']))
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['document'] = get_object_or_404(Document, pk=self.kwargs['pk'])
        return context
    def form_valid(self, form):
        document = get_object_or_404(Document, pk=self.kwargs['pk'])
        _log_activity(self.request.user, 'usuniecie', document=document, details=f"Usunął dokument '{document.nazwa}'", ip_address=get_client_ip(self.request))
        document.delete()
        messages.success(self.request, 'Dokument został pomyślnie usunięty.')
        return redirect(reverse('documents:home'))

class FolderCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Folder
    form_class = FolderCreateForm
    template_name = 'documents/folder_create.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        return user_can_create_folder(self.request.user)

    def form_valid(self, form):
        form.instance.wlasciciel = self.request.user
        self.object = form.save()
        assign_perm('browse_folder', self.request.user, self.object) # Explicitly assign browse permission to owner
        _log_activity(self.request.user, 'tworzenie', folder=self.object, details=f"Utworzył folder '{self.object.nazwa}'", ip_address=get_client_ip(self.request))
        messages.success(self.request, f'Folder "{self.object.nazwa}" został utworzony pomyślnie.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('documents:home')

class FolderListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Folder
    template_name = 'documents/folder_list.html'
    context_object_name = 'page_obj'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_superuser or (hasattr(self.request.user, 'profile') and self.request.user.profile.is_admin)

    def get_queryset(self):
        queryset = get_objects_for_user(self.request.user, 'documents.browse_folder', klass=Folder)
        queryset = queryset.select_related('wlasciciel__profile').prefetch_related('tagi')
        self.name_query = self.request.GET.get('name', '')

        if self.name_query:
            queryset = queryset.filter(nazwa__icontains=self.name_query)
            
        return queryset.order_by('-data_utworzenia')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        for folder_item in context['page_obj']:
            folder_item.current_user_can_edit = user_can_edit_folder(user, folder_item)
            folder_item.current_user_can_delete = user_can_delete_folder(user, folder_item)
        context['name_query'] = self.name_query
        return context

class FolderEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Folder
    form_class = FolderUpdateForm
    template_name = 'documents/folder_edit.html'

    def test_func(self):
        return user_can_edit_folder(self.request.user, self.get_object())

    def form_valid(self, form):
        _log_activity(self.request.user, 'edycja', folder=self.object, details=f"Zaktualizował folder '{self.object.nazwa}'", ip_address=get_client_ip(self.request))
        messages.success(self.request, f'Folder "{self.object.nazwa}" został zaktualizowany.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('documents:folder_view', kwargs={'folder_id': self.object.pk})

class FolderDeleteView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'documents/folder_delete.html'
    form_class = type('EmptyForm', (forms.Form,), {})

    def test_func(self):
        return user_can_delete_folder(self.request.user, get_object_or_404(Folder, pk=self.kwargs['pk']))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['folder'] = get_object_or_404(Folder, pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        folder = get_object_or_404(Folder, pk=self.kwargs['pk'])
        _log_activity(self.request.user, 'usuniecie', folder=folder, details=f"Usunął folder '{folder.nazwa}'", ip_address=get_client_ip(self.request))
        folder.delete()
        messages.success(self.request, 'Folder został pomyślnie usunięty.')
        return redirect(reverse('documents:home'))

@login_required
def search_results(request):
    query = request.GET.get('query', '')
    documents = Document.objects.none()
    folders = Folder.objects.none()

    if query:
        # Search in documents
        documents = get_objects_for_user(request.user, 'documents.browse_document', klass=Document).filter(
            Q(nazwa__icontains=query) | Q(opis__icontains=query)
        ).filter(usunieto=False).select_related('wlasciciel__profile', 'folder').prefetch_related('tagi')

        # Search in folders
        folders = get_objects_for_user(request.user, 'documents.browse_folder', klass=Folder).filter(
            Q(nazwa__icontains=query) | Q(opis__icontains=query)
        ).select_related('wlasciciel__profile').prefetch_related('tagi')

        _log_activity(request.user, 'wyszukiwanie', details=f"Wyszukał '{query}'", ip_address=get_client_ip(request))

    context = {
        'query': query,
        'documents': documents,
        'folders': folders,
    }
    return render(request, 'documents/search_results.html', context)