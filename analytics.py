import math

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
