/**
 * VERDÉ - Wishlist Module
 * Connects frontend UI to Django Wishlist API endpoints:
 * - POST /wishlist/add/
 * - POST /wishlist/remove/
 */
(function () {
  'use strict';

  function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function showToast(message, isError) {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast-message' + (isError ? ' toast-error' : '');
    toast.textContent = message;
    if (isError) {
      toast.style.backgroundColor = '#991b1b';
    }
    container.appendChild(toast);

    requestAnimationFrame(function () {
      toast.classList.add('show');
    });

    setTimeout(function () {
      toast.classList.remove('show');
      setTimeout(function () {
        toast.remove();
      }, 320);
    }, 3200);
  }

  function updateWishlistBadges(count) {
    const countNum = parseInt(count, 10);
    const safeCount = Number.isFinite(countNum) ? Math.max(0, countNum) : 0;
    document.querySelectorAll('#wishlistCountBadge, .js-wishlist-count-badge').forEach(function (badge) {
      badge.textContent = String(safeCount);
      badge.style.display = safeCount > 0 ? 'flex' : 'none';
    });
  }

  async function toggleWishlist({ productId, variantId = null, buttonEl, onCompleted }) {
    if (!productId) return;

    // Check if user is authenticated via data attribute on body
    const bodyAuth = document.body.dataset.userAuthenticated;
    if (bodyAuth === 'false' || bodyAuth === 'False') {
      showToast('Please sign in to save items to your wishlist.', true);
      setTimeout(function () {
        window.location.href = '/login-page/?next=' + encodeURIComponent(window.location.pathname);
      }, 800);
      return;
    }

    const currentlyInWishlist = buttonEl ? (buttonEl.classList.contains('active') || buttonEl.classList.contains('in-wishlist')) : false;
    const endpoint = currentlyInWishlist ? '/wishlist/remove/' : '/wishlist/add/';
    const action = currentlyInWishlist ? 'remove' : 'add';

    if (buttonEl) {
      buttonEl.disabled = true;
      buttonEl.setAttribute('aria-busy', 'true');
    }

    try {
      const csrfToken = getCsrfToken();
      const payload = {
        product_id: parseInt(productId, 10),
        variant_id: variantId ? parseInt(variantId, 10) : null,
      };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });

      // Handle redirect if Django login_required intercepted
      if (response.redirected && response.url.includes('/login')) {
        window.location.href = response.url;
        return;
      }

      const data = await response.json().catch(function () { return null; });

      if (!response.ok || !data || data.status !== 'success') {
        if (response.status === 401 || response.status === 403) {
          showToast('Please sign in to manage your wishlist.', true);
          setTimeout(function () {
            window.location.href = '/login-page/?next=' + encodeURIComponent(window.location.pathname);
          }, 800);
          return;
        }
        throw new Error(data && data.message ? data.message : 'Unable to update wishlist.');
      }

      const nowInWishlist = (action === 'add');

      if (buttonEl) {
        if (nowInWishlist) {
          buttonEl.classList.add('active', 'in-wishlist');
          buttonEl.setAttribute('aria-label', 'Remove from wishlist');
          buttonEl.setAttribute('title', 'Remove from wishlist');
          const path = buttonEl.querySelector('svg path');
          if (path) path.setAttribute('fill', 'currentColor');
        } else {
          buttonEl.classList.remove('active', 'in-wishlist');
          buttonEl.setAttribute('aria-label', 'Add to wishlist');
          buttonEl.setAttribute('title', 'Add to wishlist');
          const path = buttonEl.querySelector('svg path');
          if (path) path.setAttribute('fill', 'none');
        }
      }

      // Update badge count
      const currentBadges = document.querySelectorAll('#wishlistCountBadge, .js-wishlist-count-badge');
      let currentCount = 0;
      if (currentBadges.length > 0) {
        currentCount = parseInt(currentBadges[0].textContent, 10) || 0;
      }
      const newCount = nowInWishlist ? currentCount + 1 : Math.max(0, currentCount - 1);
      updateWishlistBadges(newCount);

      showToast(data.message || (nowInWishlist ? 'Saved to your wishlist.' : 'Removed from your wishlist.'));

      // Dispatch event
      window.dispatchEvent(new CustomEvent('verde:wishlist-updated', {
        detail: {
          productId: parseInt(productId, 10),
          variantId: variantId ? parseInt(variantId, 10) : null,
          inWishlist: nowInWishlist,
          count: newCount,
        },
      }));

      if (typeof onCompleted === 'function') {
        onCompleted({ inWishlist: nowInWishlist, count: newCount, data: data });
      }
    } catch (err) {
      showToast(err.message || 'Something went wrong. Please try again.', true);
    } finally {
      if (buttonEl) {
        buttonEl.disabled = false;
        buttonEl.removeAttribute('aria-busy');
      }
    }
  }

  // Remove directly from wishlist (e.g. from wishlist page)
  async function removeFromWishlist({ productId, variantId = null, buttonEl, onCompleted, suppressToast = false }) {
    if (!productId) return;

    if (buttonEl) {
      buttonEl.disabled = true;
      buttonEl.setAttribute('aria-busy', 'true');
    }

    try {
      const csrfToken = getCsrfToken();
      const payload = {
        product_id: parseInt(productId, 10),
        variant_id: variantId ? parseInt(variantId, 10) : null,
      };

      const response = await fetch('/wishlist/remove/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });

      if (response.redirected && response.url.includes('/login')) {
        window.location.href = response.url;
        return;
      }

      const data = await response.json().catch(function () { return null; });

      if (!response.ok || !data || data.status !== 'success') {
        throw new Error(data && data.message ? data.message : 'Unable to remove from wishlist.');
      }

      // Update badge count
      const currentBadges = document.querySelectorAll('#wishlistCountBadge, .js-wishlist-count-badge');
      let currentCount = 0;
      if (currentBadges.length > 0) {
        currentCount = parseInt(currentBadges[0].textContent, 10) || 0;
      }
      const newCount = Math.max(0, currentCount - 1);
      updateWishlistBadges(newCount);

      if (!suppressToast) {
        showToast(data.message || 'Removed from your wishlist.');
      }

      window.dispatchEvent(new CustomEvent('verde:wishlist-updated', {
        detail: {
          productId: parseInt(productId, 10),
          variantId: variantId ? parseInt(variantId, 10) : null,
          inWishlist: false,
          count: newCount,
        },
      }));

      if (typeof onCompleted === 'function') {
        onCompleted({ inWishlist: false, count: newCount, data: data });
      }
    } catch (err) {
      showToast(err.message || 'Unable to remove item.', true);
      if (buttonEl) {
        buttonEl.disabled = false;
        buttonEl.removeAttribute('aria-busy');
      }
    }
  }

  window.VERDEWishlist = {
    toggle: toggleWishlist,
    remove: removeFromWishlist,
    updateBadges: updateWishlistBadges,
    showToast: showToast,
  };
})();
