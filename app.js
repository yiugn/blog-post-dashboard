const state = {
  posts: [],
  filtered: [],
  blogStats: [],
  statsDate: "",
  page: 1,
  perPage: 50,
};

const $ = (selector) => document.querySelector(selector);
const numberFormatter = new Intl.NumberFormat("ko-KR");
const formatNumber = (value) => numberFormatter.format(Number(value) || 0);
const formatMetric = (value) => value === null || value === undefined ? "—" : formatNumber(value);
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

function kstDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function postDate(post) {
  return post.post_date || kstDate(post.published_at) || kstDate(post.first_seen_at);
}

function dateSource(post) {
  if (post.post_date_source) return post.post_date_source;
  return post.published_at ? "published" : "first_seen";
}

function computeBlogStats() {
  const stats = new Map();
  state.posts.forEach((post) => {
    const key = `${post.platform}:${post.slug}`;
    const current = stats.get(key) || {
      key,
      name: post.blog_name,
      platform: post.platform,
      postsTotal: 0,
      postsToday: 0,
      viewsTotal: null,
      viewsToday: null,
      viewPosts: 0,
    };
    current.postsTotal += 1;
    if (postDate(post) === state.statsDate) current.postsToday += 1;
    if (post.views_total !== null && post.views_total !== undefined) {
      current.viewsTotal = (current.viewsTotal || 0) + Number(post.views_total || 0);
      current.viewsToday = (current.viewsToday || 0) + Number(post.views_today || 0);
      current.viewPosts += 1;
    }
    stats.set(key, current);
  });
  state.blogStats = [...stats.values()].sort((a, b) => b.postsTotal - a.postsTotal);
}

function applyBlogFilter(blogName, todayOnly = false) {
  $("#blog-filter").value = blogName;
  $("#day-filter").value = todayOnly ? "today" : "";
  state.page = 1;
  applyFilters();
  $(".table-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderSummary() {
  const max = Math.max(...state.blogStats.map((row) => row.postsTotal), 1);
  $("#blog-summary").innerHTML = state.blogStats.map((row) => `
    <button class="blog-row" type="button" data-blog="${escapeHtml(row.name)}" title="${escapeHtml(row.name)} 포스트만 보기">
      <span class="blog-identity">
        <strong class="blog-name">${escapeHtml(row.name)}</strong>
        <small>${escapeHtml(row.platform)}</small>
      </span>
      <span class="blog-stat"><small>전체 글</small><strong>${formatNumber(row.postsTotal)}</strong></span>
      <span class="blog-stat"><small>오늘 발행</small><strong>${formatNumber(row.postsToday)}</strong></span>
      <span class="blog-stat"><small>누적 조회</small><strong>${formatMetric(row.viewsTotal)}</strong></span>
      <span class="blog-stat live-stat"><small>오늘 조회</small><strong>${formatMetric(row.viewsToday)}</strong></span>
      <span class="bar"><i style="width:${Math.max(2, row.postsTotal / max * 100)}%"></i></span>
    </button>
  `).join("");
  document.querySelectorAll("#blog-summary .blog-row").forEach((button) => {
    button.addEventListener("click", () => applyBlogFilter(button.dataset.blog));
  });
}

function renderTodaySummary() {
  const rows = [...state.blogStats].sort((a, b) =>
    b.postsToday - a.postsToday || b.postsTotal - a.postsTotal
  );
  const totalToday = rows.reduce((sum, row) => sum + row.postsToday, 0);
  $("#today-summary-total").textContent = `오늘 ${formatNumber(totalToday)}개`;
  $("#today-summary").innerHTML = rows.map((row) => `
    <button class="today-row ${row.postsToday ? "has-posts" : ""}" type="button"
      data-blog="${escapeHtml(row.name)}" title="${escapeHtml(row.name)}의 오늘 포스트 보기">
      <span>
        <strong>${escapeHtml(row.name)}</strong>
        <small>${escapeHtml(row.platform)}</small>
      </span>
      <b>${formatNumber(row.postsToday)}</b>
    </button>
  `).join("");
  document.querySelectorAll("#today-summary .today-row").forEach((button) => {
    button.addEventListener("click", () => applyBlogFilter(button.dataset.blog, true));
  });
}

function renderBlogOptions() {
  const names = [...new Set(state.posts.map((post) => post.blog_name))]
    .sort((a, b) => a.localeCompare(b, "ko"));
  $("#blog-filter").innerHTML = '<option value="">모든 블로그</option>' +
    names.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
}

function applyFilters() {
  const query = $("#search").value.trim().toLocaleLowerCase("ko");
  const platform = $("#platform-filter").value;
  const blog = $("#blog-filter").value;
  const day = $("#day-filter").value;
  const sort = $("#sort-order").value;

  state.filtered = state.posts.filter((post) => {
    const haystack = `${post.title} ${post.blog_name}`.toLocaleLowerCase("ko");
    return (!query || haystack.includes(query)) &&
      (!platform || post.platform === platform) &&
      (!blog || post.blog_name === blog) &&
      (!day || postDate(post) === state.statsDate);
  });
  state.filtered.sort((a, b) => {
    if (sort === "title") return a.title.localeCompare(b.title, "ko");
    if (sort === "views") return Number(b.views_total ?? -1) - Number(a.views_total ?? -1);
    if (sort === "today-views") return Number(b.views_today ?? -1) - Number(a.views_today ?? -1);
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
  $("#post-body").innerHTML = rows.map((post) => {
    const source = dateSource(post);
    const approximate = source === "first_seen";
    const dateLabel = postDate(post) ? formatDate(`${postDate(post)}T00:00:00+09:00`) : "미확인";
    return `
      <tr>
        <td><span class="badge ${post.platform === "Tilnote" ? "tilnote" : ""}">${escapeHtml(post.platform)}</span></td>
        <td class="blog-cell">${escapeHtml(post.blog_name)}</td>
        <td><a class="title-link" href="${escapeHtml(post.post_url)}" target="_blank" rel="noopener">${escapeHtml(post.title)}</a></td>
        <td class="date">
          <span class="${approximate ? "estimated-date" : ""}" title="${approximate ? "원문 발행일 미제공 · 최초 수집일 기준" : "원문 발행일"}">
            ${dateLabel}${approximate ? "*" : ""}
          </span>
        </td>
        <td class="views">${formatMetric(post.views_total)}</td>
        <td class="views today-views">${formatMetric(post.views_today)}</td>
        <td class="account">${escapeHtml(post.account_masked || "—")}</td>
        <td><a class="open-link" href="${escapeHtml(post.post_url)}" target="_blank" rel="noopener" aria-label="포스트 열기">↗</a></td>
      </tr>
    `;
  }).join("");
  $("#empty-state").hidden = rows.length > 0;
  const maxPage = Math.max(1, Math.ceil(state.filtered.length / state.perPage));
  const from = state.filtered.length ? start + 1 : 0;
  const to = Math.min(start + state.perPage, state.filtered.length);
  $("#page-status").textContent =
    `${formatNumber(from)}–${formatNumber(to)} / ${formatNumber(state.filtered.length)} · ${state.page}/${maxPage} 페이지`;
  $("#prev-page").disabled = state.page <= 1;
  $("#next-page").disabled = state.page >= maxPage;
}

function renderCoverage(data) {
  const views = data.views || {};
  const supportedPosts = views.supported_posts ?? state.posts.filter((post) => post.views_total !== null && post.views_total !== undefined).length;
  const totalPosts = views.total_posts ?? state.posts.length;
  const checkedAt = views.checked_at ? formatDate(views.checked_at, true) : "아직 집계 전";
  $("#view-coverage").innerHTML =
    `<strong>조회수 집계 범위</strong> ${formatNumber(supportedPosts)} / ${formatNumber(totalPosts)}개 포스트 · ` +
    `마지막 확인 ${escapeHtml(checkedAt)}<br>` +
    `<span>Tilnote 공개 API 제공값을 매시간 갱신합니다. WikiDocs 공식 API는 날짜·조회수를 제공하지 않아 ` +
    `날짜는 최초 수집일에 *를 표시하고 조회수는 —로 구분합니다.</span>`;
}

async function loadData() {
  try {
    const response = await fetch(`data/posts.json?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.posts = data.posts || [];
    state.statsDate = data.stats_date || kstDate(new Date());
    computeBlogStats();

    const views = data.views || {};
    const totalViews = views.total ?? state.posts.reduce(
      (sum, post) => sum + Number(post.views_total || 0), 0
    );
    const todayViews = views.today ?? state.posts.reduce(
      (sum, post) => sum + Number(post.views_today || 0), 0
    );
    const todayPosts = state.blogStats.reduce((sum, row) => sum + row.postsToday, 0);

    $("#total-posts").textContent = formatNumber(state.posts.length);
    $("#today-posts").textContent = formatNumber(todayPosts);
    $("#blog-count").textContent = formatNumber(data.blog_count || state.blogStats.length);
    $("#total-views").textContent = formatNumber(totalViews);
    $("#today-views").textContent = formatNumber(todayViews);
    $("#updated-at").textContent = data.generated_at ? formatDate(data.generated_at, true) : "최초 수집 대기 중";

    const tilnoteState = data.source_state?.tilnote;
    const updateNote = document.querySelector(".updated-card small");
    if (tilnoteState && !tilnoteState.history_complete) {
      updateNote.textContent =
        `전체 이력 수집 ${formatNumber(tilnoteState.completed_count)} / ${formatNumber(tilnoteState.total_pages)} 페이지`;
    } else {
      updateNote.textContent = "매시 17분 원천 집계 · 화면은 5분마다 자동 확인";
    }
    renderBlogOptions();
    renderSummary();
    renderTodaySummary();
    renderCoverage(data);
    applyFilters();
  } catch (error) {
    $("#updated-at").textContent = "데이터를 불러오지 못했습니다";
    console.error(error);
  }
}

["search", "platform-filter", "blog-filter", "day-filter", "sort-order"].forEach((id) => {
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
