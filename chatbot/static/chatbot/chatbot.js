/* ============================================================
   VERDÉ Botanical Chatbot — chatbot.js
   High-end, luxurious, modern, and minimalist concierge controller.
   ============================================================ */
(function () {
  "use strict";

  /* ── CSRF helper ─────────────────────────────────────── */
  function getCsrfToken() {
    // 1. Meta tag
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute("content")) {
      return meta.getAttribute("content");
    }

    // 2. Hidden input rendered by {% csrf_token %}
    var input = document.querySelector('[name="csrfmiddlewaretoken"]');
    if (input && input.value) {
      return input.value;
    }

    // 3. Cookie
    var cookies = document.cookie.split(";");
    for (var i = 0; i < cookies.length; i++) {
      var c = cookies[i].trim();
      if (c.startsWith("csrftoken=")) {
        return decodeURIComponent(c.substring("csrftoken=".length));
      }
    }
    return "";
  }

  /* ── State ───────────────────────────────────────────── */
  var isOpen = false;
  var isSending = false;

  /* ── DOM Elements ────────────────────────────────────── */
  var widget       = document.getElementById("verde-chatbot-widget");
  var toggle       = document.getElementById("chatbot-toggle");
  var tooltip      = document.getElementById("chatbot-tooltip");
  var window_el    = document.getElementById("chatbot-window");
  var closeBtn     = document.getElementById("chatbot-close");
  var badge        = document.getElementById("chatbot-badge");
  var scrollArea   = document.getElementById("chatbot-messages");
  var dynamicThread= document.getElementById("chatbot-dynamic-messages");
  var suggestions  = document.getElementById("chatbot-suggestions");
  var input        = document.getElementById("chatbot-input");
  var sendBtn      = document.getElementById("chatbot-send");

  if (!toggle || !window_el || !scrollArea || !input || !sendBtn) {
    return;
  }

  /* ── Dynamic Footer Avoidance ────────────────────────── */
  var footer = document.querySelector("footer");
  if (widget && footer && "IntersectionObserver" in window) {
    var footerVisible = false;
    var updateFooterOffset = function () {
      if (!footerVisible) {
        widget.style.setProperty("--cb-footer-offset", "0px");
        return;
      }

      var viewportHeight = document.documentElement.clientHeight;
      var footerTop = footer.getBoundingClientRect().top;
      var styles = getComputedStyle(widget);
      var baseBottom = parseFloat(styles.getPropertyValue("--cb-base-bottom")) || 26;
      var isMobile = window.matchMedia("(max-width: 480px)").matches;
      var clearance = 14;
      var offset = Math.max(0, viewportHeight - footerTop + clearance - baseBottom);

      var maxOffset = Math.max(0, viewportHeight - (isMobile ? 96 : 110) - 240);
      offset = Math.min(offset, maxOffset);
      widget.style.setProperty("--cb-footer-offset", offset + "px");
    };

    var footerObserver = new IntersectionObserver(function (entries) {
      footerVisible = entries[0].isIntersecting;
      updateFooterOffset();
    });
    footerObserver.observe(footer);
    window.addEventListener("scroll", updateFooterOffset, { passive: true });
    window.addEventListener("resize", updateFooterOffset);
  }

  /* ── Refined Suggested Questions with Micro-Icons ─────── */
  var SUGGESTIONS = [
    {
      icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-9"/><path d="M12 13c0-4.5 4.5-8 9-8-1 4.5-4.5 8-9 8Z"/><path d="M12 17c0-3.5-3.5-6-7-6 .8 3.5 3.5 6 7 6Z"/></svg>',
      text: "What products do you sell?"
    },
    {
      icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>',
      text: "How do I track my order?"
    },
    {
      icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>',
      text: "What is your return policy?"
    },
    {
      icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="13" x="1" y="5" rx="2"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>',
      text: "Do you offer free shipping?"
    },
    {
      icon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
      text: "How can I contact support?"
    }
  ];

  /* ── Structured Text Formatter (No Raw Tables / Pipes) ── */
  function formatBotMessage(rawText) {
    if (!rawText) return "";

    // 1. Sanitize raw HTML tags to prevent XSS
    var text = String(rawText)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // 2. Prohibit raw markdown tables & pipes: convert into structured bullet items
    var rawLines = text.split(/\r?\n/);
    var processedLines = [];
    var isInsideTable = false;

    for (var i = 0; i < rawLines.length; i++) {
      var line = rawLines[i].trim();

      // Skip markdown table divider line: e.g. |---|---| or |:---|:---|
      if (/^\|?\s*[:\-]+(?:\s*\|\s*[:\-]+)+\s*\|?$/.test(line)) {
        isInsideTable = true;
        continue;
      }

      // Check for table rows or lines containing pipes
      if (line.indexOf("|") !== -1) {
        var cells = line
          .split("|")
          .map(function (c) { return c.trim(); })
          .filter(function (c) { return c.length > 0; });

        if (cells.length > 0) {
          // If this is the header row right before a divider, treat it as a bold sub-header
          if (!isInsideTable && i + 1 < rawLines.length && /^\|?\s*[:\-]+(?:\s*\|\s*[:\-]+)+\s*\|?$/.test(rawLines[i + 1].trim())) {
            // e.g. Category | Details
            processedLines.push("### " + cells.join(" — "));
            continue;
          }

          // Format table row into a clean, structured bullet point
          if (cells.length === 1) {
            processedLines.push("• " + cells[0]);
          } else if (cells.length === 2) {
            processedLines.push("• **" + cells[0] + ":** " + cells[1]);
          } else {
            var primary = cells[0];
            var secondary = cells.slice(1).join(" — ");
            processedLines.push("• **" + primary + ":** " + secondary);
          }
          continue;
        }
      }

      isInsideTable = false;

      // Replace any stray pipe symbol with a clean dash separator
      line = line.replace(/\s*\|\s*/g, " — ");
      processedLines.push(line);
    }

    text = processedLines.join("\n");

    // 3. Convert markdown headers: ### Heading -> <h4 class="cb-bubble-h4">
    text = text.replace(/^###\s*(.+)$/gm, '<h4 class="cb-bubble-h4">$1</h4>');
    text = text.replace(/^##\s*(.+)$/gm, '<h4 class="cb-bubble-h4">$1</h4>');
    text = text.replace(/^#\s*(.+)$/gm, '<h4 class="cb-bubble-h4">$1</h4>');

    // 4. Convert bold **text** or __text__ -> <strong>text</strong>
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // 5. Convert italic *text* -> <em>text</em>
    text = text.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');

    // 6. Group list items into structured <ul> tags with clean spacing
    var blocks = text.split(/\n\s*\n/);
    var htmlBlocks = [];

    blocks.forEach(function (block) {
      var bLines = block.split(/\n/);
      var listItems = [];
      var nonListLines = [];

      for (var j = 0; j < bLines.length; j++) {
        var l = bLines[j].trim();
        if (/^[•\-\*]\s+(.+)/.test(l)) {
          var match = l.match(/^[•\-\*]\s+(.+)/);
          if (nonListLines.length > 0) {
            htmlBlocks.push('<p class="cb-bubble-p">' + nonListLines.join("<br>") + '</p>');
            nonListLines = [];
          }
          listItems.push('<li>' + match[1] + '</li>');
        } else if (/^\d+\.\s+(.+)/.test(l)) {
          var numMatch = l.match(/^\d+\.\s+(.+)/);
          if (nonListLines.length > 0) {
            htmlBlocks.push('<p class="cb-bubble-p">' + nonListLines.join("<br>") + '</p>');
            nonListLines = [];
          }
          listItems.push('<li>' + numMatch[1] + '</li>');
        } else if (l.length > 0) {
          if (listItems.length > 0) {
            htmlBlocks.push('<ul class="cb-bubble-list">' + listItems.join("") + '</ul>');
            listItems = [];
          }
          nonListLines.push(l);
        }
      }

      if (listItems.length > 0) {
        htmlBlocks.push('<ul class="cb-bubble-list">' + listItems.join("") + '</ul>');
      }
      if (nonListLines.length > 0) {
        htmlBlocks.push('<p class="cb-bubble-p">' + nonListLines.join("<br>") + '</p>');
      }
    });

    return htmlBlocks.join("");
  }

  /* ── Scroll Helper ───────────────────────────────────── */
  function scrollToBottom() {
    var previousBehavior = scrollArea.style.scrollBehavior;
    scrollArea.style.scrollBehavior = "auto";
    scrollArea.scrollTop = scrollArea.scrollHeight;
    scrollArea.style.scrollBehavior = previousBehavior;
  }

  /* ── Window Toggle ───────────────────────────────────── */
  function setToggleOpen(open) {
    isOpen = open;
    if (open) {
      toggle.classList.add("cb-open");
      window_el.classList.add("cb-open");
      toggle.setAttribute("aria-expanded", "true");
      if (tooltip) tooltip.classList.add("cb-hidden");
      if (badge) badge.classList.remove("cb-visible");
      setTimeout(function () {
        input.focus();
        scrollToBottom();
      }, 120);
    } else {
      toggle.classList.remove("cb-open");
      window_el.classList.remove("cb-open");
      toggle.setAttribute("aria-expanded", "false");
      if (tooltip) tooltip.classList.remove("cb-hidden");
    }
  }

  /* ── Append Message ──────────────────────────────────── */
  function appendMessage(role, text) {
    // role: "bot" | "user" | "error"
    var container = dynamicThread || scrollArea;
    var wrapper = document.createElement("div");

    if (role === "error") {
      wrapper.className = "cb-error-bubble";
      wrapper.textContent = text;
      container.appendChild(wrapper);
      scrollToBottom();
      return;
    }

    wrapper.className = "cb-msg cb-msg-" + role;

    if (role === "bot") {
      var avatarEl = document.createElement("div");
      avatarEl.className = "cb-msg-avatar";
      avatarEl.innerHTML =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#A8C4B0" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M12 22v-9"/><path d="M12 13c0-4.5 4.5-8 9-8-1 4.5-4.5 8-9 8Z"/><path d="M12 17c0-3.5-3.5-6-7-6 .8 3.5 3.5 6 7 6Z"/>' +
        "</svg>";
      wrapper.appendChild(avatarEl);

      var bubble = document.createElement("div");
      bubble.className = "cb-bubble";
      bubble.innerHTML = formatBotMessage(text);
      wrapper.appendChild(bubble);
    } else {
      var userBubble = document.createElement("div");
      userBubble.className = "cb-bubble";
      userBubble.textContent = text;
      wrapper.appendChild(userBubble);
    }

    container.appendChild(wrapper);
    scrollToBottom();
  }

  /* ── Typing Indicator ────────────────────────────────── */
  function showTypingIndicator() {
    var container = dynamicThread || scrollArea;
    var indicator = document.createElement("div");
    indicator.className = "cb-typing";
    indicator.id = "cb-typing";

    var avatarEl = document.createElement("div");
    avatarEl.className = "cb-msg-avatar";
    avatarEl.innerHTML =
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#A8C4B0" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M12 22v-9"/><path d="M12 13c0-4.5 4.5-8 9-8-1 4.5-4.5 8-9 8Z"/><path d="M12 17c0-3.5-3.5-6-7-6 .8 3.5 3.5 6 7 6Z"/>' +
      "</svg>";

    var dots = document.createElement("div");
    dots.className = "cb-typing-dots";
    dots.innerHTML = "<span></span><span></span><span></span>";

    indicator.appendChild(avatarEl);
    indicator.appendChild(dots);
    container.appendChild(indicator);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    var el = document.getElementById("cb-typing");
    if (el && el.parentNode) {
      el.parentNode.removeChild(el);
    }
  }

  /* ── Input State Control ─────────────────────────────── */
  function setSending(val) {
    isSending = val;
    sendBtn.disabled = val;
    input.disabled   = val;
  }

  /* ── Render Suggested Questions ──────────────────────── */
  function renderSuggestions() {
    if (!suggestions) return;
    suggestions.innerHTML = "";

    SUGGESTIONS.forEach(function (item) {
      var chip = document.createElement("button");
      chip.className = "cb-chip";
      chip.type = "button";

      var iconSpan = document.createElement("span");
      iconSpan.className = "cb-chip-icon";
      iconSpan.innerHTML = item.icon;

      var textSpan = document.createElement("span");
      textSpan.className = "cb-chip-text";
      textSpan.textContent = item.text;

      var arrowSpan = document.createElement("span");
      arrowSpan.className = "cb-chip-arrow";
      arrowSpan.innerHTML =
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>';

      chip.appendChild(iconSpan);
      chip.appendChild(textSpan);
      chip.appendChild(arrowSpan);

      chip.addEventListener("click", function () {
        if (isSending) return;
        input.value = item.text;
        sendMessage();
      });

      suggestions.appendChild(chip);
    });
  }

  /* ── Send Message ────────────────────────────────────── */
  function sendMessage() {
    var text = input.value.trim();
    if (!text || isSending) return;

    if (suggestions) suggestions.classList.add("cb-dismissed");
    appendMessage("user", text);
    input.value = "";
    autoResizeInput();

    setSending(true);
    showTypingIndicator();

    fetch("/chatbot/chat/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ message: text }),
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () {
            return { response: null };
          }).then(function (data) {
            throw new Error(
              (data && data.response) ||
                "Something went wrong (HTTP " + res.status + ")."
            );
          });
        }
        return res.json();
      })
      .then(function (data) {
        removeTypingIndicator();
        var reply =
          (data && data.response) ||
          "I apologize, but I could not retrieve an answer at this moment. Please feel free to ask again.";
        appendMessage("bot", reply);

        if (!isOpen && badge) {
          badge.classList.add("cb-visible");
        }
      })
      .catch(function (err) {
        removeTypingIndicator();
        appendMessage("error", err.message || "Unable to connect to concierge service. Please try again.");
      })
      .finally(function () {
        setSending(false);
        scrollToBottom();
      });
  }

  /* ── Auto-resize Input ───────────────────────────────── */
  function autoResizeInput() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 72) + "px";
  }

  /* ── Event Listeners ─────────────────────────────────── */
  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    setToggleOpen(!isOpen);
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      setToggleOpen(false);
    });
  }

  if (tooltip) {
    tooltip.addEventListener("click", function (e) {
      e.stopPropagation();
      if (!isOpen) {
        setToggleOpen(true);
      }
    });
  }

  sendBtn.addEventListener("click", function () {
    sendMessage();
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  input.addEventListener("input", autoResizeInput);

  // Close when clicking outside
  document.addEventListener("click", function (e) {
    if (!isOpen) return;
    if (window_el.contains(e.target) || toggle.contains(e.target) || (tooltip && tooltip.contains(e.target))) {
      return;
    }
    setToggleOpen(false);
  });

  // Escape key closes window
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && isOpen) {
      setToggleOpen(false);
      toggle.focus();
    }
  });

  /* ── Initialization ──────────────────────────────────── */
  function init() {
    renderSuggestions();
    // Hint badge after 3 seconds if not opened
    setTimeout(function () {
      if (!isOpen && badge) {
        badge.classList.add("cb-visible");
      }
    }, 3000);
  }

  init();
})();
