/* ==========================================================================
   EcoSort AI - Main JavaScript
   Navigation toggle and shared utilities
   ========================================================================== */

// Mobile navigation toggle
function toggleNav() {
    const navLinks = document.getElementById('navLinks');
    if (navLinks) {
        navLinks.classList.toggle('show');
    }
}

// Close mobile nav when clicking a link
document.addEventListener('DOMContentLoaded', () => {
    const links = document.querySelectorAll('.nav-links a');
    links.forEach(link => {
        link.addEventListener('click', () => {
            const navLinks = document.getElementById('navLinks');
            if (navLinks) {
                navLinks.classList.remove('show');
            }
        });
    });
});

// Format date for display
function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('th-TH', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

// Format number with thousands separator
function formatNum(n) {
    return Number(n).toLocaleString('en-US');
}
