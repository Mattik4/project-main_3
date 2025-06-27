from django import template
from documents.models import SystemSettings

register = template.Library()


@register.simple_tag
def get_setting(key, default=None):
    """Template tag do pobierania ustawień systemowych"""
    return SystemSettings.get_setting(key, default)