/**
 * VERDÉ — Botanical Lifestyle UI Controller
 * Modular, vanilla JavaScript without external dependencies.
 * Easy hooks for backend integration.
 */

document.addEventListener('DOMContentLoaded', () => {
  // State
  const state = {
    cart: [...(window.VerdeData?.initialCart || [])],
    wishlistCount: 3,
    isWishlisted: false,
  };

  // DOM Elements
  const header = document.querySelector('.site-header');
  const cartDrawer = document.getElementById('cartDrawer');
  const cartBackdrop = document.getElementById('cartBackdrop');
  const cartBtn = document.getElementById('cartBtn');
  const cartCloseBtn = document.getElementById('cartCloseBtn');
  const cartCountBadge = document.getElementById('cartCountBadge');
  const cartItemsList = document.getElementById('cartItemsList');
  const cartSubtotalEl = document.getElementById('cartSubtotal');
  
  const authModal = document.getElementById('authModal');
  const modalBackdrop = document.getElementById('modalBackdrop');
  const signinBtn = document.getElementById('signinBtn');
  const authCloseBtn = document.getElementById('authCloseBtn');
  const authTabs = document.querySelectorAll('.auth-tab');
  const authForm = document.getElementById('authForm');
  const authSubmitBtn = document.getElementById('authSubmitBtn');

  const searchModal = document.getElementById('searchModal');
  const searchBtn = document.getElementById('searchBtn');
  const searchCloseBtn = document.getElementById('searchCloseBtn');
  const searchInput = document.getElementById('searchInput');
  const suggChips = document.querySelectorAll('.sugg-chip');

  const wishlistBtn = document.getElementById('wishlistBtn');
  const wishlistBadge = document.getElementById('wishlistCountBadge');

  const mobileMenuToggle = document.getElementById('mobileMenuToggle');
  const mobileNavDrawer = document.getElementById('mobileNavDrawer');
  const mobileNavCloseBtn = document.getElementById('mobileNavCloseBtn');

  const categoryCards = document.querySelectorAll('.collection-card');
  const toastContainer = document.getElementById('toastContainer');

  // --- Scroll State for Header ---
  window.addEventListener('scroll', () => {
    if (window.scrollY > 20) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
  });

  // --- Toast Notification Helper ---
  function showToast(message) {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = 'toast-message';
    toast.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
        <polyline points="22 4 12 14.01 9 11.01"></polyline>
      </svg>
      <span>${message}</span>
    `;
    toastContainer.appendChild(toast);

    // Trigger animate in
    requestAnimationFrame(() => {
      toast.classList.add('show');
    });

    // Auto dismiss
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // --- Shopping Cart Functions ---
  function updateCartUI() {
    const totalItems = state.cart.reduce((sum, item) => sum + item.quantity, 0);
    const subtotal = state.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    // Update badges
    if (cartCountBadge) {
      cartCountBadge.textContent = totalItems;
      cartCountBadge.style.display = totalItems > 0 ? 'flex' : 'none';
    }

    if (cartSubtotalEl) {
      cartSubtotalEl.textContent = `$${subtotal.toFixed(2)}`;
    }

    // Render items
    if (cartItemsList) {
      if (state.cart.length === 0) {
        cartItemsList.innerHTML = `
          <div class="cart-empty">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="9" cy="21" r="1"></circle>
              <circle cx="20" cy="21" r="1"></circle>
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
            </svg>
            <p>Your cart is empty.</p>
          </div>
        `;
      } else {
        cartItemsList.innerHTML = state.cart.map(item => `
          <div class="cart-item" data-id="${item.id}">
            <img src="${item.image}" alt="${item.name}" class="cart-item-img">
            <div class="cart-item-details">
              <div class="cart-item-name">${item.name}</div>
              <div class="cart-item-meta">${item.category}</div>
              <div class="cart-item-footer">
                <div class="qty-control">
                  <button class="qty-btn" data-action="decrease" data-id="${item.id}" aria-label="Decrease quantity">−</button>
                  <span class="qty-val">${item.quantity}</span>
                  <button class="qty-btn" data-action="increase" data-id="${item.id}" aria-label="Increase quantity">+</button>
                </div>
                <div class="cart-item-price">$${(item.price * item.quantity).toFixed(2)}</div>
                <button class="cart-item-remove" data-action="remove" data-id="${item.id}" aria-label="Remove item">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        `).join('');
      }
    }
  }

  function openCart() {
    cartDrawer?.classList.add('open');
    cartBackdrop?.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeCart() {
    cartDrawer?.classList.remove('open');
    cartBackdrop?.classList.remove('active');
    document.body.style.overflow = '';
  }

  cartBtn?.addEventListener('click', openCart);
  cartCloseBtn?.addEventListener('click', closeCart);
  cartBackdrop?.addEventListener('click', closeCart);

  // Delegate cart quantity buttons
  cartItemsList?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;

    const action = btn.dataset.action;
    const itemId = btn.dataset.id;
    const item = state.cart.find(i => i.id === itemId);
    if (!item) return;

    if (action === 'increase') {
      item.quantity += 1;
    } else if (action === 'decrease') {
      if (item.quantity > 1) {
        item.quantity -= 1;
      } else {
        state.cart = state.cart.filter(i => i.id !== itemId);
        showToast(`Removed "${item.name}" from cart`);
      }
    } else if (action === 'remove') {
      state.cart = state.cart.filter(i => i.id !== itemId);
      showToast(`Removed "${item.name}" from cart`);
    }

    updateCartUI();
  });

  // --- Auth Modal (Sign In / Register) ---
  function openAuthModal() {
    authModal?.classList.add('open');
    modalBackdrop?.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeAuthModal() {
    authModal?.classList.remove('open');
    modalBackdrop?.classList.remove('active');
    document.body.style.overflow = '';
  }

  signinBtn?.addEventListener('click', openAuthModal);
  authCloseBtn?.addEventListener('click', closeAuthModal);
  modalBackdrop?.addEventListener('click', () => {
    closeAuthModal();
    closeSearchModal();
  });

  authTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      authTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const mode = tab.dataset.tab;
      if (authSubmitBtn) {
        authSubmitBtn.textContent = mode === 'register' ? 'Create Account' : 'Sign In';
      }
    });
  });

  const authEmailInput = document.getElementById('authEmail');
  const authPasswordInput = document.getElementById('authPassword');
  const authEmailError = document.getElementById('authEmailError');
  const authPasswordError = document.getElementById('authPasswordError');

  function clearAuthFieldErrors() {
    authEmailInput?.classList.remove('is-invalid');
    authPasswordInput?.classList.remove('is-invalid');
    if (authEmailError) authEmailError.textContent = '';
    if (authPasswordError) authPasswordError.textContent = '';
  }

  authEmailInput?.addEventListener('input', () => {
    authEmailInput.classList.remove('is-invalid');
    if (authEmailError) authEmailError.textContent = '';
  });

  authPasswordInput?.addEventListener('input', () => {
    authPasswordInput.classList.remove('is-invalid');
    if (authPasswordError) authPasswordError.textContent = '';
  });

  authForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    clearAuthFieldErrors();

    const email = authEmailInput?.value.trim();
    const password = authPasswordInput?.value;

    let hasError = false;
    if (!email) {
      authEmailInput?.classList.add('is-invalid');
      if (authEmailError) authEmailError.textContent = 'Please enter your email address.';
      hasError = true;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      authEmailInput?.classList.add('is-invalid');
      if (authEmailError) authEmailError.textContent = 'Please enter a valid email address.';
      hasError = true;
    }

    if (!password) {
      authPasswordInput?.classList.add('is-invalid');
      if (authPasswordError) authPasswordError.textContent = 'Please enter your password.';
      hasError = true;
    }

    if (hasError) return;

    showToast(`Welcome back to VERDÉ, ${email.split('@')[0]}!`);
    closeAuthModal();
  });

  // --- Search Overlay Modal ---
  function openSearchModal() {
    searchModal?.classList.add('open');
    modalBackdrop?.classList.add('active');
    searchInput?.focus();
    document.body.style.overflow = 'hidden';
  }

  function closeSearchModal() {
    searchModal?.classList.remove('open');
    modalBackdrop?.classList.remove('active');
    document.body.style.overflow = '';
  }

  searchBtn?.addEventListener('click', openSearchModal);
  searchCloseBtn?.addEventListener('click', closeSearchModal);

  suggChips.forEach(chip => {
    chip.addEventListener('click', () => {
      if (searchInput) {
        searchInput.value = chip.textContent.trim();
        showToast(`Searching for "${chip.textContent.trim()}"...`);
        closeSearchModal();
      }
    });
  });

  // --- Wishlist Interaction ---
  wishlistBtn?.addEventListener('click', () => {
    state.isWishlisted = !state.isWishlisted;
    if (state.isWishlisted) {
      state.wishlistCount += 1;
      wishlistBtn.querySelector('svg')?.setAttribute('fill', 'currentColor');
      showToast('Saved to your botanical wishlist');
    } else {
      state.wishlistCount = Math.max(0, state.wishlistCount - 1);
      wishlistBtn.querySelector('svg')?.setAttribute('fill', 'none');
      showToast('Removed from your wishlist');
    }
    if (wishlistBadge) {
      wishlistBadge.textContent = state.wishlistCount;
    }
  });

  // --- Category Card Click ---
  categoryCards.forEach(card => {
    card.addEventListener('click', () => {
      const category = card.dataset.category || card.querySelector('.card-badge')?.textContent.trim();
      showToast(`Browsing ${category}`);
      // Ready for user's router or backend page transition
      console.log('Category selected:', category);
    });
  });

  // --- Hero Button Click ---
  const heroBtn = document.querySelector('.hero-btn');
  heroBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    document.querySelector('.collections-section')?.scrollIntoView({ behavior: 'smooth' });
    showToast('Viewing curated botanical collections');
  });

  // --- Mobile Navigation Drawer ---
  mobileMenuToggle?.addEventListener('click', () => {
    mobileNavDrawer?.classList.add('open');
    modalBackdrop?.classList.add('active');
  });

  mobileNavCloseBtn?.addEventListener('click', () => {
    mobileNavDrawer?.classList.remove('open');
    modalBackdrop?.classList.remove('active');
  });

  // --- Global Keyboard Escape Key Handler ---
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeCart();
      closeAuthModal();
      closeSearchModal();
      mobileNavDrawer?.classList.remove('open');
      modalBackdrop?.classList.remove('active');
    }
  });

  // Initialize UI
  updateCartUI();
});
