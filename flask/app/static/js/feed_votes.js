$(function () {
  function sendVote(url, val) {
    return $.ajax({
      url: url,
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ value: val })
    });
  }


  // LIKE
  $(document).on("mousedown", ".btnVoteLike", function (e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    const url = $(this).data("vote-url");
    if (!url) return false;

    sendVote(url, 1).done(function () {
      location.reload();
    });

    return false;
  });

  // DISLIKE
  $(document).on("mousedown", ".btnVoteDislike", function (e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    const url = $(this).data("vote-url");
    if (!url) return false;

    sendVote(url, -1).done(function () {
      location.reload();
    });

    return false;
  });

  // TAG CLICK (search redirect)
  $(document).on("click", "a.badge[data-feed-tag]", function (e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    window.location = this.href;
    return false;
  });

  $(document).on("click", ".feed-card", function (e) {
    if ($(e.target).closest("a, button, video, input, textarea, select, label").length) return;
    const href = $(this).data("href");
    if (href) window.location = href;
  });

  $(document).on("keydown", ".feed-card", function (e) {
    if (e.key !== "Enter") return;
    const href = $(this).data("href");
    if (href) window.location = href;
  });
});
