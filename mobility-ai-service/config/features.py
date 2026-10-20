"""Server-owned product switches. Disabled unless explicitly enabled."""
import os


def analysis_enabled():
    return os.getenv('FORM_ANALYSIS_ENABLED', 'false').strip().lower() == 'true'


def public_features():
    return {'form_analysis': analysis_enabled()}
