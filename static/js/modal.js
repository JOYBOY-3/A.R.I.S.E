// =============================================================================
// Custom Modal System - Modern replacement for alert/prompt/confirm
// =============================================================================

const Modal = {
  // Alert modal
  alert: function (message, title = 'Notice', type = 'info') {
    return new Promise((resolve) => {
      const modal = this._createModal(title, message, type, [
        { text: 'OK', class: 'button-primary', handler: () => resolve() },
      ]);
      document.body.appendChild(modal);
      this._show(modal);
    });
  },

  // Confirm modal
  confirm: function (message, title = 'Confirm', type = 'warning') {
    return new Promise((resolve) => {
      const modal = this._createModal(title, message, type, [
        {
          text: 'Cancel',
          class: 'button-secondary',
          handler: () => resolve(false),
        },
        {
          text: 'Confirm',
          class: 'button-primary',
          handler: () => resolve(true),
        },
      ]);
      document.body.appendChild(modal);
      this._show(modal);
    });
  },

  // Prompt modal
  prompt: function (
    message,
    title = 'Input Required',
    defaultValue = '',
    type = 'info'
  ) {
    return new Promise((resolve) => {
      const inputId = 'arise-modal-input-' + Date.now();
      const messageWithInput = `
        ${message}
        <input type="text" id="${inputId}" class="arise-modal-input" 
               value="${defaultValue}" placeholder="Enter value...">
      `;

      const modal = this._createModal(title, messageWithInput, type, [
        {
          text: 'Cancel',
          class: 'button-secondary',
          handler: () => resolve(null),
        },
        {
          text: 'OK',
          class: 'button-primary',
          handler: () => {
            const input = document.getElementById(inputId);
            resolve(input ? input.value : null);
          },
        },
      ]);

      document.body.appendChild(modal);
      this._show(modal);

      // Focus input after modal appears
      setTimeout(() => {
        const input = document.getElementById(inputId);
        if (input) input.focus();
      }, 100);
    });
  },

  // Internal: Create modal structure
  _createModal: function (title, message, type, buttons) {
    const overlay = document.createElement('div');
    overlay.className = 'arise-modal-overlay';

    const icons = {
      info: 'ℹ️',
      success: '✅',
      warning: '⚠️',
      error: '❌',
    };

    overlay.innerHTML = `
      <div class="arise-modal">
        <div class="arise-modal-header">
          <span class="arise-modal-icon ${type}">${
      icons[type] || icons.info
    }</span>
          <h3 class="arise-modal-title">${title}</h3>
        </div>
        <div class="arise-modal-body">${message}</div>
        <div class="arise-modal-footer">
          ${buttons
            .map(
              (btn, idx) =>
                `<button class="${btn.class}" data-action="${idx}">${btn.text}</button>`
            )
            .join('')}
        </div>
      </div>
    `;

    // Attach button handlers
    overlay.querySelectorAll('button[data-action]').forEach((btn, idx) => {
      btn.addEventListener('click', () => {
        buttons[idx].handler();
        this._hide(overlay);
      });
    });

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        buttons[buttons.length - 1].handler();
        this._hide(overlay);
      }
    });

    return overlay;
  },

  // Show modal
  _show: function (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  },

  // Hide modal
  _hide: function (modal) {
    modal.classList.remove('active');
    setTimeout(() => {
      document.body.removeChild(modal);
      document.body.style.overflow = '';
    }, 200);
  },
};

// Global shortcuts
window.Modal = Modal;
