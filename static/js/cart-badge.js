(function () {
  function getCartApiUrl() {
    const cartLink = document.querySelector('[data-cart-api]');
    return cartLink ? cartLink.dataset.cartApi : null;
  }

  function updateCartBadges(totalItems) {
    document.querySelectorAll('.js-cart-count-badge').forEach(function (badge) {
      badge.textContent = String(totalItems);
      badge.style.display = totalItems > 0 ? 'flex' : 'none';
    });
  }

  function refreshCartCount() {
    const cartApiUrl = getCartApiUrl();
    if (!cartApiUrl) return Promise.resolve();

    return fetch(cartApiUrl, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || data.status !== 'success') {
            throw new Error(data.message || 'Unable to load cart count.');
          }
          const totalItems = Number.parseInt(data.total_items, 10);
          updateCartBadges(Number.isFinite(totalItems) ? Math.max(0, totalItems) : 0);
        });
      })
      .catch(function (error) {
        console.error('Unable to refresh cart count:', error);
      });
  }

  window.VERDECartBadge = { refresh: refreshCartCount };
  window.addEventListener('verde:cart-updated', refreshCartCount);
  document.addEventListener('DOMContentLoaded', refreshCartCount);
})();
