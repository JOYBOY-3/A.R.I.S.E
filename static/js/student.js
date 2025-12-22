document.addEventListener('DOMContentLoaded', () => {
  const views = {
    login: document.getElementById('student-login-view'),
    dashboard: document.getElementById('student-dashboard-view'),
    courseDetail: document.getElementById('course-detail-view'),
  };

  let token = localStorage.getItem('studentToken');
  let currentCourseId = null;

  // View management
  function showView(viewName) {
    Object.values(views).forEach((view) => (view.style.display = 'none'));
    if (views[viewName]) views[viewName].style.display = 'block';
  }

  // Check if already logged in
  if (token) {
    loadDashboard();
  } else {
    showView('login');
  }

  // Login handler
  document
    .getElementById('student-login-form')
    .addEventListener('submit', async (e) => {
      e.preventDefault();
      const univRoll = document.getElementById('univ-roll-input').value.trim();
      const password = document.getElementById('password-input').value;
      const loginMessage = document.getElementById('login-message');

      loginMessage.textContent = 'Logging in...';

      try {
        const response = await fetch('/api/student/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ university_roll_no: univRoll, password }),
        });

        const data = await response.json();

        if (response.ok) {
          token = data.token;
          localStorage.setItem('studentToken', token);
          document.getElementById(
            'welcome-message'
          ).textContent = `Welcome, ${data.student_name}!`;
          loadDashboard();
        } else {
          loginMessage.textContent = data.message || 'Login failed';
        }
      } catch (error) {
        console.error('Login error:', error);
        loginMessage.textContent = 'Network error. Is the server running?';
      }
    });

  // Load dashboard
  async function loadDashboard() {
    try {
      const response = await fetch('/api/student/dashboard', {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.status === 401) {
        logout();
        return;
      }

      const data = await response.json();

      document.getElementById(
        'overall-percentage'
      ).textContent = `${data.overall_percentage}%`;

      const coursesContainer = document.getElementById('courses-container');
      coursesContainer.innerHTML = '';

      data.courses.forEach((course) => {
        const courseCard = document.createElement('div');
        courseCard.className = 'stat-card';
        courseCard.style.cursor = 'pointer';
        courseCard.innerHTML = `
                    <h3>${course.course_name}</h3>
                    <p style="font-size: 2rem; font-weight: bold; color: var(--primary-color);">
                        ${course.percentage}%
                    </p>
                    <p style="color: var(--text-light);">
                        ${course.present_count} / ${course.total_sessions} classes attended
                    </p>
                `;
        courseCard.addEventListener('click', () =>
          loadCourseDetail(course.course_id)
        );
        coursesContainer.appendChild(courseCard);
      });

      showView('dashboard');
    } catch (error) {
      console.error('Dashboard error:', error);
    }
  }

  // Load course detail
  async function loadCourseDetail(courseId) {
    currentCourseId = courseId;

    try {
      const response = await fetch(`/api/student/course/${courseId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      const data = await response.json();

      document.getElementById('course-name-header').textContent =
        data.course_name;
      document.getElementById('present-count').textContent = data.present_count;
      document.getElementById('absent-count').textContent = data.absent_count;
      document.getElementById(
        'course-percentage'
      ).textContent = `${data.percentage}%`;

      const logContainer = document.getElementById('attendance-log');
      logContainer.innerHTML = '';

      data.log.forEach((entry) => {
        const dateObj = new Date(entry.date);
        const dateStr = dateObj.toLocaleDateString('en-GB', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
        });
        const timeStr = dateObj.toLocaleTimeString('en-GB', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        });

        const logItem = document.createElement('div');
        logItem.className = 'stat-card';
        logItem.style.display = 'flex';
        logItem.style.justifyContent = 'space-between';
        logItem.style.alignItems = 'center';

        const icon = entry.status === 'Present' ? '✅' : '❌';
        const color =
          entry.status === 'Present'
            ? 'var(--success-color)'
            : 'var(--danger-color)';

        logItem.innerHTML = `
                    <span>
                      ${dateStr} <span style="color: var(--text-light); font-size: 0.95em;">(${timeStr})</span>
                    </span>
                    <span style="color: ${color}; font-weight: bold;">
                        ${icon} ${entry.status}
                    </span>
                `;
        logContainer.appendChild(logItem);
      });

      showView('courseDetail');
    } catch (error) {
      console.error('Course detail error:', error);
    }
  }

  // Back to dashboard
  document.getElementById('back-to-dashboard').addEventListener('click', () => {
    loadDashboard();
  });

  // Logout
  document.getElementById('logout-button').addEventListener('click', logout);

  function logout() {
    localStorage.removeItem('studentToken');
    token = null;
    document.getElementById('univ-roll-input').value = '';
    document.getElementById('password-input').value = '';
    document.getElementById('login-message').textContent = '';
    showView('login');
  }
});
