document.addEventListener('DOMContentLoaded', () => {
  const views = {
    login: document.getElementById('student-login-view'),
    dashboard: document.getElementById('student-dashboard-view'),
    courseDetail: document.getElementById('course-detail-view'),
    analytics: document.getElementById('analytics-view'),
  };

  let token = localStorage.getItem('studentToken');
  let currentCourseId = null;
  let currentSemesterId = null;  // Track selected semester filter
  let chartInstances = {};  // Store Chart.js instances for cleanup

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
      document.getElementById(
        'welcome-message'
      ).textContent = `Welcome, ${data.student_name}!`;

      document.getElementById(
        'overall-percentage'
      ).textContent = `${data.overall_percentage}%`;

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
        coursesContainer.innerHTML = '<p style="color: var(--text-light); text-align: center;">No courses found for selected semester.</p>';
      } else {
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
      }

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

  // Load analytics
  async function loadAnalytics() {
    try {
      const analyticsUrl = currentSemesterId
        ? `/api/student/analytics?semester_id=${currentSemesterId}`
        : '/api/student/analytics';

      const response = await fetch(analyticsUrl, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.status === 401) {
        logout();
        return;
      }

      if (!response.ok) {
        document.getElementById('no-analytics-message').style.display = 'block';
        document.getElementById('analytics-container').innerHTML = '';
        showView('analytics');
        return;
      }

      const data = await response.json();
      const analyticsContainer = document.getElementById('analytics-container');
      const noAnalyticsMsg = document.getElementById('no-analytics-message');

      if (!data.analytics || Object.keys(data.analytics).length === 0) {
        noAnalyticsMsg.style.display = 'block';
        analyticsContainer.innerHTML = '';
        showView('analytics');
        return;
      }

      noAnalyticsMsg.style.display = 'none';
      analyticsContainer.innerHTML = '';

      // Destroy previous chart instances
      Object.values(chartInstances).forEach(chart => {
        if (chart) chart.destroy();
      });
      chartInstances = {};

      // Create analytics cards for each course
      Object.keys(data.analytics).forEach((courseId) => {
        const analytics = data.analytics[courseId];
        const minReq = data.min_attendance_requirement;

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

        const trendEmoji = analytics.trend_direction === 'up' ? '📈' : analytics.trend_direction === 'down' ? '📉' : '➡️';

        const card = document.createElement('div');
        card.className = 'stat-card';
        card.style.borderLeft = `4px solid ${statusColor}`;
        card.style.backgroundColor = statusBgColor;

        const chartCanvasId = `chart-${courseId}`;

        card.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">
              <h3 style="margin-top: 0; color: var(--text-primary);">${analytics.course_name}</h3>
              <p style="margin: 0.5rem 0; font-size: 0.95rem;">
                <strong>Status:</strong> ${statusEmoji} ${analytics.status.toUpperCase()}
              </p>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0;">
            <div>
              <p style="margin: 0.25rem 0; font-size: 0.85rem; color: var(--text-secondary);">Last 7 Days</p>
              <p style="margin: 0; font-size: 1.5rem; font-weight: bold; color: ${statusColor};">${analytics.last_7_days_avg.toFixed(1)}%</p>
            </div>
            <div>
              <p style="margin: 0.25rem 0; font-size: 0.85rem; color: var(--text-secondary);">Last 30 Days</p>
              <p style="margin: 0; font-size: 1.5rem; font-weight: bold; color: #6c757d;">${analytics.last_30_days_avg.toFixed(1)}%</p>
            </div>
            <div>
              <p style="margin: 0.25rem 0; font-size: 0.85rem; color: var(--text-secondary);">Semester Total</p>
              <p style="margin: 0; font-size: 1.5rem; font-weight: bold; color: #0066cc;">${analytics.semester_total.toFixed(1)}%</p>
            </div>
            <div>
              <p style="margin: 0.25rem 0; font-size: 0.85rem; color: var(--text-secondary);">Trend</p>
              <p style="margin: 0; font-size: 1.2rem; font-weight: bold;">${trendEmoji}</p>
            </div>
          </div>

          <p style="margin: 0.5rem 0; padding: 0.5rem; background-color: rgba(0,0,0,0.05); border-radius: 4px; font-size: 0.9rem;">
            Institute Requirement: <strong>${minReq}%</strong> | Your Progress: <strong style="color: ${statusColor};">${analytics.last_7_days_avg.toFixed(1)}%</strong>
          </p>

          <h4 style="margin: 1rem 0 0.5rem 0; color: var(--text-secondary);">7-Day Trend</h4>
          <canvas id="${chartCanvasId}" style="max-height: 200px; margin-bottom: 1rem;"></canvas>

          <p style="margin: 0; font-size: 0.85rem; color: var(--text-secondary);">
            Total Sessions: ${analytics.total_sessions}
          </p>
        `;

        analyticsContainer.appendChild(card);

        // Create chart
        const ctx = document.getElementById(chartCanvasId).getContext('2d');
        const dailyData = analytics.daily_breakdown.map(d => d.percentage !== null ? d.percentage : 0);
        const dailyLabels = analytics.daily_breakdown.map(d => {
          const date = new Date(d.date);
          return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });

        chartInstances[chartCanvasId] = new Chart(ctx, {
          type: 'line',
          data: {
            labels: dailyLabels,
            datasets: [{
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
            }, {
              label: `Minimum (${minReq}%)`,
              data: Array(dailyLabels.length).fill(minReq),
              borderColor: '#dc3545',
              borderDash: [5, 5],
              borderWidth: 1,
              fill: false,
              pointRadius: 0,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
              legend: {
                display: true,
                position: 'bottom',
                labels: { usePointStyle: true }
              }
            },
            scales: {
              y: {
                min: 0,
                max: 100,
                ticks: { suffix: '%' }
              }
            }
          }
        });
      });

      showView('analytics');
    } catch (error) {
      console.error('Analytics error:', error);
    }
  }

  // Back to dashboard
  document.getElementById('back-to-dashboard').addEventListener('click', () => {
    loadDashboard();
  });

  // View analytics button
  document.getElementById('view-analytics-button').addEventListener('click', () => {
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
  document.getElementById('clear-filter-button').addEventListener('click', () => {
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
        headers: { 'Authorization': `Bearer ${token}` },
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
  window.showCriticalAlerts = function() {
    const panel = document.getElementById('critical-alerts-panel');
    const alertsContent = document.getElementById('alerts-content');

    const criticalAlerts = window.currentCriticalAlerts || [];
    const warningAlerts = window.currentWarningAlerts || [];

    if (criticalAlerts.length === 0 && warningAlerts.length === 0) {
      alertsContent.innerHTML = '<div class="no-alerts-message"><p>✅ No attendance alerts! Your attendance is in good standing.</p></div>';
    } else {
      let html = '';

      // Critical Alerts Section (< 60%)
      if (criticalAlerts.length > 0) {
        html += '<div class="alerts-section">';
        html += '<div class="section-title">🚨 CRITICAL - Immediate Action Required</div>';
        criticalAlerts.forEach(alert => {
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
        html += '<div class="section-title">⚠️ WARNING - Improvement Needed</div>';
        warningAlerts.forEach(alert => {
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
  window.closeCriticalAlerts = function() {
    const panel = document.getElementById('critical-alerts-panel');
    panel.classList.remove('open');
  };

  // Add click handler to alert icon
  document.getElementById('critical-alert-icon').addEventListener('click', () => {
    showCriticalAlerts();
  });

  // Load critical alerts on dashboard load
  const originalLoadDashboard = loadDashboard;
  loadDashboard = function() {
    originalLoadDashboard.call(this);
    loadCriticalAlerts();
  };
});






// ============================================================
// MODERN GAMING LEADERBOARD - JavaScript Functions
// Add these functions to your existing student.js file
// ============================================================

/**
 * Load leaderboard data from API
 */
async function loadLeaderboard(courseId = null) {
  try {
    const token = localStorage.getItem('studentToken');
    
    if (!token) {
      throw new Error('Authentication token not found. Please login again.');
    }

    const url = courseId 
      ? `/api/student/leaderboard?course_id=${courseId}`
      : '/api/student/leaderboard';
    
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) {
      if (response.status === 401) {
        logout();
        return;
      }
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
        rankMedal.style.background = 'linear-gradient(135deg, #ffd700 0%, #ffed4e 100%)';
        rankMedal.style.color = '#1a1a2e';
      } else if (rankDisplay === 2) {
        rankMedal.textContent = '🥈';
        rankMedal.style.background = 'linear-gradient(135deg, #c0c0c0 0%, #e8e8e8 100%)';
        rankMedal.style.color = '#1a1a2e';
      } else if (rankDisplay === 3) {
        rankMedal.textContent = '🥉';
        rankMedal.style.background = 'linear-gradient(135deg, #cd7f32 0%, #daa520 100%)';
        rankMedal.style.color = '#ffffff';
      } else {
        rankMedal.textContent = '🏅';
        rankMedal.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
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
    const currentValue = Math.floor(startValue + (endValue - startValue) * progress);
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
    'FIRST_STEP': { icon: '🎯', description: 'First Step - Attended first class' },
    'CONSISTENT': { icon: '🔥', description: 'Consistent - 7 day streak' },
    'PERFECT_WEEK': { icon: '⭐', description: 'Perfect Week - 100% for 7 days' },
    'IRON_STREAK': { icon: '💪', description: 'Iron Streak - 14 day streak' },
    'PERFECT_MONTH': { icon: '👑', description: 'Perfect Month - 100% for 30 days' },
    'LEADERSHIP': { icon: '🏆', description: 'Leadership - Reached Top 3' },
    'COMEBACK': { icon: '🎊', description: 'Comeback - Improved attendance' }
  };

  if (badges.length === 0) {
    container.innerHTML = '<span style="opacity: 0.7; font-size: 0.9rem; color: white;">Keep playing to earn badges! 🎮</span>';
    return;
  }

  badges.forEach((badge, index) => {
    const badgeConfig = badgeIcons[badge.type] || { 
      icon: '⭐', 
      description: badge.description || 'Achievement Unlocked' 
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
    'FIRST_STEP': '🎯',
    'CONSISTENT': '🔥',
    'PERFECT_WEEK': '⭐',
    'IRON_STREAK': '💪',
    'PERFECT_MONTH': '👑',
    'LEADERSHIP': '🏆',
    'COMEBACK': '🎊'
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
      badgesHtml = entry.badges.map(b => {
        const icon = badgeIcons[b.type] || '⭐';
        const description = b.description || 'Achievement';
        return `
          <div class="leaderboard-badge" title="${description}">
            ${icon}
            <div class="leaderboard-badge-tooltip">${description}</div>
          </div>
        `;
      }).join('');
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
  const views = ['student-dashboard-view', 'analytics-view', 'course-detail-view', 'student-login-view'];
  views.forEach(viewId => {
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
      headers: { 'Authorization': `Bearer ${token}` }
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
      data.courses.forEach(course => {
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
    
    console.log(`Loaded ${data.courses ? data.courses.length : 0} courses into leaderboard filter`);
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