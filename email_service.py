# =================================================================
#   A.R.I.S.E. Email Service - HACKATHON VERSION
#   Simple, reliable email functions for parent alerts
# =================================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

# Import configuration
try:
    from config import *
except ImportError:
    print("ERROR: config.py not found!")
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = ""
    SENDER_PASSWORD = ""
    SENDER_NAME = "A.R.I.S.E."
    ENABLE_INSTANT_ALERTS = True
    ENABLE_ABSENT_ALERTS = True
    TEST_MODE = False

logger = logging.getLogger(__name__)


def send_email(to_email, subject, html_content):
    """
    Core email sending function - handles all SMTP logic
    Returns: (success: bool, error_msg: str or None)
    """
    # Validate email
    if not to_email or '@' not in to_email:
        logger.warning(f"Invalid email address: {to_email}")
        return False, "Invalid email address"
    
    # Test mode - just print
    if TEST_MODE:
        print(f"\n{'='*60}")
        print(f"TEST MODE EMAIL")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"{'='*60}\n")
        return True, None
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg['To'] = to_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Connect to Gmail SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        # FIXED: Remove emoji from log message - use text only
        logger.info(f"Email sent successfully to {to_email}")
        return True, None
        
    except smtplib.SMTPAuthenticationError:
        error_msg = "Gmail authentication failed - check your app password"
        logger.error(f"Email failed - {error_msg}")
        return False, error_msg
        
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {str(e)}"
        logger.error(f"Email failed to {to_email}: {error_msg}")
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Email failed to {to_email}: {error_msg}")
        return False, error_msg


# =================================================================
#   ALERT TYPE 1: INSTANT PRESENT ALERT
# =================================================================

def send_instant_present_alert(student_name, parent_email, course_name, timestamp):
    """
    Send immediate alert when student marks attendance
    """
    if not ENABLE_INSTANT_ALERTS:
        logger.debug("Instant alerts disabled")
        return False, "Disabled"
    
    # Format time nicely
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = dt.strftime("%I:%M %p")
        date_str = dt.strftime("%d %B %Y")
    except (ValueError, TypeError):
        time_str = "just now"
        date_str = datetime.now().strftime("%d %B %Y")
    
    subject = f"✅ {student_name} - Attendance Marked"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
            .container {{ background: white; max-width: 600px; margin: 0 auto; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .header {{ background: #28a745; color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ padding: 30px; }}
            .info-box {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            .info-box p {{ margin: 10px 0; font-size: 16px; }}
            .info-box strong {{ color: #333; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Attendance Marked Successfully</h1>
            </div>
            <div class="content">
                <p style="font-size: 16px; color: #333;">Dear Parent,</p>
                <p style="font-size: 16px; color: #333;">Your child <strong>{student_name}</strong> has successfully marked attendance.</p>
                
                <div class="info-box">
                    <p><strong>📚 Course:</strong> {course_name}</p>
                    <p><strong>🕐 Time:</strong> {time_str}</p>
                    <p><strong>📅 Date:</strong> {date_str}</p>
                </div>
                
                <p style="font-size: 14px; color: #666; margin-top: 20px;">
                    This is an automated message from the A.R.I.S.E. Attendance System.
                </p>
            </div>
            <div class="footer">
                <p><strong>A.R.I.S.E.</strong> - Automated Roll-call & Integrated Session Entry</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(parent_email, subject, html)


# =================================================================
#   ALERT TYPE 2: ABSENT ALERT (After Session Ends)
# =================================================================

def send_absent_alert(student_name, parent_email, course_name, date_str):
    """
    Send alert when student is absent from a class
    """
    if not ENABLE_ABSENT_ALERTS:
        logger.debug("Absent alerts disabled")
        return False, "Disabled"
    
    subject = f"⚠️ {student_name} - Absent from {course_name}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
            .container {{ background: white; max-width: 600px; margin: 0 auto; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .header {{ background: #dc3545; color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ padding: 30px; }}
            .warning-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 20px; margin: 20px 0; }}
            .warning-box p {{ margin: 10px 0; font-size: 16px; color: #856404; }}
            .info-box {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            .info-box p {{ margin: 10px 0; font-size: 16px; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ Absent Alert</h1>
            </div>
            <div class="content">
                <p style="font-size: 16px; color: #333;">Dear Parent,</p>
                
                <div class="warning-box">
                    <p><strong>Your child {student_name} was marked ABSENT.</strong></p>
                </div>
                
                <div class="info-box">
                    <p><strong>📚 Course:</strong> {course_name}</p>
                    <p><strong>📅 Date:</strong> {date_str}</p>
                </div>
                
                <p style="font-size: 14px; color: #666; margin-top: 20px;">
                    If this is incorrect or your child had a valid reason for absence, 
                    please contact the course instructor.
                </p>
            </div>
            <div class="footer">
                <p><strong>A.R.I.S.E.</strong> - Automated Roll-call & Integrated Session Entry</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(parent_email, subject, html)


# =================================================================
#   ALERT TYPE 3: DAILY SUMMARY (5 PM)
# =================================================================

def send_daily_summary(student_name, parent_email, summary_data):
    """
    Send comprehensive daily attendance summary
    
    summary_data format:
    {
        'date': '17 January 2026',
        'present_today': 3,
        'absent_today': 1,
        'total_today': 4,
        'courses_today': [
            {'name': 'Mathematics', 'status': 'Present', 'time': '09:00 AM'},
            {'name': 'Physics', 'status': 'Absent', 'time': '11:00 AM'},
        ],
        'overall_percentage': 87.5,
        'total_classes': 120,
        'attended_classes': 105
    }
    """
    
    # Build course table rows
    course_rows = ""
    for course in summary_data['courses_today']:
        if course['status'] == 'Present':
            icon = "✅"
            status_color = "#28a745"
            bg_color = "#d4edda"
        else:
            icon = "❌"
            status_color = "#dc3545"
            bg_color = "#f8d7da"
        
        course_rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #ddd;">{course['name']}</td>
            <td style="padding: 15px; border-bottom: 1px solid #ddd; color: #666;">{course.get('time', 'N/A')}</td>
            <td style="padding: 15px; border-bottom: 1px solid #ddd; text-align: center; background: {bg_color};">
                <span style="color: {status_color}; font-weight: bold;">{icon} {course['status']}</span>
            </td>
        </tr>
        """
    
    # Determine overall status color
    if summary_data['overall_percentage'] >= 75:
        overall_color = "#28a745"  # Green
    elif summary_data['overall_percentage'] >= 60:
        overall_color = "#ffc107"  # Yellow
    else:
        overall_color = "#dc3545"  # Red
    
    subject = f"📊 {student_name} - Daily Attendance Summary"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
            .container {{ background: white; max-width: 650px; margin: 0 auto; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin: 25px 0; }}
            .stat-card {{ text-align: center; padding: 20px; border-radius: 8px; }}
            .stat-card.present {{ background: #d4edda; border: 2px solid #28a745; }}
            .stat-card.absent {{ background: #f8d7da; border: 2px solid #dc3545; }}
            .stat-card.total {{ background: #d1ecf1; border: 2px solid #17a2b8; }}
            .stat-card h2 {{ margin: 0; font-size: 32px; color: #333; }}
            .stat-card p {{ margin: 5px 0 0 0; font-size: 14px; color: #666; }}
            table {{ width: 100%; border-collapse: collapse; margin: 25px 0; }}
            th {{ background: #667eea; color: white; padding: 15px; text-align: left; font-weight: 600; }}
            .overall-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 8px; text-align: center; margin: 25px 0; }}
            .overall-box h2 {{ margin: 0; font-size: 48px; }}
            .overall-box p {{ margin: 10px 0 0 0; font-size: 16px; opacity: 0.9; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Daily Attendance Summary</h1>
                <p>{summary_data.get('date', datetime.now().strftime('%d %B %Y'))}</p>
            </div>
            <div class="content">
                <p style="font-size: 16px; color: #333;">Dear Parent,</p>
                <p style="font-size: 16px; color: #333;">
                    Here is today's attendance report for <strong>{student_name}</strong>:
                </p>
                
                <div class="stats-grid">
                    <div class="stat-card present">
                        <h2>{summary_data['present_today']}</h2>
                        <p>Classes Attended</p>
                    </div>
                    <div class="stat-card absent">
                        <h2>{summary_data['absent_today']}</h2>
                        <p>Classes Missed</p>
                    </div>
                    <div class="stat-card total">
                        <h2>{summary_data.get('total_today', summary_data['present_today'] + summary_data['absent_today'])}</h2>
                        <p>Total Classes</p>
                    </div>
                </div>
                
                <h3 style="color: #333; margin-top: 30px;">Today's Classes</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Course Name</th>
                            <th>Time</th>
                            <th style="text-align: center;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {course_rows}
                    </tbody>
                </table>
                
                <div class="overall-box">
                    <p style="font-size: 14px; margin: 0 0 10px 0; opacity: 0.9;">OVERALL ATTENDANCE</p>
                    <h2>{summary_data['overall_percentage']}%</h2>
                    <p>{summary_data.get('attended_classes', 'N/A')} out of {summary_data.get('total_classes', 'N/A')} classes attended</p>
                </div>
                
                <p style="font-size: 13px; color: #666; margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
                    💡 <strong>Tip:</strong> Attendance below 75% may affect eligibility for final examinations. 
                    Please ensure your child maintains regular attendance.
                </p>
            </div>
            <div class="footer">
                <p><strong>A.R.I.S.E.</strong> - Automated Roll-call & Integrated Session Entry</p>
                <p>Generated on {datetime.now().strftime('%d %B %Y at %I:%M %p')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(parent_email, subject, html)


# =================================================================
#   UTILITY FUNCTION - Test Email System
# =================================================================

def test_email_system(test_email):
    """
    Quick test function to verify email system works
    """
    print("\n" + "="*60)
    print("🧪 TESTING EMAIL SYSTEM")
    print("="*60)
    
    # Test 1: Instant Alert
    print("\n1️⃣ Testing Instant Present Alert...")
    success, error = send_instant_present_alert(
        "Test Student",
        test_email,
        "Test Course - Mathematics",
        datetime.now().isoformat()
    )
    print(f"   Result: {'✅ SUCCESS' if success else '❌ FAILED - ' + str(error)}")
    
    # Test 2: Absent Alert
    print("\n2️⃣ Testing Absent Alert...")
    success, error = send_absent_alert(
        "Test Student",
        test_email,
        "Test Course - Physics",
        datetime.now().strftime("%d %B %Y")
    )
    print(f"   Result: {'✅ SUCCESS' if success else '❌ FAILED - ' + str(error)}")
    
    # Test 3: Daily Summary
    print("\n3️⃣ Testing Daily Summary...")
    test_summary = {
        'date': datetime.now().strftime("%d %B %Y"),
        'present_today': 2,
        'absent_today': 1,
        'total_today': 3,
        'courses_today': [
            {'name': 'Mathematics', 'status': 'Present', 'time': '09:00 AM'},
            {'name': 'Physics', 'status': 'Present', 'time': '11:00 AM'},
            {'name': 'Chemistry', 'status': 'Absent', 'time': '02:00 PM'}
        ],
        'overall_percentage': 87.5,
        'total_classes': 120,
        'attended_classes': 105
    }
    success, error = send_daily_summary("Test Student", test_email, test_summary)
    print(f"   Result: {'✅ SUCCESS' if success else '❌ FAILED - ' + str(error)}")
    
    print("\n" + "="*60)
    print("✅ All tests complete! Check your inbox.")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Run test when this file is executed directly
    print("📧 A.R.I.S.E. Email Service - Test Mode")
    test_email = input("Enter your test email address: ")
    test_email_system(test_email)