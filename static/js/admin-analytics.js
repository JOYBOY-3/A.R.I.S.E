/**
 * Admin Analytics Dashboard — Chart.js charts, data fetching, and table rendering.
 * Depends on: Chart.js 4.x, admin.js (for auth token)
 */
(function () {
    'use strict';

    // Chart instances for cleanup
    let courseTrendChart = null;
    let dailyTrendChart = null;
    let dowChart = null;
    let typeSplitChart = null;
    let courseComparisonChart = null;

    // Auth helper
    function getToken() {
        return localStorage.getItem('adminToken');
    }
    function authHeaders() {
        return { 'Authorization': 'Bearer ' + getToken(), 'Content-Type': 'application/json' };
    }

    // Status badge helper
    function statusBadge(status) {
        const map = {
            safe: '<span class="status-badge status-safe">🟢 Safe</span>',
            warning: '<span class="status-badge status-warning">🟡 Warning</span>',
            critical: '<span class="status-badge status-critical">🔴 Critical</span>'
        };
        return map[status] || status;
    }

    // Rate color helper 
    function rateColor(pct) {
        if (pct >= 75) return '#22c55e';
        if (pct >= 60) return '#eab308';
        return '#ef4444';
    }

    // Chart.js default theme
    const chartColors = {
        primary: '#6366f1',
        success: '#22c55e',
        warning: '#eab308',
        danger: '#ef4444',
        info: '#06b6d4',
        purple: '#a855f7',
        grid: 'rgba(255,255,255,0.08)',
        text: '#94a3b8'
    };

    // =========================================================
    //  OVERVIEW TAB
    // =========================================================
    async function loadOverview() {
        try {
            const res = await fetch('/api/admin/analytics/overview', { headers: authHeaders() });
            if (!res.ok) return;
            const d = await res.json();

            document.getElementById('kpi-total-students').textContent = d.total_students;
            document.getElementById('kpi-total-courses').textContent = d.total_courses;
            document.getElementById('kpi-total-sessions').textContent = d.total_sessions;
            document.getElementById('kpi-overall-rate').textContent = d.overall_attendance_rate + '%';
            document.getElementById('kpi-at-risk').textContent = d.at_risk_count;
            document.getElementById('kpi-online-sessions').textContent = d.online_sessions;
            document.getElementById('kpi-sessions-week').textContent = d.sessions_this_week;
            document.getElementById('kpi-avg-attendance').textContent = d.avg_attendance_per_session;

            // Course summary table
            const tbody = document.getElementById('course-summary-tbody');
            tbody.innerHTML = '';
            d.course_summary.forEach(c => {
                const row = document.createElement('tr');
                row.innerHTML = `
          <td>${c.course_code}</td>
          <td>${c.course_name}</td>
          <td>${c.teacher_name || '-'}</td>
          <td>${c.enrolled_count}</td>
          <td>${c.session_count}</td>
          <td><span style="color:${rateColor(c.attendance_rate)};font-weight:600">${c.attendance_rate}%</span></td>
        `;
                tbody.appendChild(row);
            });
        } catch (e) {
            console.error('Overview load error:', e);
        }
    }

    // =========================================================
    //  COURSE ANALYTICS TAB
    // =========================================================
    let courseStudentsData = [];

    async function populateCourseSelect() {
        try {
            const res = await fetch('/api/admin/courses-view', { headers: authHeaders() });
            if (!res.ok) return;
            const courses = await res.json();
            const sel = document.getElementById('analytics-course-select');
            sel.innerHTML = '<option value="">-- Select a Course --</option>';
            courses.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.textContent = `${c.course_code} — ${c.course_name}`;
                sel.appendChild(opt);
            });
        } catch (e) {
            console.error('Course select error:', e);
        }
    }

    async function loadCourseAnalytics(courseId) {
        if (!courseId) {
            document.getElementById('course-analytics-content').style.display = 'none';
            return;
        }
        try {
            const res = await fetch(`/api/admin/analytics/course/${courseId}`, { headers: authHeaders() });
            if (!res.ok) return;
            const d = await res.json();

            document.getElementById('course-analytics-content').style.display = '';
            document.getElementById('ca-course-name').textContent = `${d.course.course_code} — ${d.course.course_name}`;
            document.getElementById('ca-teacher').textContent = `👤 ${d.course.teacher_name || 'N/A'}`;
            document.getElementById('ca-semester').textContent = `📅 ${d.course.semester_name || 'N/A'}`;
            document.getElementById('ca-enrolled').textContent = d.enrolled_count;
            document.getElementById('ca-sessions').textContent = d.total_sessions;
            document.getElementById('ca-at-risk').textContent = d.at_risk_count;

            // Students table
            courseStudentsData = d.students;
            renderCourseStudents();

            // Trend chart
            renderCourseTrendChart(d.trend);
        } catch (e) {
            console.error('Course analytics error:', e);
        }
    }

    function renderCourseStudents() {
        const tbody = document.getElementById('ca-students-tbody');
        const search = (document.getElementById('ca-student-search').value || '').toLowerCase();
        tbody.innerHTML = '';
        courseStudentsData
            .filter(s => s.student_name.toLowerCase().includes(search) ||
                s.university_roll_no.toLowerCase().includes(search) ||
                s.class_roll_id.toString().includes(search))
            .forEach(s => {
                const row = document.createElement('tr');
                row.innerHTML = `
          <td>${s.class_roll_id}</td>
          <td>${s.student_name}</td>
          <td>${s.university_roll_no}</td>
          <td>${s.present_count}</td>
          <td>${s.total_sessions}</td>
          <td style="color:${rateColor(s.percentage)};font-weight:600">${s.percentage}%</td>
          <td>${statusBadge(s.status)}</td>
        `;
                tbody.appendChild(row);
            });
    }

    function renderCourseTrendChart(trend) {
        const ctx = document.getElementById('course-trend-chart');
        if (courseTrendChart) courseTrendChart.destroy();

        const labels = trend.map(t => {
            const d = new Date(t.start_time);
            return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
        });
        const presentData = trend.map(t => t.present_count);
        const totalData = trend.map(t => t.total_students);

        courseTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Present',
                        data: presentData,
                        borderColor: chartColors.success,
                        backgroundColor: 'rgba(34,197,94,0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Enrolled',
                        data: totalData,
                        borderColor: chartColors.info,
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: chartColors.text } } },
                scales: {
                    x: { ticks: { color: chartColors.text }, grid: { color: chartColors.grid } },
                    y: { beginAtZero: true, ticks: { color: chartColors.text }, grid: { color: chartColors.grid } }
                }
            }
        });
    }

    // =========================================================
    //  STUDENT LOOKUP TAB
    // =========================================================
    async function populateStudentSelect() {
        try {
            const res = await fetch('/api/admin/students', { headers: authHeaders() });
            if (!res.ok) return;
            const students = await res.json();
            const sel = document.getElementById('student-lookup-select');
            sel.innerHTML = '<option value="">-- Select a Student --</option>';
            students.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = `${s.university_roll_no} — ${s.student_name}`;
                sel.appendChild(opt);
            });
        } catch (e) {
            console.error('Student select error:', e);
        }
    }

    async function loadStudentAnalytics(studentId) {
        if (!studentId) {
            document.getElementById('student-analytics-content').style.display = 'none';
            return;
        }
        try {
            const res = await fetch(`/api/admin/analytics/student/${studentId}`, { headers: authHeaders() });
            if (!res.ok) return;
            const d = await res.json();

            document.getElementById('student-analytics-content').style.display = '';
            document.getElementById('sa-student-name').textContent = d.student.student_name;
            document.getElementById('sa-student-roll').textContent =
                `${d.student.university_roll_no} • ${d.student.enrollment_no}`;

            const badge = document.getElementById('sa-overall-badge');
            badge.textContent = d.overall_percentage + '%';
            badge.className = 'sa-overall-badge sa-badge-' + d.overall_status;

            // Courses table
            const ctbody = document.getElementById('sa-courses-tbody');
            ctbody.innerHTML = '';
            d.courses.forEach(c => {
                const row = document.createElement('tr');
                row.innerHTML = `
          <td>${c.course_code}</td>
          <td>${c.course_name}</td>
          <td>${c.class_roll_id}</td>
          <td>${c.present_count}</td>
          <td>${c.total_sessions}</td>
          <td style="color:${rateColor(c.percentage)};font-weight:600">${c.percentage}%</td>
          <td>${statusBadge(c.status)}</td>
        `;
                ctbody.appendChild(row);
            });

            // Absences table
            const atbody = document.getElementById('sa-absences-tbody');
            atbody.innerHTML = '';
            d.recent_absences.forEach(a => {
                const row = document.createElement('tr');
                const dt = new Date(a.start_time);
                row.innerHTML = `
          <td>${dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
          <td>${a.course_code} — ${a.course_name}</td>
        `;
                atbody.appendChild(row);
            });
        } catch (e) {
            console.error('Student analytics error:', e);
        }
    }

    // =========================================================
    //  TRENDS TAB
    // =========================================================
    async function loadTrends() {
        try {
            const res = await fetch('/api/admin/analytics/trends', { headers: authHeaders() });
            if (!res.ok) return;
            const d = await res.json();

            renderDailyTrendChart(d.daily);
            renderDowChart(d.day_of_week);
            renderTypeSplitChart(d.session_type_split);
            renderCourseComparisonChart(d.course_sessions);
        } catch (e) {
            console.error('Trends load error:', e);
        }
    }

    function renderDailyTrendChart(daily) {
        const ctx = document.getElementById('daily-trend-chart');
        if (dailyTrendChart) dailyTrendChart.destroy();

        dailyTrendChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: daily.map(d => {
                    const dt = new Date(d.date);
                    return dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
                }),
                datasets: [{
                    label: 'Attendance Count',
                    data: daily.map(d => d.attendance_count),
                    backgroundColor: 'rgba(99,102,241,0.6)',
                    borderColor: chartColors.primary,
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: chartColors.text } } },
                scales: {
                    x: { ticks: { color: chartColors.text, maxRotation: 45 }, grid: { color: chartColors.grid } },
                    y: { beginAtZero: true, ticks: { color: chartColors.text }, grid: { color: chartColors.grid } }
                }
            }
        });
    }

    function renderDowChart(dow) {
        const ctx = document.getElementById('dow-chart');
        if (dowChart) dowChart.destroy();

        const colors = dow.map(d => {
            const avg = d.avg_attendance || 0;
            if (avg >= 6) return chartColors.success;
            if (avg >= 3) return chartColors.warning;
            return chartColors.danger;
        });

        dowChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: dow.map(d => d.day_name),
                datasets: [{
                    label: 'Avg Attendance',
                    data: dow.map(d => Math.round(d.avg_attendance || 0)),
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: chartColors.text } } },
                scales: {
                    x: { ticks: { color: chartColors.text }, grid: { color: chartColors.grid } },
                    y: { beginAtZero: true, ticks: { color: chartColors.text }, grid: { color: chartColors.grid } }
                }
            }
        });
    }

    function renderTypeSplitChart(split) {
        const ctx = document.getElementById('type-split-chart');
        if (typeSplitChart) typeSplitChart.destroy();

        const labels = split.map(s => s.session_type === 'online' ? 'Online' : 'Offline');
        const data = split.map(s => s.session_count);

        typeSplitChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: [chartColors.info, chartColors.purple],
                    borderColor: 'transparent',
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                cutout: '60%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: chartColors.text, padding: 16 } }
                }
            }
        });
    }

    function renderCourseComparisonChart(courses) {
        const ctx = document.getElementById('course-comparison-chart');
        if (courseComparisonChart) courseComparisonChart.destroy();

        const rates = courses.map(c => {
            const possible = c.enrolled * c.session_count;
            return possible > 0 ? Math.round((c.total_marks / possible) * 100) : 0;
        });

        courseComparisonChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: courses.map(c => c.course_code),
                datasets: [
                    {
                        label: 'Sessions',
                        data: courses.map(c => c.session_count),
                        backgroundColor: 'rgba(99,102,241,0.5)',
                        borderRadius: 4
                    },
                    {
                        label: 'Attendance %',
                        data: rates,
                        backgroundColor: rates.map(r => r >= 75 ? 'rgba(34,197,94,0.6)' : r >= 60 ? 'rgba(234,179,8,0.6)' : 'rgba(239,68,68,0.6)'),
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: chartColors.text } } },
                scales: {
                    x: { ticks: { color: chartColors.text }, grid: { color: chartColors.grid } },
                    y: { beginAtZero: true, ticks: { color: chartColors.text }, grid: { color: chartColors.grid } }
                }
            }
        });
    }

    // =========================================================
    //  EVENT LISTENERS
    // =========================================================
    document.addEventListener('DOMContentLoaded', () => {
        // Tab change detection — load analytics when analytics tab is clicked
        document.querySelectorAll('.tab-button[data-tab="analytics"]').forEach(btn => {
            btn.addEventListener('click', () => {
                loadOverview();
                populateCourseSelect();
                populateStudentSelect();
            });
        });

        // Analytics sub-tab: load trends when clicked
        document.querySelectorAll('.sub-tab-button[data-subtab="analytics-trends"]').forEach(btn => {
            btn.addEventListener('click', () => loadTrends());
        });

        // Course analytics course select change
        const courseSelect = document.getElementById('analytics-course-select');
        if (courseSelect) {
            courseSelect.addEventListener('change', () => loadCourseAnalytics(courseSelect.value));
        }

        // Student search filter
        const studentSearch = document.getElementById('ca-student-search');
        if (studentSearch) {
            studentSearch.addEventListener('input', () => renderCourseStudents());
        }

        // Student analytics student select change
        const studentSelect = document.getElementById('student-lookup-select');
        if (studentSelect) {
            studentSelect.addEventListener('change', () => loadStudentAnalytics(studentSelect.value));
        }
    });

})();
