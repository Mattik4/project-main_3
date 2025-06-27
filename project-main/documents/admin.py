from django.contrib import admin
from django.contrib.auth.models import User
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import assign_perm, remove_perm, get_perms
from .models import (
    Document, DocumentVersion, Folder, Tag, 
    DocumentMetadata, Comment, ActivityLog, DocumentShare, SystemSettings
)


@admin.register(Document)
class DocumentAdmin(GuardedModelAdmin):
    """Document administration with Guardian integration"""
    list_display = ['nazwa', 'typ_pliku', 'get_file_size', 'wlasciciel', 'folder', 'data_utworzenia', 'status', 'usunieto']
    list_filter = ['typ_pliku', 'status', 'usunieto', 'data_utworzenia', 'folder']
    search_fields = ['nazwa', 'wlasciciel__username', 'wlasciciel__first_name', 'wlasciciel__last_name']
    readonly_fields = ['data_utworzenia', 'ostatnia_modyfikacja', 'rozmiar_pliku']
    filter_horizontal = ['tagi']  # This works now since we removed 'through' parameter
    
    fieldsets = (
        ('Podstawowe informacje', {
            'fields': ('nazwa', 'typ_pliku', 'status')
        }),
        ('Lokalizacja', {
            'fields': ('wlasciciel', 'folder')
        }),
        ('Kategoryzacja', {
            'fields': ('tagi',)  # This now works since tagi is a simple ManyToManyField
        }),
        ('Metadane', {
            'fields': ('rozmiar_pliku', 'data_utworzenia', 'ostatnia_modyfikacja'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('usunieto',)
        })
    )
    
    def get_file_size(self, obj):
        return obj.get_file_size_display()
    get_file_size.short_description = 'Rozmiar'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # For non-superusers, show only documents they can view
        return get_objects_for_user(request.user, 'documents.browse_document', qs)


@admin.register(Folder)
class FolderAdmin(GuardedModelAdmin):
    """Folder administration with Guardian integration"""
    list_display = ['nazwa', 'wlasciciel', 'rodzic', 'get_full_path', 'data_utworzenia', 'get_documents_count']
    list_filter = ['data_utworzenia', 'wlasciciel']
    search_fields = ['nazwa', 'wlasciciel__username', 'wlasciciel__first_name', 'wlasciciel__last_name']
    readonly_fields = ['data_utworzenia']
    
    fieldsets = (
        ('Podstawowe informacje', {
            'fields': ('nazwa', 'opis')
        }),
        ('Struktura', {
            'fields': ('wlasciciel', 'rodzic')
        }),
        ('Metadane', {
            'fields': ('data_utworzenia',),
            'classes': ('collapse',)
        })
    )
    
    def get_documents_count(self, obj):
        return obj.documents.filter(usunieto=False).count()
    get_documents_count.short_description = 'Liczba dokumentów'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related('wlasciciel', 'rodzic')
        # For non-superusers, show only folders they can view
        return get_objects_for_user(request.user, 'documents.browse_folder', qs).select_related('wlasciciel', 'rodzic')


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    """Document version administration"""
    list_display = ['dokument', 'numer_wersji', 'utworzony_przez', 'data_utworzenia', 'get_comment_preview']
    list_filter = ['data_utworzenia']
    search_fields = ['dokument__nazwa', 'utworzony_przez__username', 'komentarz']
    readonly_fields = ['data_utworzenia']
    
    def get_comment_preview(self, obj):
        return obj.komentarz[:50] + "..." if len(obj.komentarz) > 50 else obj.komentarz
    get_comment_preview.short_description = 'Komentarz'


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Tag administration"""
    list_display = ['nazwa', 'kolor', 'get_documents_count']
    search_fields = ['nazwa']
    
    def get_documents_count(self, obj):
        return obj.document_set.filter(usunieto=False).count()
    get_documents_count.short_description = 'Liczba dokumentów'


@admin.register(DocumentMetadata)
class DocumentMetadataAdmin(admin.ModelAdmin):
    """Document metadata administration"""
    list_display = ['dokument', 'klucz', 'get_value_preview']
    list_filter = ['klucz']
    search_fields = ['dokument__nazwa', 'klucz', 'wartosc']
    
    def get_value_preview(self, obj):
        return obj.wartosc[:100] + "..." if len(obj.wartosc) > 100 else obj.wartosc
    get_value_preview.short_description = 'Wartość'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Comment administration"""
    list_display = ['dokument', 'uzytkownik', 'get_content_preview', 'data_utworzenia', 'rodzic']
    list_filter = ['data_utworzenia']
    search_fields = ['dokument__nazwa', 'uzytkownik__username', 'tresc']
    readonly_fields = ['data_utworzenia']
    
    def get_content_preview(self, obj):
        return obj.tresc[:50] + "..." if len(obj.tresc) > 50 else obj.tresc
    get_content_preview.short_description = 'Treść'


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Activity log administration"""
    list_display = ['uzytkownik', 'typ_aktywnosci', 'dokument', 'folder', 'znacznik_czasu', 'adres_ip']
    list_filter = ['typ_aktywnosci', 'znacznik_czasu']
    search_fields = ['uzytkownik__username', 'szczegoly', 'adres_ip']
    readonly_fields = ['znacznik_czasu']
    date_hierarchy = 'znacznik_czasu'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uzytkownik', 'dokument', 'folder')
    
    def has_add_permission(self, request):
        """Disable manual log creation"""
        return False


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    """Document sharing administration"""
    list_display = [
        'dokument', 'udostepnione_przez', 'udostepnione_dla', 
        'uprawnienie', 'data_udostepnienia', 'data_wygasniecia', 'aktywne'
    ]
    list_filter = ['uprawnienie', 'aktywne', 'data_udostepnienia']
    search_fields = [
        'dokument__nazwa', 'udostepnione_przez__username', 
        'udostepnione_dla__username'
    ]
    readonly_fields = ['data_udostepnienia']
    
    fieldsets = (
        ('Dokument', {
            'fields': ('dokument', 'uprawnienie')
        }),
        ('Użytkownicy', {
            'fields': ('udostepnione_przez', 'udostepnione_dla')
        }),
        ('Czas', {
            'fields': ('data_udostepnienia', 'data_wygasniecia')
        }),
        ('Status', {
            'fields': ('aktywne',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'dokument', 'udostepnione_przez', 'udostepnione_dla'
        )


# Don't register DocumentTag - it's managed through Document admin
# admin.site.register(DocumentTag)

# Custom admin actions
def make_documents_published(modeladmin, request, queryset):
    """Bulk action to publish documents"""
    queryset.update(status='published')
    modeladmin.message_user(request, f"Opublikowano {queryset.count()} dokumentów.")

make_documents_published.short_description = "Opublikuj wybrane dokumenty"

def make_documents_archived(modeladmin, request, queryset):
    """Bulk action to archive documents"""
    queryset.update(status='archived')
    modeladmin.message_user(request, f"Zarchiwizowano {queryset.count()} dokumentów.")

make_documents_archived.short_description = "Zarchiwizuj wybrane dokumenty"

# Add actions to DocumentAdmin
DocumentAdmin.actions = [make_documents_published, make_documents_archived]


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'klucz',         # Corrected from 'key'
        'wartosc',       # Corrected from 'value'
        'kategoria',     # Corrected from 'category'
        'opis',          # Corrected from 'description'
        'data_modyfikacji' # Corrected from 'updated_at'
    )
    search_fields = ('klucz', 'wartosc', 'opis', 'kategoria') # Use correct field names
    list_filter = (
        'kategoria',     # Corrected from 'category'
        'data_utworzenia',# Corrected from 'created_at'
        'data_modyfikacji' # Corrected from 'updated_at'
    )
    list_editable = ('wartosc', 'kategoria', 'opis') # Corrected 'value' to 'wartosc'
    
    fieldsets = (
        ('Ustawienie', {
            'fields': ('klucz', 'wartosc', 'kategoria', 'opis')
        }),
        ('Informacje o czasie', {
            'fields': ('data_utworzenia', 'data_modyfikacji'),
            'classes': ('collapse',) # Make this section collapsible
        }),
    )
    readonly_fields = (
        'data_utworzenia', # Corrected from 'created_at'
        'data_modyfikacji'  # Corrected from 'updated_at'
    )

    # Optional: if you want to ensure 'klucz' is not editable after creation
    # def get_readonly_fields(self, request, obj=None):
    #     if obj: # When editing an object
    #         return self.readonly_fields + ('klucz',)
    #     return self.readonly_fields

def grant_view_permission(modeladmin, request, queryset):
    """Nadaj uprawnienia do przeglądania wybranym dokumentom"""
    if not queryset:
        modeladmin.message_user(request, "Nie wybrano żadnych dokumentów.", level='error')
        return
    
    # Tutaj możesz dodać formularz do wyboru użytkowników
    # Na razie jako przykład, nadajmy uprawnienia wszystkim edytorom
    from users.models import Role, UserProfile
    try:
        editor_role = Role.objects.get(nazwa='edytor')
        editor_profiles = UserProfile.objects.filter(rola=editor_role, aktywny=True)
        
        granted_count = 0
        for document in queryset:
            for profile in editor_profiles:
                assign_perm('browse_document', profile.user, document)
                assign_perm('comment_document', profile.user, document)
                granted_count += 1
        
        modeladmin.message_user(
            request, 
            f"Nadano uprawnienia przeglądania i komentowania {granted_count} użytkownikom dla {queryset.count()} dokumentów."
        )
    except Role.DoesNotExist:
        modeladmin.message_user(request, "Rola 'edytor' nie istnieje.", level='error')

grant_view_permission.short_description = "Nadaj uprawnienia przeglądania edytorom"

def grant_download_permission(modeladmin, request, queryset):
    """Nadaj uprawnienia do pobierania wybranym dokumentom"""
    from users.models import Role, UserProfile
    try:
        editor_role = Role.objects.get(nazwa='edytor')
        editor_profiles = UserProfile.objects.filter(rola=editor_role, aktywny=True)
        
        granted_count = 0
        for document in queryset:
            for profile in editor_profiles:
                assign_perm('browse_document', profile.user, document)
                assign_perm('comment_document', profile.user, document)
                assign_perm('download_document', profile.user, document)
                granted_count += 1
        
        modeladmin.message_user(
            request, 
            f"Nadano pełne uprawnienia {granted_count} użytkownikom dla {queryset.count()} dokumentów."
        )
    except Role.DoesNotExist:
        modeladmin.message_user(request, "Rola 'edytor' nie istnieje.", level='error')

grant_download_permission.short_description = "Nadaj pełne uprawnienia edytorom"

# Dodaj te akcje do DocumentAdmin:
DocumentAdmin.actions = [
    make_documents_published, 
    make_documents_archived, 
    grant_view_permission,
    grant_download_permission
]    