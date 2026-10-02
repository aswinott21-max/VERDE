(function () {
  'use strict';

  var storageKey = 'verde:product-stock-update';

  function renderStock(element, stock) {
    element.dataset.stock = stock;
    element.textContent = stock > 0
      ? '● In Stock (' + stock + ' available)'
      : '● Out of Stock';
    element.classList.toggle('in-stock', stock > 0);
    element.classList.toggle('out-of-stock', stock <= 0);
  }

  function applyStockUpdate(update) {
    var productId = String(update.productId);
    var variantId = update.variantId === null || update.variantId === undefined
      ? null
      : String(update.variantId);
    var delta = Number(update.delta);

    if (!productId || !Number.isFinite(delta) || delta === 0) return;

    if (variantId === null) {
      document.querySelectorAll('[data-stock-product-id]').forEach(function (element) {
        if (
          element.dataset.stockProductId !== productId ||
          element.dataset.stockVariantId
        ) return;
        var stock = Number(element.dataset.stock);
        if (!Number.isFinite(stock)) return;
        renderStock(element, Math.max(0, stock + delta));
      });
      return;
    }

    document.querySelectorAll('[data-variant-id][data-stock]').forEach(function (element) {
      if (element.dataset.variantId !== variantId) return;
      var stock = Number(element.dataset.stock);
      if (!Number.isFinite(stock)) return;
      var updatedStock = Math.max(0, stock + delta);
      element.dataset.stock = updatedStock;
      if (element.hasAttribute('data-variant-stock')) {
        element.dataset.variantStock = updatedStock;
      }
    });

    document.querySelectorAll('[data-stock-variant-id]').forEach(function (element) {
      if (
        element.dataset.stockProductId !== productId ||
        element.dataset.stockVariantId !== variantId
      ) return;
      var stock = Number(element.dataset.stock);
      if (!Number.isFinite(stock)) return;
      renderStock(element, Math.max(0, stock + delta));
    });
  }

  function update(productId, variantId, delta) {
    var updateData = {
      productId: productId,
      variantId: variantId === undefined ? null : variantId,
      delta: delta,
    };

    applyStockUpdate(updateData);

    try {
      updateData.id = Date.now() + '-' + Math.random();
      localStorage.setItem(storageKey, JSON.stringify(updateData));
    } catch (error) {
      console.warn('[Product stock] Could not synchronize stock across tabs:', error);
    }
  }

  window.addEventListener('storage', function (event) {
    if (event.key !== storageKey || !event.newValue) return;
    try {
      applyStockUpdate(JSON.parse(event.newValue));
    } catch (error) {
      console.warn('[Product stock] Could not read a stock update:', error);
    }
  });

  window.VERDEProductStock = { update: update };
})();
