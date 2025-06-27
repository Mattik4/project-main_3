from django import forms
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from .models import Document, Folder, Tag, Comment
import os
from guardian.shortcuts import get_objects_for_user


class DocumentUploadForm(forms.ModelForm):
    """Enhanced form for document upload with file handling"""
    
    plik = forms.FileField(
        label='Plik',
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'docx', 'doc', 'xlsx', 'xls', 'txt', 'png', 'jpg', 'jpeg']
        )],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.docx,.doc,.xlsx,.xls,.txt,.png,.jpg,.jpeg',
            'id': 'file-input'
        }),
        help_text="Obsługiwane formaty: PDF, DOCX, DOC, XLSX, XLS, TXT, PNG, JPG, JPEG. Maksymalny rozmiar: 50MB."
    )
    
    nazwa = forms.CharField(
        label='Nazwa dokumentu',
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Zostanie automatycznie ustawiona na podstawie nazwy pliku'
        }),
        help_text="Opcjonalnie - jeśli puste, zostanie użyta nazwa pliku"
    )
    
    opis = forms.CharField(
        label='Opis',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Opcjonalny opis dokumentu'
        })
    )
    
    class Meta:
        model = Document
        fields = ['plik', 'nazwa', 'opis', 'folder', 'tagi', 'status']
        widgets = {
            'folder': forms.Select(attrs={'class': 'form-control'}),
            'tagi': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Show only folders owned by user or with permissions
            # Allow selecting no folder (root)
            self.fields['folder'].required = False
            self.fields['folder'].empty_label = "Folder główny"

            if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
                self.fields['folder'].queryset = Folder.objects.all()
            else:
                # Get all folders the user can browse
                browseable_folders = get_objects_for_user(user, 'documents.browse_folder', klass=Folder)
                self.fields['folder'].queryset = browseable_folders
            
            # Set default folder if user has any and no initial folder is set
            if self.fields['folder'].queryset.exists() and not self.initial.get('folder'):
                # Try to set initial to the first browseable folder, or leave as None for root
                pass # Let it be None by default if not explicitly set
    
    def clean_plik(self):
        """Validate uploaded file"""
        plik = self.cleaned_data.get('plik')
        
        if not plik:
            raise ValidationError("Musisz wybrać plik do wgrania.")
        
        # Check file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        if plik.size > max_size:
            raise ValidationError(f"Plik jest za duży! Maksymalny rozmiar to 50MB. Twój plik ma {plik.size / 1024 / 1024:.1f}MB.")
        
        # Check file extension
        allowed_extensions = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'txt', 'png', 'jpg', 'jpeg']
        ext = os.path.splitext(plik.name)[1].lower().lstrip('.')
        
        if ext not in allowed_extensions:
            raise ValidationError(f"Nieobsługiwany format pliku. Dozwolone formaty: {', '.join(allowed_extensions)}")
        
        # Basic security check - don't allow executable files
        dangerous_extensions = ['exe', 'bat', 'cmd', 'com', 'scr', 'vbs', 'js']
        if ext in dangerous_extensions:
            raise ValidationError("Ze względów bezpieczeństwa, ten typ pliku nie jest dozwolony.")
        
        return plik
    
    def clean_nazwa(self):
        """Clean document name"""
        nazwa = self.cleaned_data.get('nazwa', '').strip()
        
        # If no name provided, we'll use filename in save()
        if not nazwa:
            return nazwa
        
        # Validate name
        if len(nazwa) > 255:
            raise ValidationError("Nazwa dokumentu nie może być dłuższa niż 255 znaków.")
        
        # Remove dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        for char in dangerous_chars:
            if char in nazwa:
                raise ValidationError(f"Nazwa nie może zawierać znaku: {char}")
        
        return nazwa
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        plik = cleaned_data.get('plik')
        nazwa = cleaned_data.get('nazwa')
        
        # If no name provided, set it from filename
        if plik and not nazwa:
            cleaned_data['nazwa'] = os.path.basename(plik.name)
        
        return cleaned_data


class DocumentUpdateForm(forms.ModelForm):
    """Form for updating document metadata (not the file itself)"""
    
    class Meta:
        model = Document
        fields = ['nazwa', 'opis', 'folder', 'tagi', 'status']
        widgets = {
            'nazwa': forms.TextInput(attrs={'class': 'form-control'}),
            'opis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'folder': forms.Select(attrs={'class': 'form-control'}),
            'tagi': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
                self.fields['folder'].queryset = Folder.objects.all()
            else:
                browseable_folders = get_objects_for_user(user, 'documents.browse_folder', klass=Folder)
                self.fields['folder'].queryset = browseable_folders


class DocumentVersionUploadForm(forms.Form):
    """Form for uploading new version of existing document"""
    
    plik = forms.FileField(
        label='Nowa wersja pliku',
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'docx', 'doc', 'xlsx', 'xls', 'txt', 'png', 'jpg', 'jpeg']
        )],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.docx,.doc,.xlsx,.xls,.txt,.png,.jpg,.jpeg'
        })
    )
    
    komentarz = forms.CharField(
        label='Komentarz do wersji',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Opisz zmiany w tej wersji...'
        })
    )
    
    def clean_plik(self):
        """Validate uploaded file"""
        plik = self.cleaned_data.get('plik')
        
        if not plik:
            raise ValidationError("Musisz wybrać plik.")
        
        # Check file size
        max_size = 50 * 1024 * 1024  # 50MB
        if plik.size > max_size:
            raise ValidationError("Plik jest za duży! Maksymalny rozmiar to 50MB.")
        
        return plik


class FolderCreateForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['nazwa', 'opis', 'rodzic', 'tagi']  # DODANO 'tagi'
        widgets = {
            'nazwa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nazwa folderu'}),
            'opis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Opis folderu (opcjonalny)'}),
            'rodzic': forms.Select(attrs={'class': 'form-control'}),
            'tagi': forms.CheckboxSelectMultiple(),  # DODANO
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Allow selecting no parent folder (root)
            self.fields['rodzic'].required = False
            self.fields['rodzic'].empty_label = "Folder główny"

            if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
                self.fields['rodzic'].queryset = Folder.objects.all()
            else:
                # Get all folders the user can browse
                browseable_folders = get_objects_for_user(user, 'documents.browse_folder', klass=Folder)
                self.fields['rodzic'].queryset = browseable_folders


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['tresc', 'wersja_dokumentu', 'dokument']
        widgets = {
            'tresc': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dodaj komentarz...', 
                'required': True
            }),
            'wersja_dokumentu': forms.HiddenInput(), # This will be set dynamically
            'dokument': forms.HiddenInput(), # Add this line
        }
        labels = {
            'tresc': ''  # Usuwa label, bo mamy placeholder
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make wersja_dokumentu field not required at form level, as it's optional
        self.fields['wersja_dokumentu'].required = False

    def clean_tresc(self):
        tresc = self.cleaned_data.get('tresc', '').strip()
        if not tresc:
            raise ValidationError("Komentarz nie może być pusty.")
        if len(tresc) < 3:
            raise ValidationError("Komentarz musi mieć co najmniej 3 znaki.")
        if len(tresc) > 1000:
            raise ValidationError("Komentarz nie może być dłuższy niż 1000 znaków.")
        return tresc


class TagCreateForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['nazwa', 'kolor']
        widgets = {
            'nazwa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nazwa tagu'}),
            'kolor': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }

class TagUpdateForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['nazwa', 'kolor']
        widgets = {
            'nazwa': forms.TextInput(attrs={'class': 'form-control'}),
            'kolor': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }





class DocumentShareForm(forms.Form):
    """Form for sharing documents with other users"""
    user_email = forms.EmailField(
        label='Email użytkownika',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'jan.kowalski@firma.pl'
        })
    )
    
    permission_level = forms.ChoiceField(
        label='Poziom uprawnień',
        choices=[
            ('browse_document', 'Tylko przeglądanie'),
            ('download_document', 'Przeglądanie i pobieranie'),
            ('comment_document', 'Przeglądanie i komentowanie'),
            ('change_document', 'Pełne uprawnienia do edycji'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    expiry_date = forms.DateTimeField(
        label='Data wygaśnięcia (opcjonalnie)',
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )


class BulkActionForm(forms.Form):
    """Form for bulk actions on documents"""
    action = forms.ChoiceField(
        choices=[
            ('publish', 'Opublikuj'),
            ('archive', 'Zarchiwizuj'),
            ('delete', 'Usuń'),
            ('move', 'Przenieś do folderu'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    target_folder = forms.ModelChoiceField(
        queryset=Folder.objects.all(),
        required=False,
        empty_label="Wybierz folder",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
                self.fields['target_folder'].queryset = Folder.objects.all()
            else:
                # Get all folders the user can browse
                browseable_folders = get_objects_for_user(user, 'documents.browse_folder', klass=Folder)
                self.fields['target_folder'].queryset = browseable_folders

class FolderUpdateForm(forms.ModelForm):
    """Form for updating folder metadata"""
    
    class Meta:
        model = Folder
        fields = ['nazwa', 'opis', 'rodzic', 'tagi']  # DODANO 'tagi'
        widgets = {
            'nazwa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nazwa folderu'}),
            'opis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Opis folderu (opcjonalny)'}),
            'rodzic': forms.Select(attrs={'class': 'form-control'}),
            'tagi': forms.CheckboxSelectMultiple(),  # DODANO
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        
        if user:
            # Allow selecting no parent folder (root)
            self.fields['rodzic'].required = False
            self.fields['rodzic'].empty_label = "Folder główny"

            # Show folders user can access, but exclude current folder and its children to prevent circular references
            if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
                queryset = Folder.objects.all()
            else:
                # Get all folders the user can browse
                browseable_folders = get_objects_for_user(user, 'documents.browse_folder', klass=Folder)
                queryset = browseable_folders
            
            # Exclude current folder and its descendants to prevent circular references
            if instance:
                descendants = self._get_descendants(instance)
                exclude_ids = [instance.id] + list(descendants.values_list('id', flat=True))
                queryset = queryset.exclude(id__in=exclude_ids)
            
            self.fields['rodzic'].queryset = queryset
    
    def _get_descendants(self, folder):
        """Get all descendants of a folder"""
        descendants = Folder.objects.filter(rodzic=folder)
        all_descendants = descendants
        
        for descendant in descendants:
            all_descendants = all_descendants | self._get_descendants(descendant)
        
        return all_descendants
    
    def clean_nazwa(self):
        """Validate folder name"""
        nazwa = self.cleaned_data.get('nazwa', '').strip()
        
        if not nazwa:
            raise ValidationError("Nazwa folderu jest wymagana.")
        
        if len(nazwa) > 255:
            raise ValidationError("Nazwa folderu nie może być dłuższa niż 255 znaków.")
        
        # Check for dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        for char in dangerous_chars:
            if char in nazwa:
                raise ValidationError(f"Nazwa nie może zawierać znaku: {char}")
        
        return nazwa


class FolderDeleteForm(forms.Form):
    """Form for folder deletion with options for handling contents"""
    
    DELETE_CHOICES = [
        ('move_to_parent', 'Przenieś zawartość do folderu nadrzędnego'),
        ('move_to_folder', 'Przenieś zawartość do innego folderu'),
        ('delete_all', 'Usuń folder wraz z całą zawartością'),
    ]
    
    action = forms.ChoiceField(
        label='Co zrobić z zawartością folderu?',
        choices=DELETE_CHOICES,
        initial='move_to_parent',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    target_folder = forms.ModelChoiceField(
        label='Folder docelowy',
        queryset=Folder.objects.none(),  # Will be set in __init__
        required=False,
        empty_label="Wybierz folder",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    confirm_deletion = forms.BooleanField(
        label='Potwierdzam, że chcę usunąć ten folder',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        folder_to_delete = kwargs.pop('folder', None)
        super().__init__(*args, **kwargs)
        
        if user and folder_to_delete:
            # Set available target folders (exclude the folder being deleted and its descendants)
            if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
                queryset = Folder.objects.all()
            else:
                # Get all folders the user can browse
                browseable_folders = get_objects_for_user(user, 'documents.browse_folder', klass=Folder)
                queryset = browseable_folders
            
            # Exclude the folder being deleted and its descendants
            descendants = self._get_descendants(folder_to_delete)
            exclude_ids = [folder_to_delete.id] + list(descendants.values_list('id', flat=True))
            queryset = queryset.exclude(id__in=exclude_ids)
            
            self.fields['target_folder'].queryset = queryset
            
            # If folder has no parent, disable "move to parent" option
            if not folder_to_delete.rodzic:
                self.fields['action'].choices = [
                    choice for choice in self.DELETE_CHOICES 
                    if choice[0] != 'move_to_parent'
                ]
                self.fields['action'].initial = 'move_to_folder'
    
    def _get_descendants(self, folder):
        """Get all descendants of a folder"""
        descendants = Folder.objects.filter(rodzic=folder)
        all_descendants = descendants
        
        for descendant in descendants:
            all_descendants = all_descendants | self._get_descendants(descendant)
        
        return all_descendants
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        target_folder = cleaned_data.get('target_folder')
        
        if action == 'move_to_folder' and not target_folder:
            raise ValidationError("Musisz wybrać folder docelowy dla tej opcji.")
        
        return cleaned_data