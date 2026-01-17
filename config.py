# =================================================================
#   A.R.I.S.E. Email Configuration - HACKATHON VERSION
#   Simple, working configuration for Gmail SMTP
# =================================================================

# ===== GMAIL SMTP SETTINGS =====
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "rajuhuptaooooo@gmail.com"

# ⚠️ IMPORTANT: Replace with your Gmail App Password
# Get it from: https://myaccount.google.com/apppasswords
SENDER_PASSWORD = "sewp zujq dhys nizj"

SENDER_NAME = "A.R.I.S.E. Attendance System"

# ===== EMAIL ALERT SETTINGS =====
# Set to True/False to enable/disable different alert types
ENABLE_INSTANT_ALERTS = True        # Send email immediately when student marks attendance
ENABLE_ABSENT_ALERTS = True         # Send email when student is absent after session ends
ENABLE_DAILY_SUMMARY = True         # Send 5 PM daily summary

# Timing
DAILY_SUMMARY_TIME_HOUR = 17        # 5 PM (24-hour format)
DAILY_SUMMARY_TIME_MINUTE = 0

# ===== TESTING =====
# Set to True during development to print emails instead of sending
TEST_MODE = False

# Test email addresses (for development)
TEST_PARENT_EMAIL = "sourabhkrgupta720@gmail.com"  # Replace with your test email