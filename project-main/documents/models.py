from django.db import models
from django.contrib.auth.models import User # Direct import is fine if User is not customized extensively
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.conf import settings
import os
import uuid
# Ensure users.models is loaded or use string references if circular dependency arises
# For now, direct import is assumed to work based on your project structure.
from users.models import Role, UserProfile


def document_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"

    from datetime import datetime
    now = datetime.now()

    return f"documents/{instance.wlasciciel.id}/{now.year}/{now.month:02d}/{filename}"

class Tag(models.Model):
    """Tags for document categorization"""
    nazwa = models.CharField(max_length=50, unique=True)
    kolor = models.CharField(max_length=20, default='#007bff')

    def __str__(self):
        return self.nazwa

    class Meta:
        db_table = 'tag'
        verbose_name = "Tag"
        verbose_name_plural = "Tagi"
        ordering = ['nazwa']


class Folder(models.Model):
    """Folder structure for documents"""
    nazwa = models.CharField(max_length=255)
    opis = models.TextField(blank=True)
    data_utworzenia = models.DateTimeField(auto_now_add=True)
    rodzic = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='podkatalogi')
    wlasciciel = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders_owned') # Changed related_name for clarity
    tagi = models.ManyToManyField(Tag, blank=True, verbose_name='Tagi', related_name='folders')

    def __str__(self):
        return self.nazwa

    def get_full_path(self):
        """Get full folder path"""
        path_parts = [self.nazwa]
        parent = self.rodzic
        while parent:
            path_parts.insert(0, parent.nazwa)
            parent = parent.rodzic
        return ' / '.join(path_parts)

    class Meta:
        db_table = 'folder'
        verbose_name = "Folder"
        verbose_name_plural = "Foldery"
        unique_together = ['nazwa', 'rodzic', 'wlasciciel']
        ordering = ['nazwa']
        # Django automatically creates add_folder, change_folder, delete_folder, view_folder
        # We only define permissions that are *additional* to these.
        permissions = (
            ("browse_folder", "Can browse folder and its contents"),
            # ("change_folder", "Can change folder metadata"), # REMOVED - uses built-in documents.change_folder
            # ("delete_folder", "Can delete folder"), # REMOVED - uses built-in documents.delete_folder
            ("add_document_to_folder", "Can add documents to folder"),
            ("add_subfolder_to_folder", "Can add subfolders to folder"),
        )


class Document(models.Model):
    """Main document model"""
    ALLOWED_EXTENSIONS = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'txt', 'png', 'jpg', 'jpeg']

    STATUS_CHOICES = [
        ('draft', 'Szkic'),
        ('published', 'Opublikowany'),
        ('archived', 'Zarchiwizowany'),
    ]

    # Basic information
    nazwa = models.CharField(max_length=255)
    # typ_pliku should ideally be determined on save or be a choice field if limited
    typ_pliku = models.CharField(max_length=100, blank=True) # Made blank=True as it's auto-set
    # rozmiar_pliku should also be auto-set or allow null/blank if plik can be null
    rozmiar_pliku = models.PositiveIntegerField(null=True, blank=True) # Allowed null/blank

    plik = models.FileField(
        upload_to=document_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)],
        help_text="Obsługiwane formaty: PDF, DOCX, DOC, XLSX, XLS, TXT, PNG, JPG, JPEG",
        blank=True,
        null=True
    )

    data_utworzenia = models.DateTimeField(auto_now_add=True)
    ostatnia_modyfikacja = models.DateTimeField(auto_now=True)
    wlasciciel = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents_owned') # Changed related_name
    # Consider on_delete=models.SET_NULL for folder if you want documents to remain if folder is deleted
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    usunieto = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    tagi = models.ManyToManyField(Tag, blank=True, related_name='documents') # Changed related_name

    opis = models.TextField(blank=True, help_text="Opcjonalny opis dokumentu")
    hash_pliku = models.CharField(max_length=64, blank=True, help_text="SHA-256 hash for file integrity")

    def __str__(self):
        return self.nazwa

    def clean(self):
        super().clean()
        if self.plik and hasattr(self.plik, 'size') and self.plik.size > 50 * 1024 * 1024:
            raise ValidationError({"plik": "Plik nie może być większy niż 50MB."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.plik and hasattr(self.plik, 'path'):
            try:
                if os.path.isfile(self.plik.path):
                    os.remove(self.plik.path)
            except (ValueError, OSError, AttributeError): # Added AttributeError
                pass
        super().delete(*args, **kwargs)

    def get_file_size_display(self):
        """Return human readable file size"""
        if not self.rozmiar_pliku:
            return "0 B"
        
        size = self.rozmiar_pliku
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def get_file_extension(self):
        # Use typ_pliku if available, otherwise derive from nazwa
        if self.typ_pliku:
            return f".{self.typ_pliku}"
        if not self.nazwa:
            return ""
        return os.path.splitext(self.nazwa)[1].lower()

    def get_file_icon(self):
        ext_only = self.typ_pliku.lower() if self.typ_pliku else self.get_file_extension().lstrip('.')
        icon_map = {
            'pdf': 'bi-file-earmark-pdf-fill text-danger',
            'doc': 'bi-file-earmark-word-fill text-primary',
            'docx': 'bi-file-earmark-word-fill text-primary',
            'xls': 'bi-file-earmark-excel-fill text-success',
            'xlsx': 'bi-file-earmark-excel-fill text-success',
            'txt': 'bi-file-earmark-text-fill text-secondary',
            'png': 'bi-file-earmark-image-fill text-info',
            'jpg': 'bi-file-earmark-image-fill text-info',
            'jpeg': 'bi-file-earmark-image-fill text-info',
        }
        return icon_map.get(ext_only, 'bi-file-earmark-fill text-muted')

    def is_image(self):
        return self.typ_pliku in ['png', 'jpg', 'jpeg']

    def can_preview(self):
        return self.plik and self.typ_pliku in ['pdf', 'txt', 'png', 'jpg', 'jpeg']

    @property
    def download_url(self): # This should be handled by reverse in templates
        if self.plik:
            from django.urls import reverse
            try:
                return reverse('documents:document_download', args=[self.id])
            except Exception:
                return None # Or '#'
        return None

    class Meta:
        db_table = 'dokument'
        verbose_name = "Dokument"
        verbose_name_plural = "Dokumenty"
        ordering = ['-ostatnia_modyfikacja']
        # Django automatically creates add_document, change_document, delete_document, view_document
        # We only define permissions that are *additional* to these.
        permissions = (
            ("browse_document", "Can browse document"),
            # ("change_document", "Can change document metadata and versions"), # REMOVED
            # ("delete_document", "Can delete document"), # REMOVED
            ("share_document", "Can share document with others"),
            ("download_document", "Can download document file"),
            ("comment_document", "Can comment on document"),
        )

class DocumentVersion(models.Model):
    """Document version control"""
    dokument = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='wersje')
    numer_wersji = models.PositiveIntegerField()
    data_utworzenia = models.DateTimeField(auto_now_add=True)
    utworzony_przez = models.ForeignKey(User, on_delete=models.CASCADE)
    plik = models.FileField(upload_to='document_versions/%Y/%m/%d/', blank=True, null=True)
    komentarz = models.TextField(blank=True)
    rozmiar_pliku = models.PositiveIntegerField(default=0, null=True, blank=True)
    hash_pliku = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return f"{self.dokument.nazwa} v{self.numer_wersji}"

    def get_file_size_display(self):
        """Return human readable file size"""
        if not self.rozmiar_pliku:
            return "0 B"
        
        size = self.rozmiar_pliku
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def save(self, *args, **kwargs):
        if self.plik and hasattr(self.plik, 'size') and not self.rozmiar_pliku:
            self.rozmiar_pliku = self.plik.size

            if self.plik.file:
                import hashlib
                self.plik.seek(0)
                file_hash = hashlib.sha256()
                for chunk in iter(lambda: self.plik.read(4096), b""):
                    file_hash.update(chunk)
                self.hash_pliku = file_hash.hexdigest()
                self.plik.seek(0)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'wersja_dokumentu'
        unique_together = ['dokument', 'numer_wersji']
        ordering = ['-numer_wersji']

class DocumentMetadata(models.Model):
    """Custom metadata for documents"""
    dokument = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='metadane')
    klucz = models.CharField(max_length=100)
    wartosc = models.TextField()

    def __str__(self):
        return f"{self.klucz}: {self.wartosc}"

    class Meta:
        db_table = 'metadane'
        unique_together = ['dokument', 'klucz']
        verbose_name = "Metadana dokumentu"
        verbose_name_plural = "Metadane dokumentów"


class Comment(models.Model):
    dokument = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='komentarze',
        verbose_name='Dokument'
    )
    wersja_dokumentu = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name='komentarze',
        null=True,
        blank=True,
        verbose_name='Wersja dokumentu'
    )
    uzytkownik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Użytkownik' # No related_name needed unless accessing comments from User
    )
    tresc = models.TextField(verbose_name='Treść komentarza')
    data_utworzenia = models.DateTimeField(auto_now_add=True, verbose_name='Data utworzenia')
    rodzic = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='odpowiedzi',
        verbose_name='Komentarz nadrzędny'
    )
    aktywny = models.BooleanField(default=True, verbose_name='Aktywny')

    def clean(self):
        if self.wersja_dokumentu and self.wersja_dokumentu.dokument_id != self.dokument_id:
            raise ValidationError("Komentarz do wersji musi być przypisany do tego samego dokumentu co wersja.")

    class Meta:
        ordering = ['data_utworzenia']
        verbose_name = "Komentarz"
        verbose_name_plural = "Komentarze"

    def __str__(self):
        username = self.uzytkownik.get_username() if hasattr(self.uzytkownik, 'get_username') else str(self.uzytkownik)
        if self.wersja_dokumentu:
            return f'Komentarz {username} do {self.wersja_dokumentu}'
        doc_name = self.dokument.nazwa if self.dokument else "N/A"
        return f'Komentarz {username} do {doc_name}'

    def get_children(self):
        return Comment.objects.filter(rodzic=self, aktywny=True)


class ActivityLog(models.Model):
    """Activity logging"""
    ACTION_CHOICES = [
        ('logowanie', 'Logowanie'),
        ('tworzenie', 'Tworzenie'),
        ('edycja', 'Edycja'),
        ('usuniecie', 'Usunięcie'),
        ('pobieranie', 'Pobieranie'),
        ('udostepnianie', 'Udostępnianie'),
        ('komentowanie', 'Komentowanie'), # Duplicated 'komentarz', using this one
        ('zmiana_uprawnien', 'Zmiana uprawnień'),
        ('zmiana_hasla', 'Zmiana hasła'),
        # ('komentarz', 'Skomentowanie'), # This was a duplicate
    ]

    uzytkownik = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logi_aktywnosci')
    typ_aktywnosci = models.CharField(max_length=50, choices=ACTION_CHOICES)
    dokument = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True) # SET_NULL for document
    folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True)     # SET_NULL for folder
    szczegoly = models.TextField(blank=True)
    znacznik_czasu = models.DateTimeField(auto_now_add=True)
    adres_ip = models.GenericIPAddressField(null=True, blank=True) # Allow null for IP

    def __str__(self):
        return f"{self.uzytkownik.username} - {self.typ_aktywnosci} - {self.znacznik_czasu.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        db_table = 'log_aktywnosci'
        verbose_name = "Log aktywności"
        verbose_name_plural = "Logi aktywności"
        ordering = ['-znacznik_czasu']


class DocumentShare(models.Model):
    """Track document sharing with specific permissions"""
    SHARE_PERMISSION_CHOICES = [
        ('documents.browse_document', 'Tylko przeglądanie'), # Use full perm string
        ('documents.download_document', 'Przeglądanie i pobieranie'),
        ('documents.comment_document', 'Przeglądanie i komentowanie'),
        ('documents.change_document', 'Pełne uprawnienia do edycji'), # 'manage' often implies more
    ]
    dokument = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='document_shares') # Changed related_name
    udostepnione_przez = models.ForeignKey(User, on_delete=models.CASCADE, related_name='made_shares')
    udostepnione_dla = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_shares')
    # Store the actual permission codename (e.g., 'documents.browse_document')
    uprawnienie = models.CharField(max_length=100, choices=SHARE_PERMISSION_CHOICES)
    data_udostepnienia = models.DateTimeField(auto_now_add=True)
    data_wygasniecia = models.DateTimeField(null=True, blank=True)
    aktywne = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.dokument.nazwa} shared by {self.udostepnione_przez.username} to {self.udostepnione_dla.username} with {self.get_uprawnienie_display()}"

    class Meta:
        db_table = 'document_share'
        unique_together = ['dokument', 'udostepnione_dla'] # A user should only have one type of share per document
        verbose_name = "Udostępnienie dokumentu"
        verbose_name_plural = "Udostępnienia dokumentów"


class SystemSettings(models.Model):
    """Ustawienia systemowe"""
    # Renamed 'key' to 'klucz' and 'value' to 'wartosc' as per previous files
    klucz = models.CharField(max_length=100, unique=True, verbose_name='Klucz')
    wartosc = models.TextField(verbose_name='Wartość')
    opis = models.TextField(blank=True, verbose_name='Opis') # Renamed 'description'
    kategoria = models.CharField(max_length=50, default='general', verbose_name='Kategoria') # Renamed 'category'
    data_utworzenia = models.DateTimeField(auto_now_add=True) # Renamed 'created_at'
    data_modyfikacji = models.DateTimeField(auto_now=True) # Renamed 'updated_at'

    def __str__(self):
        return f"{self.klucz}: {self.wartosc}"

    @classmethod
    def get_setting(cls, klucz, default=None):
        try:
            setting = cls.objects.get(klucz=klucz)
            return setting.wartosc
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_setting(cls, klucz, wartosc, opis='', kategoria='general'):
        setting, created = cls.objects.get_or_create(
            klucz=klucz,
            defaults={
                'wartosc': wartosc,
                'opis': opis,
                'kategoria': kategoria
            }
        )
        if not created:
            setting.wartosc = wartosc
            setting.opis = opis
            setting.kategoria = kategoria
            setting.save()
        return setting

    class Meta:
        db_table = 'system_settings'
        verbose_name = 'Ustawienie systemowe'
        verbose_name_plural = 'Ustawienia systemowe'
        ordering = ['kategoria', 'klucz']