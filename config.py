
# =================================================================
#   A.R.I.S.E. - Application Configuration
#   Loads settings from environment variables (.env file)
# =================================================================

import os
import secrets
from dotenv import load_dotenv

# Load .env file from the same directory as this file
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))


def _get_or_generate_secret_key():
    """
    Gets SECRET_KEY from environment, or auto-generates one on first run.
    If auto-generated, writes it back to the .env file so it persists.
    """
    key = os.environ.get('SECRET_KEY', '')
    
    if not key or key == 'auto_generate_on_first_run' or key == 'CHANGE_ME_TO_A_RANDOM_64_CHAR_HEX_STRING':
        # Generate a cryptographically secure random key
        key = secrets.token_hex(32)  # 64-char hex string
        
        # Write it back to .env file so it persists across restarts
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        try:
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    content = f.read()
                
                # Replace the placeholder with the generated key
                for placeholder in ['auto_generate_on_first_run', 'CHANGE_ME_TO_A_RANDOM_64_CHAR_HEX_STRING']:
                    content = content.replace(f'SECRET_KEY={placeholder}', f'SECRET_KEY={key}')
                
                with open(env_path, 'w') as f:
                    f.write(content)
                    
                print(f"[CONFIG] Auto-generated SECRET_KEY and saved to .env")
            else:
                # Create .env with just the key
                with open(env_path, 'w') as f:
                    f.write(f'SECRET_KEY={key}\n')
                print(f"[CONFIG] Created .env with auto-generated SECRET_KEY")
        except Exception as e:
            print(f"[CONFIG] Warning: Could not save SECRET_KEY to .env: {e}")
            print(f"[CONFIG] The key will be regenerated on next restart!")
    
    return key


# =================================================================
#   Configuration Classes
# =================================================================

class BaseConfig:
    """Base configuration shared by all environments."""
    
    # Security
    SECRET_KEY = _get_or_generate_secret_key()
    
    # Database
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'attendance.db')
    
    # Admin
    ADMIN_DEFAULT_PASSWORD = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'admin')
    
    # Server
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    
    # ===== ATTENDANCE REQUIREMENTS =====
    MINIMUM_ATTENDANCE_PERCENTAGE = 75   # Institute minimum requirement (%)
    ATTENDANCE_WARNING_THRESHOLD = 60    # Critical warning threshold (%)
    ENABLE_ATTENDANCE_ANALYTICS = True   # Enable attendance analytics feature
    
    # Analytics time ranges for calculations
    ANALYTICS_LAST_DAYS = 7              # Last N days for trend analysis
    ANALYTICS_TREND_DAYS = 30            # Last N days for overall trend
    
    # Rate Limiting
    RATE_LIMIT_LOGIN = "5 per minute"    # Max login attempts per IP
    RATE_LIMIT_API = "100 per minute"    # Max API calls per IP
    
    # --- Cloud Sync Settings ---
    # Set IS_CLOUD_SERVER=true on the cloud instance
    IS_CLOUD_SERVER = os.environ.get('IS_CLOUD_SERVER', 'false').lower() == 'true'
    # API key for authenticating sync requests between local and cloud
    SYNC_API_KEY = os.environ.get('SYNC_API_KEY', 'arise-sync-default-key-change-me')
    # URL of the cloud server (used by local server to push data)
    CLOUD_SERVER_URL = os.environ.get('CLOUD_SERVER_URL', '')
    # Auto-sync interval in seconds (0 = manual only)
    SYNC_INTERVAL_SECONDS = int(os.environ.get('SYNC_INTERVAL_SECONDS', '300'))


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(BaseConfig):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False


class TestingConfig(BaseConfig):
    """Testing environment configuration."""
    DEBUG = True
    TESTING = True
    DATABASE_PATH = ':memory:'  # Use in-memory database for tests


# --- Select configuration based on FLASK_ENV ---
_env = os.environ.get('FLASK_ENV', 'development').lower()
_config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

Config = _config_map.get(_env, DevelopmentConfig)

# --- Export legacy constants for backward compatibility ---
MINIMUM_ATTENDANCE_PERCENTAGE = Config.MINIMUM_ATTENDANCE_PERCENTAGE
ATTENDANCE_WARNING_THRESHOLD = Config.ATTENDANCE_WARNING_THRESHOLD
ENABLE_ATTENDANCE_ANALYTICS = Config.ENABLE_ATTENDANCE_ANALYTICS
ANALYTICS_LAST_DAYS = Config.ANALYTICS_LAST_DAYS
ANALYTICS_TREND_DAYS = Config.ANALYTICS_TREND_DAYS