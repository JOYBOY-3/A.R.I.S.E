import math
import io
import base64
from datetime import datetime

# Matplotlib configuration for server-side rendering (no GUI)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def calculate_status_and_improvement(present_count, total_sessions, target_percent=75.0, critical_percent=60.0):
    """
    Calculates the student's attendance status and improvement plan.
    
    Args:
        present_count (int): Number of sessions attended.
        total_sessions (int): Total number of sessions conducted so far.
        target_percent (float): The target attendance percentage (default 75.0).
        critical_percent (float): The critical attendance threshold (default 60.0).
        
    Returns:
        dict: A dictionary containing:
            - current_percent (float)
            - status (str): 'Good', 'Warning', 'Critical'
            - color (str): 'green', 'yellow', 'red'
            - needed_to_recover (int): Classes to attend consecutively to reach target.
            - buffer_available (int): Classes that can be missed while staying above target.
            - message (str): A human-readable status message.
            - action_plan (str): Specific advice on what to do.
    """
    if total_sessions == 0:
        return {
            "current_percent": 0.0,
            "status": "Good",
            "color": "green",
            "needed_to_recover": 0,
            "buffer_available": 0,
            "message": "No sessions yet.",
            "action_plan": "Get ready for your first class!"
        }

    current_percent = (present_count / total_sessions) * 100
    
    # Determine Status
    if current_percent < critical_percent:
        status = "Critical"
        color = "red"
        message = f"Critical: Attendance is below {critical_percent}%!"
    elif current_percent < target_percent:
        status = "Warning"
        color = "yellow"
        message = f"Warning: Attendance is below {target_percent}%."
    else:
        status = "Good"
        color = "green"
        message = f"Great! You are above {target_percent}%."

    # Calculate 'Needed to Recover'
    # Formula: (present + x) / (total + x) >= target
    # x >= (target * total - present) / (1 - target)
    target_rate = target_percent / 100.0
    needed_to_recover = 0
    
    if current_percent < target_percent:
        numerator = (total_sessions * target_rate) - present_count
        denominator = 1.0 - target_rate
        if denominator > 0:
            needed_to_recover = math.ceil(numerator / denominator)
        else:
            needed_to_recover = 999 # Mathematically impossible if target is 100% and we are below it
            
    # Calculate 'Buffer Available' (How many can I miss?)
    # Formula: present / (total + x) >= target
    # x <= present/target - total
    buffer_available = 0
    if current_percent > target_percent:
        max_total = present_count / target_rate
        buffer_available = int(max_total - total_sessions)

    # Generate Action Plan
    if needed_to_recover > 0:
        action_plan = f"You need to attend the next {needed_to_recover} classes consecutively to reach {target_percent}%."
    elif buffer_available > 0:
        action_plan = f"You are in the Safe Zone. You can miss up to {buffer_available} classes and stay above {target_percent}%."
    else:
        action_plan = "Maintain your current attendance streak to stay safe."

    return {
        "current_percent": round(current_percent, 1),
        "status": status,
        "color": color,
        "needed_to_recover": needed_to_recover,
        "buffer_available": buffer_available,
        "message": message,
        "action_plan": action_plan
    }


# =============================================================================
#   Teacher Analytics Functions
# =============================================================================

def generate_attendance_trend_graph(sessions_data):
    """
    Generates a base64-encoded PNG line graph showing attendance trends over time.
    
    Args:
        sessions_data: List of dicts with 'date', 'present_count', 'total_students' keys
        
    Returns:
        str: Base64-encoded PNG image data URI, or None if no data
    """
    if not sessions_data or len(sessions_data) < 2:
        return None
    
    try:
        # Parse dates and calculate percentages
        dates = []
        percentages = []
        
        for session in sessions_data:
            try:
                date_str = session.get('date', session.get('start_time', ''))
                if isinstance(date_str, str):
                    # Handle different date formats
                    if 'T' in date_str:
                        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        date_obj = datetime.strptime(date_str.split(' ')[0], '%Y-%m-%d')
                else:
                    date_obj = date_str
                
                dates.append(date_obj)
                
                total = session.get('total_students', 1)
                present = session.get('present_count', 0)
                pct = (present / total * 100) if total > 0 else 0
                percentages.append(pct)
            except (ValueError, TypeError):
                continue
        
        if len(dates) < 2:
            return None
        
        # Create the figure with a clean style
        fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
        fig.patch.set_facecolor('#1a1d23')  # Dark background
        ax.set_facecolor('#252930')
        
        # Plot the line
        ax.plot(dates, percentages, 
                color='#4da3ff', 
                linewidth=2.5, 
                marker='o', 
                markersize=6,
                markerfacecolor='#4da3ff',
                markeredgecolor='white',
                markeredgewidth=1)
        
        # Fill under the line
        ax.fill_between(dates, percentages, alpha=0.2, color='#4da3ff')
        
        # Add 75% threshold line
        ax.axhline(y=75, color='#28a745', linestyle='--', linewidth=1.5, alpha=0.7, label='75% Target')
        
        # Style the axes
        ax.set_ylabel('Attendance %', color='#e9ecef', fontsize=11)
        ax.set_xlabel('Session Date', color='#e9ecef', fontsize=11)
        ax.tick_params(colors='#adb5bd', labelsize=9)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate(rotation=45)
        
        # Set y-axis range
        ax.set_ylim(0, 105)
        
        # Style grid
        ax.grid(True, alpha=0.2, color='#6c757d')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#3d4450')
        ax.spines['bottom'].set_color('#3d4450')
        
        # Legend
        ax.legend(loc='lower right', facecolor='#252930', edgecolor='#3d4450', labelcolor='#e9ecef')
        
        plt.tight_layout()
        
        # Save to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)
        
        return f"data:image/png;base64,{image_base64}"
        
    except Exception as e:
        print(f"Error generating trend graph: {e}")
        return None


def get_at_risk_students(students_data, threshold=75.0):
    """
    Identifies students with attendance below the threshold.
    
    Args:
        students_data: List of dicts with 'student_name', 'present_count', 'total_sessions' keys
        threshold: Attendance percentage threshold (default 75.0)
        
    Returns:
        List of at-risk student dicts sorted by attendance (lowest first)
    """
    at_risk = []
    
    for student in students_data:
        total = student.get('total_sessions', 0)
        present = student.get('present_count', 0)
        
        if total == 0:
            continue
            
        pct = (present / total) * 100
        
        if pct < threshold:
            # Calculate sessions needed to reach 75%
            target_rate = threshold / 100.0
            if target_rate < 1.0:
                numerator = (total * target_rate) - present
                denominator = 1.0 - target_rate
                sessions_needed = math.ceil(numerator / denominator) if denominator > 0 else 999
            else:
                sessions_needed = 999
            
            at_risk.append({
                'student_id': student.get('student_id'),
                'student_name': student.get('student_name', 'Unknown'),
                'university_roll_no': student.get('university_roll_no', ''),
                'class_roll_id': student.get('class_roll_id', ''),
                'attendance_percent': round(pct, 1),
                'present_count': present,
                'total_sessions': total,
                'sessions_needed': sessions_needed,
                'status': 'Critical' if pct < 60 else 'Warning'
            })
    
    # Sort by attendance percentage (lowest first)
    at_risk.sort(key=lambda x: x['attendance_percent'])
    
    return at_risk

