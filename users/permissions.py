"""
Guardian permissions helpers for Document Manager
"""
from guardian.shortcuts import assign_perm, remove_perm, get_perms
# from guardian.core import ObjectPermissionChecker # Not directly used in these functions
from django.contrib.auth.models import User # Not directly needed if using request.user
# from .models import UserProfile, Role # UserProfile is accessed via user.profile

# It's good practice to import models from the app they belong to
# when using them in functions that might be called from various places.
# from documents.models import Document, Folder # Import these where needed or pass objects


# --- Document Permissions ---

def user_can_view_document(user, document):
    """Check if user can view specific document."""
    if not user.is_authenticated:
        return False

    # Administratorzy i Edytorzy widzą wszystko
    if user.is_superuser or (hasattr(user, 'profile') and (user.profile.is_admin or user.profile.is_editor)):
        return True

    # Właściciel zawsze może przeglądać swoje dokumenty
    if document.wlasciciel == user:
        return True

    # Dla wszystkich innych - tylko jawnie nadane uprawnienia przez administratora
    return user.has_perm('browse_document', document)


def user_can_create_document(user, folder=None):
    """Check if user can create new documents."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or (hasattr(user, 'profile') and (user.profile.is_admin or user.profile.is_editor)):
        return True
    return False


def user_can_edit_document(user, document):
    """Check if user can edit specific document metadata or upload new versions."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
        return True

    if hasattr(user, 'profile') and user.profile.is_editor:
        return True

    return False


def user_can_delete_document(user, document):
    """Check if user can delete specific document."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
        return True

    if hasattr(user, 'profile') and user.profile.is_editor:
        return True

    return False


def user_can_comment_on_document(user, document):
    """Check if user can comment on a document."""
    if not user.is_authenticated:
        return False

    # Najpierw sprawdź czy może przeglądać dokument
    if not user_can_view_document(user, document):
        return False
    
    # Sprawdź czy profil jest aktywny
    if hasattr(user, 'profile') and not user.profile.aktywny:
        return False
    
    # Administratorzy i Edytorzy mogą komentować wszystko co widzą
    if user.is_superuser or (hasattr(user, 'profile') and (user.profile.is_admin or user.profile.is_editor)):
        return True
    
    # Właściciel może komentować swoje dokumenty
    if document.wlasciciel == user:
        return True
        
    # Dla innych - sprawdź jawnie nadane uprawnienie do komentowania
    return user.has_perm('comment_document', document)


def user_can_share_document(user, document):
    """Check if user can share specific document."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
        return True

    if document.wlasciciel == user and (hasattr(user, 'profile') and (user.profile.is_admin or user.profile.is_editor)):
        return True
    
    if hasattr(user, 'profile') and user.profile.is_editor and user.has_perm('share_document', document):
        return True

    return False


def share_document_with_user(document, from_user, to_user_obj, permission_level='browse_document'):
    """Share document with another user.
    to_user_obj is an instance of User.
    """
    # Define all possible document permissions
    all_doc_permissions = [
        'browse_document', 'change_document', 'delete_document', 
        'share_document', 'download_document', 'comment_document'
    ]
    
    # Remove existing document-specific permissions for this document from the target user
    for perm in all_doc_permissions:
        if to_user_obj.has_perm(perm, document):
            remove_perm(perm, to_user_obj, document)
    
    # Assign new permission
    assign_perm(permission_level, to_user_obj, document)
    
    # Log the sharing activity
    from documents.models import ActivityLog # Local import to avoid circularity
    ActivityLog.objects.create(
        uzytkownik=from_user,
        typ_aktywnosci='udostepnianie',
        dokument=document,
        szczegoly=f"Udostępniono '{document.nazwa}' dla {to_user_obj.get_full_name()} z uprawnieniem {permission_level}",
        # adres_ip='127.0.0.1'  # Get real IP in views
    )


def remove_all_permissions_for_document_from_user(document, user_obj):
    """Remove all document permissions for a specific document from a user."""
    all_doc_permissions = [
        'browse_document', 'change_document', 'delete_document', 
        'share_document', 'download_document', 'comment_document'
    ]
    for perm in all_doc_permissions:
        if user_obj.has_perm(perm, document):
            remove_perm(perm, user_obj, document)


def get_user_document_permissions(user, document):
    """Get all permissions user has for specific document."""
    return get_perms(user, document)


# --- Folder Permissions ---

def user_can_view_folder(user, folder):
    """Check if user can view specific folder."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
        return True

    if folder.wlasciciel == user: # Owner can always view
        return True

    return user.has_perm('browse_folder', folder)


def user_can_create_folder(user, folder=None):
    """Check if user can create new folders."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or (hasattr(user, 'profile') and (user.profile.is_admin or user.profile.is_editor)):
        return True
    # Allow users with the general 'add_folder' permission to create folders
    return user.has_perm('documents.add_folder')


def user_can_edit_folder(user, folder):
    """Check if user can edit specific folder's metadata."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
        return True

    if folder.wlasciciel == user:
        return True

    if hasattr(user, 'profile') and user.profile.is_editor:
        return True
        
    return False

def user_can_delete_folder(user, folder):
    """Check if user can delete specific folder."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_admin):
        return True

    if folder.wlasciciel == user:
        return True

    if hasattr(user, 'profile') and user.profile.is_editor:
        return True
        
    return False

def admin_grant_document_access(admin_user, target_user, document, permissions=['browse_document']):
    """
    Funkcja dla administratora do nadawania uprawnień do dokumentu.
    
    Args:
        admin_user: Użytkownik administrator nadający uprawnienia
        target_user: Użytkownik otrzymujący uprawnienia  
        document: Dokument do którego nadawane są uprawnienia
        permissions: Lista uprawnień do nadania (domyślnie tylko przeglądanie)
    
    Available permissions:
        - 'browse_document': Przeglądanie dokumentu
        - 'download_document': Pobieranie dokumentu  
        - 'comment_document': Komentowanie dokumentu
        - 'change_document': Edycja dokumentu
        - 'delete_document': Usuwanie dokumentu
        - 'share_document': Udostępnianie dokumentu
    """
    # Sprawdź czy użytkownik ma uprawnienia administratora
    if not (admin_user.is_superuser or (hasattr(admin_user, 'profile') and admin_user.profile.is_admin)):
        raise PermissionError("Tylko administrator może nadawać uprawnienia do dokumentów.")
    
    # Nadaj uprawnienia
    from guardian.shortcuts import assign_perm
    from documents.models import ActivityLog
    
    for permission in permissions:
        assign_perm(permission, target_user, document)
    
    # Zaloguj aktywność
    ActivityLog.objects.create(
        uzytkownik=admin_user,
        typ_aktywnosci='udostepnianie',
        dokument=document,
        szczegoly=f"Nadano uprawnienia {', '.join(permissions)} użytkownikowi {target_user.get_full_name()} do dokumentu {document.nazwa}",
        adres_ip='127.0.0.1'  # W rzeczywistej aplikacji pobierz prawdziwy IP
    )
    
    return True


def admin_revoke_document_access(admin_user, target_user, document, permissions=None):
    """
    Funkcja dla administratora do odbierania uprawnień do dokumentu.
    
    Args:
        admin_user: Użytkownik administrator odbierający uprawnienia
        target_user: Użytkownik tracący uprawnienia
        document: Dokument z którego odbierane są uprawnienia  
        permissions: Lista uprawnień do odebrania (None = wszystkie)
    """
    # Sprawdź czy użytkownik ma uprawnienia administratora
    if not (admin_user.is_superuser or (hasattr(admin_user, 'profile') and admin_user.profile.is_admin)):
        raise PermissionError("Tylko administrator może odbierać uprawnienia do dokumentów.")
    
    from guardian.shortcuts import remove_perm
    from documents.models import ActivityLog
    
    # Jeśli nie podano listy uprawnień, usuń wszystkie
    if permissions is None:
        permissions = [
            'browse_document', 'download_document', 'comment_document',
            'change_document', 'delete_document', 'share_document'
        ]
    
    # Usuń uprawnienia
    for permission in permissions:
        if target_user.has_perm(permission, document):
            remove_perm(permission, target_user, document)
    
    # Zaloguj aktywność
    ActivityLog.objects.create(
        uzytkownik=admin_user,
        typ_aktywnosci='zmiana_uprawnien',
        dokument=document,
        szczegoly=f"Odebrano uprawnienia {', '.join(permissions)} użytkownikowi {target_user.get_full_name()} do dokumentu {document.nazwa}",
        adres_ip='127.0.0.1'
    )
    
    return True
