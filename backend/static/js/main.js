// main.js - Handle UI interactions for Newskoop

document.addEventListener('DOMContentLoaded', function() {
    // Handle alert dismissals
    initAlertDismissals();
    
    // Initialize dropdowns
    initDropdowns();
    
    // Add mobile menu toggle
    initMobileMenu();
  });
  
  // Handle dismissing alerts when the close button is clicked
  function initAlertDismissals() {
    const alertCloseButtons = document.querySelectorAll('.alert-close');
    alertCloseButtons.forEach(button => {
      button.addEventListener('click', function() {
        const alert = this.closest('.alert');
        alert.style.opacity = '0';
        setTimeout(() => {
          alert.style.display = 'none';
        }, 300);
      });
    });
  }
  
  // Initialize dropdown menus
  function initDropdowns() {
    const dropdownTriggers = document.querySelectorAll('.dropdown-trigger');
    
    dropdownTriggers.forEach(trigger => {
      trigger.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const dropdown = this.nextElementSibling;
        const isActive = dropdown.classList.contains('active');
        
        // Close all other dropdowns
        document.querySelectorAll('.dropdown-menu.active').forEach(menu => {
          if (menu !== dropdown) {
            menu.classList.remove('active');
          }
        });
        
        // Toggle the current dropdown
        dropdown.classList.toggle('active', !isActive);
      });
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
      const dropdowns = document.querySelectorAll('.dropdown-menu.active');
      dropdowns.forEach(dropdown => {
        if (!dropdown.contains(e.target) && !dropdown.previousElementSibling.contains(e.target)) {
          dropdown.classList.remove('active');
        }
      });
    });
  }
  
  // Add mobile menu toggle for responsive design
  function initMobileMenu() {
    // Create mobile menu toggle button
    const sidebar = document.querySelector('.sidebar');
    
    if (!sidebar) return;
    
    const mobileMenuToggle = document.createElement('button');
    mobileMenuToggle.className = 'mobile-menu-toggle';
    mobileMenuToggle.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 12h18M3 6h18M3 18h18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    `;
    
    const topNav = document.querySelector('.top-nav');
    if (topNav) {
      topNav.insertBefore(mobileMenuToggle, topNav.firstChild);
    }
    
    // Toggle sidebar visibility on mobile
    mobileMenuToggle.addEventListener('click', function() {
      sidebar.classList.toggle('show-mobile');
      this.classList.toggle('active');
    });
    
    // Close sidebar when clicking a link on mobile
    const sidebarLinks = sidebar.querySelectorAll('a');
    sidebarLinks.forEach(link => {
      link.addEventListener('click', function() {
        if (window.innerWidth <= 768) {
          sidebar.classList.remove('show-mobile');
          mobileMenuToggle.classList.remove('active');
        }
      });
    });
    
    // Add CSS for mobile toggle
    const style = document.createElement('style');
    style.textContent = `
      .mobile-menu-toggle {
        display: none;
        background: none;
        border: none;
        cursor: pointer;
        padding: 8px;
      }
      
      @media (max-width: 768px) {
        .mobile-menu-toggle {
          display: block;
        }
        
        .sidebar {
          display: none;
        }
        
        .sidebar.show-mobile {
          display: block;
        }
      }
    `;
    document.head.appendChild(style);
  }
  
  // Form validation helper
  function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
      if (!field.value.trim()) {
        isValid = false;
        
        // Add error class
        field.classList.add('is-invalid');
        
        // Create or update error message
        let errorElement = field.nextElementSibling;
        if (!errorElement || !errorElement.classList.contains('form-error')) {
          errorElement = document.createElement('div');
          errorElement.className = 'form-error';
          field.parentNode.insertBefore(errorElement, field.nextSibling);
        }
        errorElement.textContent = 'This field is required';
      } else {
        // Remove error class and message if field is valid
        field.classList.remove('is-invalid');
        
        const errorElement = field.nextElementSibling;
        if (errorElement && errorElement.classList.contains('form-error')) {
          errorElement.textContent = '';
        }
      }
    });
    
    return isValid;
  }
  
  // Modal functionality
  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      document.body.classList.add('modal-open');
    }
  }
  
  function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      document.body.classList.remove('modal-open');
    }
  }
  
  // Close modal when clicking outside of it
  document.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
      event.target.classList.remove('active');
      document.body.classList.remove('modal-open');
    }
  });
  
  // Tables - handle row selection and actions
  function initTableRowActions() {
    const tables = document.querySelectorAll('.table-selectable');
    
    tables.forEach(table => {
      const rows = table.querySelectorAll('tbody tr');
      
      rows.forEach(row => {
        row.addEventListener('click', function(e) {
          // Don't select row if clicking on buttons or links
          if (e.target.tagName === 'BUTTON' || e.target.tagName === 'A' || 
              e.target.closest('button') || e.target.closest('a')) {
            return;
          }
          
          // Toggle selection
          this.classList.toggle('selected');
          
          // Check if any rows are selected
          const selectedRows = table.querySelectorAll('tbody tr.selected');
          const bulkActions = table.closest('.card').querySelector('.bulk-actions');
          
          if (bulkActions) {
            if (selectedRows.length > 0) {
              bulkActions.style.display = 'flex';
              // Update selected count
              const countElement = bulkActions.querySelector('.selected-count');
              if (countElement) {
                countElement.textContent = selectedRows.length;
              }
            } else {
              bulkActions.style.display = 'none';
            }
          }
        });
      });
    });
  }