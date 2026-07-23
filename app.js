const state = {
  posts: [],
  filtered: [],
  page: 1,
  perPage: 50,
};

const $ = (selector) => document.querySelector(selector);
const formatNumber = (value) => new Intl.NumberFormat("ko-KR").format(value || 0);
const escapeHtml = (value = "") =>
  String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);

function formatDate(value, withTime = false) {
  if (!value) return "미확인";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 19);
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  }).format(date);
}

function renderSummary() {
  const counts = new Map();
  state.posts.forEach((post) => {
    const key = `${post.platform}:${post.slug}`;
    const current = counts.get(key) || {
      key,
      name: post.blog_name,
      platform: post.platform,
      count: 0,
    };
    current.count += 1;
    counts.set(key, current);
  });
  const rows = [...counts.values()].sort((a, b) => b.count - a.count);
  const max = Math.max(...rows.map((row) => row.count), 1);
  $("#blog-summary").innerHTML = rows.map((row) => `
    <button class="blog-row" type="button" data-blog="${escapeHtml(row.name)}" title="${escapeHtml(row.name)} 필터링">
      <span class="blog-name">${escapeHtml(row.name)}</span>
      <span class="blog-number">${formatNumber(row.count)}</span>
      <span class="bar"><i style="width:${Math.max(2, row.count / max * 100)}%"></i></span>
    </button>
  `).join("");
  document.querySelectorAll(".blog-row").forEach((button) => {
    button.addEventListener("click", () => {
      $("#blog-filter").value = button.dataset.blog;
      state.page = 1;
      applyFilters();
      $(".table-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function renderBlogOptions() {
  const names = [...new Set(state.posts.map((post) => post.blog_name))].sort((a, b) => a.localeCompare(b, "ko"));
  $("#blog-filter").innerHTML = '<option value="">모든 블로그</option>' +
    names.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
}

function applyFilters() {
  const query = $("#search").value.trim().toLocaleLowerCase("ko");
  const platform = $("#platform-filter").value;
  const blog = $("#blog-filter").value;
  const sort = $("#sort-order").value;

  state.filtered = state.posts.filter((post) => {
    const haystack = `${post.title} ${post.blog_name}`.toLocaleLowerCase("ko");
    return (!query || haystack.includes(query)) &&
      (!platform || post.platform === platform) &&
      (!blog || post.blog_name === blog);
  });
  state.filtered.sort((a, b) => {
    if (sort === "title") return a.title.localeCompare(b.title, "ko");
    const left = a.published_at || a.first_seen_at || "";
    const right = b.published_at || b.first_seen_at || "";
    return sort === "oldest" ? left.localeCompare(right) : right.localeCompare(left);
  });

  const maxPage = Math.max(1, Math.ceil(state.filtered.length / state.perPage));
  state.page = Math.min(state.page, maxPage);
  $("#filtered-count").textContent = formatNumber(state.filtered.length);
  renderTable();
}

function renderTable() {
  const start = (state.page - 1) * state.perPage;
  const rows = state.filtered.slice(start, start + state.perPage);
  $("#post-body").innerHTML = rows.map((post) => `
    <tr>
      <td><span class="badge ${post.platform === "Tilnote" ? "tilnote" : ""}">${escapeHtml(post.platform)}</span></td>
      <td class="blog-cell">${escapeHtml(post.blog_name)}</td>
      <td><a class="title-link" href="${escapeHtml(post.post_url)}" target="_blank" rel="noopener">${escapeHtml(post.title)}</a></td>
      <td class="date">${formatDate(post.published_at)}</td>
      <td class="account">${escapeHtml(post.account_masked || "—")}</td>
      <td><a class="open-link" href="${escapeHtml(post.post_url)}" target="_blank" rel="noopener" aria-label="포스트 열기">↗</a></td>
    </tr>
  `).join("");
  $("#empty-state").hidden = rows.length > 0;
  const maxPage = Math.max(1, Math.ceil(state.filtered.length / state.perPage));
  const from = state.filtered.length ? start + 1 : 0;
  const to = Math.min(start + state.perPage, state.filtered.length);
  $("#page-status").textContent = `${formatNumber(from)}–${formatNumber(to)} / ${formatNumber(state.filtered.length)} · ${state.page}/${maxPage} 페이지`;
  $("#prev-page").disabled = state.page <= 1;
  $("#next-page").disabled = state.page >= maxPage;
}

async function loadData() {
  try {
    const response = await fetch(`data/posts.json?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.posts = data.posts || [];
    $("#total-posts").textContent = formatNumber(state.posts.length);
    $("#blog-count").textContent = formatNumber(data.blog_count || 15);
    $("#updated-at").textContent = data.generated_at ? formatDate(data.generated_at, true) : "첫 수집 대기 중";
    const tilnoteState = data.source_state?.tilnote;
    const updateNote = document.querySelector(".updated-card small");
    if (tilnoteState && !tilnoteState.history_complete) {
      updateNote.textContent = `전체 이력 수집 ${formatNumber(tilnoteState.completed_count)} / ${formatNumber(tilnoteState.total_pages)} 페이지`;
    } else {
      updateNote.textContent = "매시 17분 자동 수집 · 화면은 5분마다 확인";
    }
    const dayAgo = Date.now() - 24 * 60 * 60 * 1000;
    const recent = state.posts.filter((post) => new Date(post.first_seen_at).getTime() >= dayAgo).length;
    $("#recent-count").textContent = formatNumber(recent);
    renderBlogOptions();
    renderSummary();
    applyFilters();
  } catch (error) {
    $("#updated-at").textContent = "데이터를 불러오지 못했습니다";
    console.error(error);
  }
}

["search", "platform-filter", "blog-filter", "sort-order"].forEach((id) => {
  $(`#${id}`).addEventListener(id === "search" ? "input" : "change", () => {
    state.page = 1;
    applyFilters();
  });
});
$("#prev-page").addEventListener("click", () => {
  state.page -= 1;
  renderTable();
});
$("#next-page").addEventListener("click", () => {
  state.page += 1;
  renderTable();
});

loadData();
setInterval(loadData, 5 * 60 * 1000);
