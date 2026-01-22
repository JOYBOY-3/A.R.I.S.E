// Initialize dark mode BEFORE page loads
(function () {
  const theme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', theme);
})();

// Dark Mode Toggle Logic
window.toggleTheme = function () {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const newTheme = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  updateThemeIcon(newTheme);
};

function updateThemeIcon(theme) {
  const icon = document.getElementById('theme-icon');
  if (icon) {
    icon.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // 1. Ensure Theme Toggle Button Exists (Robustness Fix)
  let toggleBtn = document.querySelector('.theme-toggle');

  // Dynamic Injection if missing (User requested "entire UI", ensures it's always there)
  if (!toggleBtn) {
    console.warn(
      'Theme toggle button missing in HTML, injecting dynamically...',
    );
    toggleBtn = document.createElement('button');
    toggleBtn.className = 'theme-toggle';
    toggleBtn.title = 'Toggle Dark Mode';
    toggleBtn.innerHTML = '<span id="theme-icon">🌙</span>';
    document.body.appendChild(toggleBtn);
  }

  // 2. Attach Click Listener (Removes reliance on inline onclick)
  // Remove existing listeners by cloning (optional, but safe)
  // toggleBtn.replaceWith(toggleBtn.cloneNode(true));
  // actually cloning removes event listeners, but we want to add one.
  // We'll just add it. If onclick exists, it runs twice? No, we'll remove onclick from HTML.
  toggleBtn.addEventListener('click', window.toggleTheme);

  // 3. Set Initial Icon State
  const currentTheme = localStorage.getItem('theme') || 'light';
  updateThemeIcon(currentTheme);

  const views = {
    login: document.getElementById('student-login-view'),
    dashboard: document.getElementById('student-dashboard-view'),
    courseDetail: document.getElementById('course-detail-view'),
    analytics: document.getElementById('analytics-view'),
  };

  let token = localStorage.getItem('studentToken');
  let currentCourseId = null;
  let currentSemesterId = null; // Track selected semester filter
  let chartInstances = {}; // Store Chart.js instances for cleanup

  // --- 1. Navigation & View Management ---
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
          document.getElementById('welcome-message').textContent =
            `Welcome, ${data.student_name}!`;
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
      // First, load all available semesters
      const semestersResponse = await fetch('/api/student/semesters', {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (semestersResponse.status === 401) {
        logout();
        return;
      }

      const semesters = await semestersResponse.json();

      // Populate semester filter dropdown
      const semesterFilter = document.getElementById('semester-filter');
      semesterFilter.innerHTML = '<option value="">All Semesters</option>';
      semesters.forEach((semester) => {
        const option = document.createElement('option');
        option.value = semester.id;
        option.textContent = semester.semester_name;
        semesterFilter.appendChild(option);
      });

      // Load dashboard data (with optional semester filter)
      const dashboardUrl = currentSemesterId
        ? `/api/student/dashboard?semester_id=${currentSemesterId}`
        : '/api/student/dashboard';

      const response = await fetch(dashboardUrl, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.status === 401) {
        logout();
        return;
      }

      const data = await response.json();

      // Set welcome message with student name
      document.getElementById('welcome-message').textContent =
        `Welcome, ${data.student_name}!`;

      document.getElementById('overall-percentage').textContent =
        `${data.overall_percentage}%`;

      // Update semester label
      const semesterLabel = document.getElementById('semester-label');
      if (data.is_filtered && data.semester_name) {
        semesterLabel.textContent = `Showing: ${data.semester_name}`;
      } else {
        semesterLabel.textContent = 'Showing: All Semesters';
      }

      // Update filter dropdown to show selected semester
      semesterFilter.value = currentSemesterId || '';

      const coursesContainer = document.getElementById('courses-container');
      coursesContainer.innerHTML = '';

      if (data.courses.length === 0) {
        coursesContainer.innerHTML =
          '<p style="color: var(--text-light); text-align: center;">No courses found for selected semester.</p>';
      } else {
        // Group courses by semester if "All Semesters" is selected
        if (!currentSemesterId) {
          const coursesBySemester = {};
          data.courses.forEach((course) => {
            const semName = course.semester_name || 'Other';
            if (!coursesBySemester[semName]) coursesBySemester[semName] = [];
            coursesBySemester[semName].push(course);
          });

          Object.keys(coursesBySemester)
            .sort()
            .forEach((semName, index) => {
              // Create Accordion Item
              const accordionItem = document.createElement('div');
              accordionItem.style.marginBottom = '1rem';

              // Accordion Header
              const header = document.createElement('div');
              header.className = 'stat-card'; // Reuse card style for header
              header.style.marginBottom = '0.5rem';
              header.style.cursor = 'pointer';
              header.style.display = 'flex';
              header.style.justifyContent = 'space-between';
              header.style.alignItems = 'center';
              header.style.padding = '1rem';
              header.style.backgroundColor = 'var(--bg-secondary)';

              header.innerHTML = `
                    <h3 style="margin: 0;">${semName}</h3>
                    <span style="font-size: 1.2rem;">▼</span>
                `;

              // Accordion Content (Hidden by default)
              const content = document.createElement('div');
              content.style.display = 'none';
              content.style.paddingLeft = '0.5rem';

              // Toggle Logic
              header.addEventListener('click', () => {
                const isHidden = content.style.display === 'none';
                content.style.display = isHidden ? 'block' : 'none';
                header.querySelector('span').textContent = isHidden ? '▲' : '▼';
              });

              // Add courses to content
              coursesBySemester[semName].forEach((course) => {
                content.appendChild(createCourseCard(course));
              });

              accordionItem.appendChild(header);
              accordionItem.appendChild(content);
              coursesContainer.appendChild(accordionItem);
            });
        } else {
          // Render normally for specific semester
          data.courses.forEach((course) => {
            coursesContainer.appendChild(createCourseCard(course));
          });
        }
      }

      showView('dashboard');
    } catch (error) {
      console.error('Dashboard error:', error);
    }
  }

  function createCourseCard(course) {
    const courseCard = document.createElement('div');
    courseCard.className = 'stat-card';
    courseCard.style.cursor = 'pointer';

    // Status & Improvement Data
    const analytics = course.analytics || {};
    const statusColor =
      analytics.color === 'green'
        ? 'var(--success-color)'
        : analytics.color === 'yellow'
          ? '#ffc107'
          : 'var(--danger-color)';
    const statusBg =
      analytics.color === 'green'
        ? 'rgba(40, 167, 69, 0.1)'
        : analytics.color === 'yellow'
          ? 'rgba(255, 193, 7, 0.1)'
          : 'rgba(220, 53, 69, 0.1)';

    courseCard.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
           <h3 style="margin-bottom: 0;">${course.course_name}</h3>
           <span style="font-size: 0.8rem; color: var(--text-light);">${analytics.status || ''}</span>
        </div>
        <div style="text-align: right;">
           <span style="font-size: 1.8rem; font-weight: bold; color: ${statusColor};">
              ${course.percentage}%
           </span>
        </div>
      </div>
      
      <div style="margin: 10px 0; height: 6px; background: #eee; border-radius: 3px; overflow: hidden;">
          <div style="width: ${course.percentage}%; background: ${statusColor}; height: 100%;"></div>
      </div>

      <p style="color: var(--text-light); font-size: 0.9rem; margin-bottom: 10px;">
          ${course.present_count} / ${course.total_sessions} classes attended
      </p>
      
      ${
        analytics.action_plan
          ? `
      <div style="background-color: ${statusBg}; padding: 8px; border-radius: 6px; font-size: 0.85rem; border-left: 3px solid ${statusColor}; color: var(--text-primary);">
          <strong>💡 Plan:</strong> ${analytics.action_plan}
      </div>
      `
          : ''
      }
    `;
    courseCard.addEventListener('click', () =>
      loadCourseDetail(course.course_id),
    );
    return courseCard;
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
      document.getElementById('course-percentage').textContent =
        `${data.percentage}%`;

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

  // Load analytics
  async function loadAnalytics(semesterId = null) {
    try {
      // 1. Populate Filter if empty
      const filter = document.getElementById('analytics-semester-filter');
      // If only default option exists, try to populate
      if (filter && filter.options.length === 1) {
        try {
          const semestersResponse = await fetch('/api/student/semesters', {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (semestersResponse.ok) {
            const semesters = await semestersResponse.json();
            semesters.forEach((semester) => {
              const option = document.createElement('option');
              option.value = semester.id;
              option.textContent = semester.semester_name;
              filter.appendChild(option);
            });
          }
        } catch (err) {
          console.error('Failed to load semesters for analytics filter', err);
        }

        // Add change listener (only once)
        filter.addEventListener('change', (e) => {
          const selectedId = e.target.value;
          loadAnalytics(selectedId || null);
        });
      }

      // Set current filter value without triggering change event loop
      if (filter) {
        filter.value = semesterId || '';
      }

      const url = semesterId
        ? `/api/student/analytics?semester_id=${semesterId}`
        : '/api/student/analytics';

      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.status === 401) {
        logout();
        return;
      }

      if (!response.ok) {
        const noAnalyticsMsg = document.getElementById('no-analytics-message');
        if (noAnalyticsMsg) noAnalyticsMsg.style.display = 'block';
        const container = document.getElementById('analytics-container');
        if (container) container.innerHTML = '';
        showView('analytics');
        return;
      }

      const data = await response.json();
      const analyticsContainer = document.getElementById('analytics-container');
      const noAnalyticsMsg = document.getElementById('no-analytics-message');

      if (!data.analytics || Object.keys(data.analytics).length === 0) {
        if (noAnalyticsMsg) noAnalyticsMsg.style.display = 'block';
        if (analyticsContainer) analyticsContainer.innerHTML = '';
        showView('analytics');
        return;
      }

      if (noAnalyticsMsg) noAnalyticsMsg.style.display = 'none';
      if (analyticsContainer) analyticsContainer.innerHTML = '';

      // Destroy previous chart instances
      Object.values(chartInstances).forEach((chart) => {
        if (chart) chart.destroy();
      });
      chartInstances = {};

      const courses = Object.keys(data.analytics).map((key) => ({
        id: key,
        ...data.analytics[key],
      }));

      // Render Logic: Accordion vs Flat
      if (!semesterId) {
        // Group by Semester
        const coursesBySemester = {};
        courses.forEach((course) => {
          const semName = course.semester_name || 'Other';
          if (!coursesBySemester[semName]) coursesBySemester[semName] = [];
          coursesBySemester[semName].push(course);
        });

        Object.keys(coursesBySemester)
          .sort()
          .forEach((semName) => {
            // Create Accordion Item
            const accordionItem = document.createElement('div');
            accordionItem.style.marginBottom = '1rem';

            // Header
            const header = document.createElement('div');
            header.className = 'stat-card';
            header.style.marginBottom = '0.5rem';
            header.style.cursor = 'pointer';
            header.style.display = 'flex';
            header.style.justifyContent = 'space-between';
            header.style.alignItems = 'center';
            header.style.padding = '1rem';
            header.style.backgroundColor = 'var(--bg-secondary)';
            header.innerHTML = `
                  <h3 style="margin: 0;">${semName}</h3>
                  <span style="font-size: 1.2rem;">▼</span>
              `;

            // Content
            const content = document.createElement('div');
            content.style.display = 'none';
            content.style.paddingLeft = '0.5rem';

            // Toggle
            header.addEventListener('click', () => {
              const isHidden = content.style.display === 'none';
              content.style.display = isHidden ? 'block' : 'none';
              header.querySelector('span').textContent = isHidden ? '▲' : '▼';
            });

            // Add cards
            coursesBySemester[semName].forEach((course) => {
              content.appendChild(
                createAnalyticsCard(course, data.min_attendance_requirement),
              );
            });

            accordionItem.appendChild(header);
            accordionItem.appendChild(content);
            analyticsContainer.appendChild(accordionItem);
          });
      } else {
        // Flat List
        courses.forEach((course) => {
          analyticsContainer.appendChild(
            createAnalyticsCard(course, data.min_attendance_requirement),
          );
        });
      }

      showView('analytics');

      // Render Charts after appending to DOM (needed for canvas context)
      // We need to wait a tick for accordions to be in DOM, though display:none might affect canvas rendering size.
      // Chart.js usually handles hidden canvas better if responsive:true.
      setTimeout(
        () => renderAnalyticsCharts(courses, data.min_attendance_requirement),
        100,
      );
    } catch (error) {
      console.error('Analytics error:', error);
    }
  }

  function createAnalyticsCard(analytics, minReq) {
    const courseId = analytics.id;

    // Determine status color
    let statusColor, statusBgColor, statusEmoji;
    if (analytics.status === 'good') {
      statusColor = '#28a745';
      statusBgColor = '#d4edda';
      statusEmoji = '✅';
    } else if (analytics.status === 'warning') {
      statusColor = '#ffc107';
      statusBgColor = '#fff3cd';
      statusEmoji = '⚠️';
    } else {
      statusColor = '#dc3545';
      statusBgColor = '#f8d7da';
      statusEmoji = '❌';
    }

    const trendEmoji =
      analytics.trend_direction === 'up'
        ? '📈'
        : analytics.trend_direction === 'down'
          ? '📉'
          : '➡️';

    const card = document.createElement('div');
    card.className = 'stat-card';
    card.style.borderLeft = `4px solid ${statusColor}`;
    card.style.backgroundColor = statusBgColor;
    card.style.marginBottom = '1rem';

    const chartCanvasId = `chart-${courseId}`;

    card.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">
              <h3 style="margin-top: 0; color: #212529;">${analytics.course_name}</h3>
              <p style="margin: 0.5rem 0; font-size: 0.95rem; color: #212529;">
                <strong>Status:</strong> ${statusEmoji} ${analytics.status.toUpperCase()}
              </p>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0;">
            <div>
              <p style="margin: 0.25rem 0; font-size: 0.85rem; color: #6c757d;">Last 7 Days</p>
              <p style="margin: 0; font-size: 1.5rem; font-weight: bold; color: ${statusColor};">${analytics.last_7_days_avg.toFixed(1)}%</p>
            </div>
            <div>
              <p style="margin: 0.25rem 0; font-size: 0.85rem; color: #6c757d;">Last 30 Days</p>
              <p style="margin: 0; font-size: 1.5rem; font-weight: bold; color: #6c757d;">${analytics.last_30_days_avg.toFixed(1)}%</p>
            </div>
            <div>
              <p style="margin: 0.25rem 0; font-size: 0.85rem; color: #6c757d;">Semester Total</p>
              <p style="margin: 0; font-size: 1.5rem; font-weight: bold; color: #0066cc;">${analytics.semester_total.toFixed(1)}%</p>
            </div>
            <div>
              <p style="margin: 0.25rem 0; font-size: 0.85rem; color: #6c757d;">Trend</p>
              <p style="margin: 0; font-size: 1.2rem; font-weight: bold;">${trendEmoji}</p>
            </div>
          </div>

          <p style="margin: 0.5rem 0; padding: 0.5rem; background-color: rgba(0,0,0,0.05); border-radius: 4px; font-size: 0.9rem; color: #212529;">
            Institute Requirement: <strong>${minReq}%</strong> | Your Progress: <strong style="color: ${statusColor};">${analytics.semester_total.toFixed(1)}%</strong>
          </p>

          ${
            analytics.improvement_plan
              ? `
            <div style="margin: 1rem 0; padding: 1rem; background-color: ${statusBgColor}; border-radius: 8px; border-left: 4px solid ${statusColor};">
                <h4 style="margin: 0 0 0.5rem 0; color: ${statusColor};">🚀 Status & Improvement Plan</h4>
                <p style="margin: 0; font-weight: bold; color: #212529;">${analytics.improvement_plan.message}</p>
                <p style="margin: 0.5rem 0 0 0; color: #212529;">${analytics.improvement_plan.action_plan}</p>
            </div>
          `
              : ''
          }

          <h4 style="margin: 1rem 0 0.5rem 0; color: #6c757d;">7-Day Trend</h4>
          <div style="height: 200px; position: relative;">
            <canvas id="${chartCanvasId}"></canvas>
          </div>

          <p style="margin: 0; font-size: 0.85rem; color: #6c757d;">
            Total Sessions: ${analytics.total_sessions}
          </p>
        `;
    return card;
  }

  function renderAnalyticsCharts(courses, minReq = 75) {
    courses.forEach((analytics) => {
      const courseId = analytics.id;
      const chartCanvasId = `chart-${courseId}`;
      const canvas = document.getElementById(chartCanvasId);

      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      const dailyData = analytics.daily_breakdown.map((d) =>
        d.percentage !== null ? d.percentage : 0,
      );
      const dailyLabels = analytics.daily_breakdown.map((d) => {
        const date = new Date(d.date);
        return date.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
        });
      });

      let statusColor, statusBgColor;
      if (analytics.status === 'good') {
        statusColor = '#28a745';
        statusBgColor = '#d4edda';
      } else if (analytics.status === 'warning') {
        statusColor = '#ffc107';
        statusBgColor = '#fff3cd';
      } else {
        statusColor = '#dc3545';
        statusBgColor = '#f8d7da';
      }

      chartInstances[chartCanvasId] = new Chart(ctx, {
        type: 'line',
        data: {
          labels: dailyLabels,
          datasets: [
            {
              label: 'Attendance %',
              data: dailyData,
              borderColor: statusColor,
              backgroundColor: statusBgColor,
              borderWidth: 2,
              fill: true,
              tension: 0.4,
              pointRadius: 4,
              pointBackgroundColor: statusColor,
              pointBorderColor: '#fff',
              pointBorderWidth: 2,
            },
            {
              label: `Requirement (${minReq}%)`,
              data: Array(dailyLabels.length).fill(minReq),
              borderColor: '#6c757d',
              borderWidth: 1,
              borderDash: [5, 5],
              pointRadius: 0,
              fill: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              max: 100,
              grid: {
                display: false,
              },
              ticks: {
                display: false,
              },
            },
            x: {
              grid: {
                display: false,
              },
              ticks: {
                font: {
                  size: 10,
                },
              },
            },
          },
          plugins: {
            legend: {
              display: false,
            },
          },
        },
      });
    });
  }

  // Back to dashboard
  document.getElementById('back-to-dashboard').addEventListener('click', () => {
    loadDashboard();
  });

  // View analytics button
  document
    .getElementById('view-analytics-button')
    .addEventListener('click', () => {
      loadAnalytics();
    });

  // Back from analytics
  document.getElementById('back-to-courses').addEventListener('click', () => {
    loadDashboard();
  });

  // Semester filter handler
  document.getElementById('semester-filter').addEventListener('change', (e) => {
    const selectedValue = e.target.value;
    currentSemesterId = selectedValue ? parseInt(selectedValue) : null;
    loadDashboard();
  });

  // Clear filter button
  document
    .getElementById('clear-filter-button')
    .addEventListener('click', () => {
      currentSemesterId = null;
      document.getElementById('semester-filter').value = '';
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

  // ============================================================
  // Critical Alerts System
  // ============================================================

  /**
   * Load and display critical attendance alerts
   * Shows icon only if there are critical alerts
   */
  async function loadCriticalAlerts() {
    if (!token) return;

    try {
      const response = await fetch('/api/student/critical-alerts', {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) throw new Error('Failed to load critical alerts');

      const data = await response.json();
      const { critical_alerts, warning_alerts, total_alert_count } = data;

      const alertIcon = document.getElementById('critical-alert-icon');
      const alertBadge = document.getElementById('alert-badge');

      // Show/hide icon based on total alert count
      if (total_alert_count > 0) {
        alertIcon.style.display = 'block';
        alertBadge.textContent = total_alert_count;
      } else {
        alertIcon.style.display = 'none';
      }

      // Store alerts for panel display
      window.currentCriticalAlerts = critical_alerts || [];
      window.currentWarningAlerts = warning_alerts || [];
    } catch (error) {
      console.error('Error loading critical alerts:', error);
    }
  }

  /**
   * Display critical alerts in sliding panel with two sections
   */
  window.showCriticalAlerts = function () {
    const panel = document.getElementById('critical-alerts-panel');
    const alertsContent = document.getElementById('alerts-content');

    const criticalAlerts = window.currentCriticalAlerts || [];
    const warningAlerts = window.currentWarningAlerts || [];

    if (criticalAlerts.length === 0 && warningAlerts.length === 0) {
      alertsContent.innerHTML =
        '<div class="no-alerts-message"><p>✅ No attendance alerts! Your attendance is in good standing.</p></div>';
    } else {
      let html = '';

      // Critical Alerts Section (< 60%)
      if (criticalAlerts.length > 0) {
        html += '<div class="alerts-section">';
        html +=
          '<div class="section-title">🚨 CRITICAL - Immediate Action Required</div>';
        criticalAlerts.forEach((alert) => {
          html += `
            <div class="alert-item critical">
              <div class="alert-course-name">📚 ${alert.course_name}</div>
              <div class="alert-percentage">${alert.attendance_percentage}%</div>
              <div class="alert-status-text">
                Below 60% critical threshold<br>
                <small>Attended: ${alert.present_count} / ${alert.total_sessions} classes</small>
              </div>
            </div>
          `;
        });
        html += '</div>';
      }

      // Warning Alerts Section (60% - 75%)
      if (warningAlerts.length > 0) {
        html += '<div class="alerts-section">';
        html +=
          '<div class="section-title">⚠️ WARNING - Improvement Needed</div>';
        warningAlerts.forEach((alert) => {
          html += `
            <div class="alert-item warning">
              <div class="alert-course-name">📚 ${alert.course_name}</div>
              <div class="alert-percentage">${alert.attendance_percentage}%</div>
              <div class="alert-status-text">
                Current attendance: ${alert.present_count} / ${alert.total_sessions} classes attended<br>
                <strong style="color: var(--primary-color); font-size: 1.1rem;">Attend ${alert.classes_needed} more class${alert.classes_needed !== 1 ? 'es' : ''} to reach 75%</strong>
              </div>
            </div>
          `;
        });
        html += '</div>';
      }

      alertsContent.innerHTML = html;
    }

    // Show panel with animation
    panel.classList.add('open');
  };

  /**
   * Close critical alerts panel
   */
  window.closeCriticalAlerts = function () {
    const panel = document.getElementById('critical-alerts-panel');
    panel.classList.remove('open');
  };

  // Add click handler to alert icon
  document
    .getElementById('critical-alert-icon')
    .addEventListener('click', () => {
      showCriticalAlerts();
    });

  // Load critical alerts on dashboard load
  const originalLoadDashboard = loadDashboard;
  loadDashboard = function () {
    originalLoadDashboard.call(this);
    loadCriticalAlerts();
  };
});

// ============================================================
// MODERN GAMING LEADERBOARD - JavaScript Functions
// Add these functions to your existing student.js file
// ============================================================

let leaderboardFiltersInitialized = false;
let allSemestersData = []; // Store all semesters and courses for leaderboard

/**
 * Initialize Leaderboard Filters (Semesters & Courses)
 */
async function initializeLeaderboardFilters() {
  if (leaderboardFiltersInitialized) return;

  const semFilter = document.getElementById('leaderboard-semester-filter');
  const courseFilter = document.getElementById('leaderboard-course-filter');
  const token = localStorage.getItem('studentToken');

  if (!semFilter || !courseFilter) return;

  try {
    // 1. Fetch All Semesters and Courses (Batch Context)
    const response = await fetch('/api/student/semesters', {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.ok) {
      allSemestersData = await response.json();

      // Clear existing options except default
      semFilter.innerHTML = '<option value="">All Semesters</option>';

      allSemestersData.forEach((sem) => {
        const option = document.createElement('option');
        option.value = sem.id;
        option.textContent = sem.semester_name;
        semFilter.appendChild(option);
      });
    }

    // 2. Initial Course Population (All Courses)
    updateLeaderboardCourseOptions(null);

    // 3. Add Event Listeners
    semFilter.addEventListener('change', (e) => {
      const semId = e.target.value;
      updateLeaderboardCourseOptions(semId);
      // Reset course filter to "All Courses" when semester changes
      courseFilter.value = '';
      loadLeaderboard(semId, null);
    });

    courseFilter.addEventListener('change', (e) => {
      const courseId = e.target.value;
      const semId = semFilter.value;
      loadLeaderboard(semId, courseId);
    });

    leaderboardFiltersInitialized = true;
  } catch (error) {
    console.error('Error initializing leaderboard filters:', error);
  }
}

/**
 * Update Course Options based on selected Semester
 * Uses locally stored data to ensure "Batch Context" availability
 */
function updateLeaderboardCourseOptions(semesterId) {
  const courseFilter = document.getElementById('leaderboard-course-filter');
  if (!courseFilter) return;

  try {
    // Save current selection if valid
    const currentSelection = courseFilter.value;

    courseFilter.innerHTML = '<option value="">All Courses</option>';

    let coursesToShow = [];

    if (semesterId) {
      // Filter by specific semester
      const semester = allSemestersData.find((s) => s.id == semesterId);
      if (semester && semester.courses) {
        coursesToShow = semester.courses;
      }
    } else {
      // Show ALL courses from ALL semesters
      allSemestersData.forEach((sem) => {
        if (sem.courses) {
          coursesToShow = coursesToShow.concat(sem.courses);
        }
      });
      // Remove duplicates based on ID (just in case)
      const uniqueCourses = [];
      const seenIds = new Set();
      coursesToShow.forEach((c) => {
        if (!seenIds.has(c.id)) {
          seenIds.add(c.id);
          uniqueCourses.push(c);
        }
      });
      coursesToShow = uniqueCourses;
    }

    // Sort courses alphabetically
    coursesToShow.sort((a, b) => a.course_name.localeCompare(b.course_name));

    if (coursesToShow.length > 0) {
      coursesToShow.forEach((course) => {
        const option = document.createElement('option');
        option.value = course.id;
        option.textContent = course.course_name;
        courseFilter.appendChild(option);
      });
    }

    // Restore selection if possible
    if (currentSelection) {
      const exists = Array.from(courseFilter.options).some(
        (opt) => opt.value === currentSelection,
      );
      if (exists) {
        courseFilter.value = currentSelection;
      }
    }
  } catch (error) {
    console.error('Error updating course options:', error);
  }
}

/**
 * Load leaderboard data from API
 */
async function loadLeaderboard(semesterId = null, courseId = null) {
  try {
    const token = localStorage.getItem('studentToken');
    if (!token) return;

    // Ensure filters are initialized
    if (!leaderboardFiltersInitialized) {
      await initializeLeaderboardFilters();
      // If we just initialized, filters are at default.
      // If args were passed (unlikely for first load), we might need to set them.
      // But typically first load is null, null.
    }

    // If called from elsewhere without args, grab current filter values
    if (
      semesterId === null &&
      courseId === null &&
      leaderboardFiltersInitialized
    ) {
      semesterId =
        document.getElementById('leaderboard-semester-filter').value || null;
      courseId =
        document.getElementById('leaderboard-course-filter').value || null;
    }

    let url = `/api/student/leaderboard?limit=50`;
    if (semesterId) url += `&semester_id=${semesterId}`;
    if (courseId) url += `&course_id=${courseId}`;

    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.status === 401) {
      logout();
      return;
    }

    if (!response.ok) {
      throw new Error(`Failed to load leaderboard (${response.status})`);
    }

    const data = await response.json();
    renderLeaderboard(data);
  } catch (error) {
    console.error('Error loading leaderboard:', error);
    const tbody = document.getElementById('leaderboard-tbody');
    if (tbody) {
      tbody.innerHTML = `
        <tr style="text-align: center; color: var(--text-light);">
          <td colspan="4">Error: ${error.message}</td>
        </tr>
      `;
    }
  }
}

/**
 * Render leaderboard data with modern gaming design
 */
function renderLeaderboard(data) {
  const { user_rank, user_stats, user_badges, leaderboard } = data;

  // Render user's rank card
  renderUserRankCard(user_rank, user_stats, user_badges);

  // Render leaderboard table
  if (leaderboard && leaderboard.length > 0) {
    renderLeaderboardTable(leaderboard, user_rank.position);
    const noMsg = document.getElementById('no-leaderboard-message');
    if (noMsg) noMsg.style.display = 'none';
  } else {
    const tbody = document.getElementById('leaderboard-tbody');
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; color: var(--text-light);">
            No students in leaderboard
          </td>
        </tr>
      `;
    }
    const noMsg = document.getElementById('no-leaderboard-message');
    if (noMsg) noMsg.style.display = 'block';
  }
}

/**
 * Render user's rank card with gamification
 */
function renderUserRankCard(userRank, userStats, badges) {
  try {
    const rankDisplay = userRank.position || 0;
    const totalStudents = userRank.total_students || 0;

    // Update rank medal
    const rankMedal = document.getElementById('user-rank-medal');
    if (rankMedal) {
      if (rankDisplay === 1) {
        rankMedal.textContent = '🥇';
        rankMedal.style.background =
          'linear-gradient(135deg, #ffd700 0%, #ffed4e 100%)';
        rankMedal.style.color = '#1a1a2e';
      } else if (rankDisplay === 2) {
        rankMedal.textContent = '🥈';
        rankMedal.style.background =
          'linear-gradient(135deg, #c0c0c0 0%, #e8e8e8 100%)';
        rankMedal.style.color = '#1a1a2e';
      } else if (rankDisplay === 3) {
        rankMedal.textContent = '🥉';
        rankMedal.style.background =
          'linear-gradient(135deg, #cd7f32 0%, #daa520 100%)';
        rankMedal.style.color = '#ffffff';
      } else {
        rankMedal.textContent = '🏅';
        rankMedal.style.background =
          'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        rankMedal.style.color = '#ffffff';
      }
    }

    // Set rank display
    const rankDisplayEl = document.getElementById('user-rank-display');
    if (rankDisplayEl) {
      rankDisplayEl.textContent = rankDisplay;
    }

    // Set total students
    const totalStudentsEl = document.getElementById('total-students');
    if (totalStudentsEl) {
      totalStudentsEl.textContent = totalStudents;
    }

    // Update stats with animation
    const attendancePercent = Math.round(userStats.attendance_percentage || 0);
    animateCounter('user-attendance', attendancePercent);
    animateCounter('user-current-streak', userStats.current_streak || 0);
    animateCounter('user-longest-streak', userStats.longest_streak || 0);
    animateCounter('user-classes-attended', userStats.present_count || 0);

    // Render badges
    renderBadges(badges);
  } catch (error) {
    console.error('Error in renderUserRankCard:', error);
  }
}

/**
 * Animate counter increment
 */
function animateCounter(elementId, endValue, duration = 1000) {
  const element = document.getElementById(elementId);

  if (!element) {
    console.warn(`Element ${elementId} not found for animation`);
    return;
  }

  const startValue = 0;
  const startTime = Date.now();

  function update() {
    const elapsed = Date.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const currentValue = Math.floor(
      startValue + (endValue - startValue) * progress,
    );
    element.textContent = currentValue;

    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }

  update();
}

/**
 * Render user's badges with modern design
 */
function renderBadges(badges) {
  const container = document.getElementById('user-badges');
  if (!container) {
    console.warn('user-badges element not found');
    return;
  }

  container.innerHTML = '';

  const badgeIcons = {
    FIRST_STEP: {
      icon: '🎯',
      description: 'First Step - Attended first class',
    },
    CONSISTENT: { icon: '🔥', description: 'Consistent - 7 day streak' },
    PERFECT_WEEK: { icon: '⭐', description: 'Perfect Week - 100% for 7 days' },
    IRON_STREAK: { icon: '💪', description: 'Iron Streak - 14 day streak' },
    PERFECT_MONTH: {
      icon: '👑',
      description: 'Perfect Month - 100% for 30 days',
    },
    LEADERSHIP: { icon: '🏆', description: 'Leadership - Reached Top 3' },
    COMEBACK: { icon: '🎊', description: 'Comeback - Improved attendance' },
  };

  if (badges.length === 0) {
    container.innerHTML =
      '<span style="opacity: 0.7; font-size: 0.9rem; color: white;">Keep playing to earn badges! 🎮</span>';
    return;
  }

  badges.forEach((badge, index) => {
    const badgeConfig = badgeIcons[badge.type] || {
      icon: '⭐',
      description: badge.description || 'Achievement Unlocked',
    };

    const badgeEl = document.createElement('div');
    badgeEl.className = 'leaderboard-badge';
    badgeEl.innerHTML = `
      ${badgeConfig.icon}
      <div class="leaderboard-badge-tooltip">${badge.description || badgeConfig.description}</div>
    `;
    badgeEl.style.animation = `slideUp 0.5s ease-out ${0.1 * index}s both`;
    container.appendChild(badgeEl);
  });
}

/**
 * Render leaderboard table with enhanced gamification
 */
function renderLeaderboardTable(leaderboard, userPosition) {
  const tbody = document.getElementById('leaderboard-tbody');
  if (!tbody) {
    console.warn('leaderboard-tbody element not found');
    return;
  }

  tbody.innerHTML = '';

  const badgeIcons = {
    FIRST_STEP: '🎯',
    CONSISTENT: '🔥',
    PERFECT_WEEK: '⭐',
    IRON_STREAK: '💪',
    PERFECT_MONTH: '👑',
    LEADERSHIP: '🏆',
    COMEBACK: '🎊',
  };

  leaderboard.forEach((entry, index) => {
    const row = document.createElement('tr');

    // Add highlight for current user
    if (entry.rank === userPosition) {
      row.classList.add('current-user');
    }

    // Determine rank badge style
    let rankBadgeClass = 'default';
    let rankDisplay = `#${entry.rank}`;
    if (entry.rank === 1) {
      rankBadgeClass = 'gold';
      rankDisplay = '🥇';
    } else if (entry.rank === 2) {
      rankBadgeClass = 'silver';
      rankDisplay = '🥈';
    } else if (entry.rank === 3) {
      rankBadgeClass = 'bronze';
      rankDisplay = '🥉';
    }

    // Determine streak color
    let streakClass = 'low';
    if (entry.current_streak >= 15) streakClass = 'high';
    else if (entry.current_streak >= 7) streakClass = 'medium';

    // Determine attendance color class
    let attendanceClass = 'low';
    const attendance = entry.attendance_percentage;
    if (attendance >= 85) attendanceClass = 'high';
    else if (attendance >= 70) attendanceClass = 'medium';

    // Build badges HTML
    let badgesHtml = '';
    if (entry.badges && entry.badges.length > 0) {
      badgesHtml = entry.badges
        .map((b) => {
          const icon = badgeIcons[b.type] || '⭐';
          const description = b.description || 'Achievement';
          return `
          <div class="leaderboard-badge" title="${description}">
            ${icon}
            <div class="leaderboard-badge-tooltip">${description}</div>
          </div>
        `;
        })
        .join('');
    }

    row.innerHTML = `
      <td>
        <div class="leaderboard-rank-badge ${rankBadgeClass}">${rankDisplay}</div>
      </td>
      <td>
        <div class="leaderboard-student-info">
          <span class="leaderboard-student-name">${entry.student_name}</span>
          <div class="leaderboard-student-badges">${badgesHtml}</div>
        </div>
      </td>
      <td>
        <div class="leaderboard-attendance-value ${attendanceClass}">
          ${Math.round(entry.attendance_percentage)}%
        </div>
      </td>
      <td>
        <div class="leaderboard-streak-value ${streakClass}">
          🔥 ${entry.current_streak}
        </div>
      </td>
    `;

    // Add stagger animation
    row.style.animation = `slideUp 0.4s ease-out ${0.05 * index}s both`;

    tbody.appendChild(row);
  });
}

/**
 * Show leaderboard view
 */
function showLeaderboard() {
  // Hide all other views
  const views = [
    'student-dashboard-view',
    'analytics-view',
    'course-detail-view',
    'student-login-view',
  ];
  views.forEach((viewId) => {
    const view = document.getElementById(viewId);
    if (view) view.style.display = 'none';
  });

  // Show leaderboard view
  const leaderboardView = document.getElementById('leaderboard-view');
  if (leaderboardView) {
    leaderboardView.style.display = 'block';
  }

  // Load courses for filter
  loadCoursesForLeaderboardFilter();

  // Load leaderboard data
  loadLeaderboard();
}

/**
 * Load courses into leaderboard filter
 */
async function loadCoursesForLeaderboardFilter() {
  try {
    const token = localStorage.getItem('studentToken');

    if (!token) {
      console.warn('Token not found for loading courses');
      return;
    }

    const response = await fetch('/api/student/dashboard', {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throw new Error(`Failed to load courses (${response.status})`);
    }

    const data = await response.json();
    const filterEl = document.getElementById('leaderboard-course-filter');

    if (!filterEl) {
      console.warn('leaderboard-course-filter element not found');
      return;
    }

    // Clear existing options
    filterEl.innerHTML = '<option value="">All Courses</option>';

    // Add course options
    if (data.courses && Array.isArray(data.courses)) {
      data.courses.forEach((course) => {
        const option = document.createElement('option');
        option.value = course.course_id;
        option.textContent = course.course_name;
        filterEl.appendChild(option);
      });
    }

    // Remove existing event listeners by cloning
    const newFilterEl = filterEl.cloneNode(true);
    filterEl.parentNode.replaceChild(newFilterEl, filterEl);

    // Add change handler to new element
    newFilterEl.addEventListener('change', (e) => {
      const courseId = e.target.value ? parseInt(e.target.value) : null;
      console.log('Loading leaderboard for course:', courseId);
      loadLeaderboard(courseId);
    });

    console.log(
      `Loaded ${data.courses ? data.courses.length : 0} courses into leaderboard filter`,
    );
  } catch (error) {
    console.error('Error loading courses for filter:', error);
  }
}

// ============================================================
// EVENT LISTENERS - Add to your existing DOMContentLoaded
// ============================================================

// Add this to your existing DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', () => {
  // Leaderboard view button
  const viewLeaderboardBtn = document.getElementById('view-leaderboard-button');
  if (viewLeaderboardBtn) {
    viewLeaderboardBtn.addEventListener('click', () => {
      console.log('Opening leaderboard...');
      showLeaderboard();
    });
  }

  // Back from leaderboard button
  const backToLeaderboardBtn = document.getElementById('back-to-leaderboard');
  if (backToLeaderboardBtn) {
    backToLeaderboardBtn.addEventListener('click', () => {
      console.log('Closing leaderboard...');
      document.getElementById('leaderboard-view').style.display = 'none';
      document.getElementById('student-dashboard-view').style.display = 'block';
    });
  }
});
