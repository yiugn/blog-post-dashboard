import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Bot,
  ChevronLeft,
  ChevronRight,
  CircleGauge,
  CloudDownload,
  Database,
  Eye,
  FileText,
  Menu,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { BlogStat, DashboardData, Post } from "@/types";

const PER_PAGE = 50;
const PublishingChart = lazy(() => import("@/components/PublishingChart"));
const numberFormat = new Intl.NumberFormat("ko-KR");
const compactFormat = new Intl.NumberFormat("ko-KR", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const formatNumber = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : numberFormat.format(value);

const formatCompact = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : compactFormat.format(value);

function formatDate(value?: string, includeTime = false) {
  if (!value) return "확인 전";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, includeTime ? 16 : 10);
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(includeTime
      ? { hour: "2-digit", minute: "2-digit", hour12: false }
      : {}),
  }).format(date);
}

function kstDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function postDate(post: Post) {
  return (
    post.post_date ||
    kstDate(post.published_at) ||
    kstDate(post.first_seen_at)
  );
}

function selectClassName() {
  return "h-11 min-w-0 rounded-xl border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-ring";
}

function LoadingDashboard() {
  return (
    <div className="min-h-screen bg-[#f6f7f4] p-6 lg:pl-[280px] lg:pr-10">
      <div className="mx-auto max-w-[1180px] space-y-5">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-48 w-full" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-36" />
          ))}
        </div>
        <Skeleton className="h-[360px]" />
        <Skeleton className="h-[520px]" />
      </div>
    </div>
  );
}

function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const navItems = [
    { label: "대시보드", icon: CircleGauge, href: "#overview" },
    { label: "전체 포스트", icon: FileText, href: "#posts" },
    { label: "블로그 분석", icon: BarChart3, href: "#blogs" },
    { label: "실시간 조회", icon: Activity, href: "#overview" },
    { label: "수집 상태", icon: Database, href: "#coverage" },
  ];

  return (
    <>
      {open && (
        <button
          aria-label="메뉴 닫기"
          className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[240px] flex-col bg-[#0b1220] px-4 py-7 text-slate-300 transition-transform duration-300 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-3 px-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#b7f34a] text-xs font-extrabold text-[#0b1220]">
            BP
          </div>
          <div>
            <div className="font-extrabold tracking-tight text-white">
              POSTPULSE
            </div>
            <div className="text-[9px] tracking-[0.14em] text-slate-400">
              CONTENT INTELLIGENCE
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto text-slate-300 lg:hidden"
            onClick={onClose}
            aria-label="사이드바 닫기"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="mt-11 px-3 text-[10px] font-semibold tracking-wider text-slate-500">
          WORKSPACE
        </div>
        <nav className="mt-3 space-y-1">
          {navItems.map((item, index) => (
            <a
              key={item.label}
              href={item.href}
              onClick={onClose}
              className={cn(
                "flex h-11 items-center gap-3 rounded-xl px-3 text-sm transition-colors hover:bg-slate-800/70 hover:text-white",
                index === 0 && "bg-[#121e34] font-semibold text-white",
              )}
            >
              <item.icon
                className={cn(
                  "h-4 w-4",
                  index === 0 ? "text-[#b7f34a]" : "text-slate-400",
                )}
              />
              {item.label}
            </a>
          ))}
        </nav>

        <div className="mt-12 px-3 text-[10px] font-semibold tracking-wider text-slate-500">
          AUTOMATION
        </div>
        <div className="mt-3 rounded-2xl bg-[#121e34] p-4">
          <Badge variant="live">LIVE</Badge>
          <div className="mt-3 text-sm font-bold text-white">
            매시간 자동 수집
          </div>
          <div className="mt-1 text-[11px] text-slate-400">
            GitHub Actions · 매시 17분
          </div>
          <div className="mt-4 h-1 overflow-hidden rounded-full bg-slate-700">
            <div className="h-full w-[58%] rounded-full bg-[#b7f34a]" />
          </div>
        </div>

        <div className="mt-auto px-3 text-[11px] leading-6 text-slate-500">
          <div>15개 블로그 연결됨</div>
          <div className="flex items-center gap-2 text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            GitHub Actions · 정상
          </div>
        </div>
      </aside>
    </>
  );
}

function MetricCard({
  label,
  value,
  note,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  note: string;
  icon: typeof FileText;
  tone: "emerald" | "blue" | "amber" | "coral";
}) {
  const tones = {
    emerald: "bg-emerald-50 text-emerald-600",
    blue: "bg-blue-50 text-blue-600",
    amber: "bg-amber-50 text-amber-600",
    coral: "bg-[#fff0ed] text-[#ff6b57]",
  };

  return (
    <Card className="min-w-0">
      <CardContent className="p-5">
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "grid h-10 w-10 shrink-0 place-items-center rounded-xl",
              tones[tone],
            )}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-semibold text-muted-foreground">
              {label}
            </div>
            <div className="mt-3 text-3xl font-extrabold tracking-[-0.04em] text-slate-900">
              {value}
            </div>
            <div className="mt-1 truncate text-[11px] text-muted-foreground">
              {note}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("");
  const [blog, setBlog] = useState("");
  const [day, setDay] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const postSectionRef = useRef<HTMLElement>(null);

  const loadData = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      const response = await fetch(
        `${import.meta.env.BASE_URL}data/posts.json?t=${Date.now()}`,
        { cache: "no-store" },
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const nextData = (await response.json()) as DashboardData;
      setData(nextData);
      setError("");
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "데이터를 불러오지 못했습니다.",
      );
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
    const timer = window.setInterval(() => void loadData(), 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [loadData]);

  const statsDate = data?.stats_date || kstDate(new Date().toISOString());

  const blogStats = useMemo<BlogStat[]>(() => {
    const map = new Map<string, BlogStat>();
    for (const post of data?.posts || []) {
      const key = `${post.platform}:${post.slug}`;
      const current = map.get(key) || {
        key,
        platform: post.platform,
        slug: post.slug,
        blogName: post.blog_name,
        postsTotal: 0,
        postsToday: 0,
        viewsTotal: null,
        viewsToday: null,
        viewPosts: 0,
      };
      current.postsTotal += 1;
      if (postDate(post) === statsDate) current.postsToday += 1;
      if (post.views_total !== null && post.views_total !== undefined) {
        current.viewsTotal =
          (current.viewsTotal || 0) + Number(post.views_total || 0);
        current.viewsToday =
          (current.viewsToday || 0) + Number(post.views_today || 0);
        current.viewPosts += 1;
      }
      map.set(key, current);
    }
    return [...map.values()].sort(
      (left, right) => right.postsTotal - left.postsTotal,
    );
  }, [data, statsDate]);

  const todayPosts = useMemo(
    () => blogStats.reduce((sum, row) => sum + row.postsToday, 0),
    [blogStats],
  );

  const trendData = useMemo(() => {
    const dateCounts = new Map<string, number>();
    for (const post of data?.posts || []) {
      const date = postDate(post);
      if (date) dateCounts.set(date, (dateCounts.get(date) || 0) + 1);
    }
    const baseDate = new Date(`${statsDate}T00:00:00+09:00`);
    return Array.from({ length: 14 }, (_, index) => {
      const date = new Date(baseDate.getTime() - (13 - index) * 86400000);
      const key = kstDate(date.toISOString());
      return {
        date: `${date.getMonth() + 1}/${date.getDate()}`,
        posts: dateCounts.get(key) || 0,
        current: index === 13,
      };
    });
  }, [data, statsDate]);

  const blogs = useMemo(
    () =>
      [...new Set((data?.posts || []).map((post) => post.blog_name))].sort(
        (left, right) => left.localeCompare(right, "ko"),
      ),
    [data],
  );

  const filteredPosts = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ko");
    const posts = (data?.posts || []).filter((post) => {
      const haystack =
        `${post.title} ${post.blog_name}`.toLocaleLowerCase("ko");
      return (
        (!normalizedQuery || haystack.includes(normalizedQuery)) &&
        (!platform || post.platform === platform) &&
        (!blog || post.blog_name === blog) &&
        (!day || postDate(post) === statsDate)
      );
    });

    return posts.sort((left, right) => {
      if (sort === "title")
        return left.title.localeCompare(right.title, "ko");
      if (sort === "views")
        return (
          Number(right.views_total ?? -1) - Number(left.views_total ?? -1)
        );
      if (sort === "today-views")
        return (
          Number(right.views_today ?? -1) - Number(left.views_today ?? -1)
        );
      const leftDate =
        postDate(left) || left.published_at || left.first_seen_at || "";
      const rightDate =
        postDate(right) || right.published_at || right.first_seen_at || "";
      return sort === "oldest"
        ? leftDate.localeCompare(rightDate)
        : rightDate.localeCompare(leftDate);
    });
  }, [blog, data, day, platform, query, sort, statsDate]);

  const maxPage = Math.max(1, Math.ceil(filteredPosts.length / PER_PAGE));
  const safePage = Math.min(page, maxPage);
  const visiblePosts = filteredPosts.slice(
    (safePage - 1) * PER_PAGE,
    safePage * PER_PAGE,
  );

  useEffect(() => {
    setPage(1);
  }, [query, platform, blog, day, sort]);

  const selectBlog = (name: string, todayOnly = false) => {
    setBlog(name);
    setDay(todayOnly ? "today" : "");
    setPage(1);
    window.setTimeout(
      () => postSectionRef.current?.scrollIntoView({ behavior: "smooth" }),
      0,
    );
  };

  if (!data && !error) return <LoadingDashboard />;

  if (!data) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f6f7f4] p-6">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle>데이터를 불러오지 못했습니다</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => void loadData(true)}>
              <RefreshCw className="mr-2 h-4 w-4" />
              다시 시도
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalPosts = data.total_posts ?? data.posts.length;
  const totalViews =
    data.views?.total ??
    data.posts.reduce((sum, post) => sum + Number(post.views_total || 0), 0);
  const todayViews =
    data.views?.today ??
    data.posts.reduce((sum, post) => sum + Number(post.views_today || 0), 0);
  const supportedPosts =
    data.views?.supported_posts ??
    data.posts.filter(
      (post) => post.views_total !== null && post.views_total !== undefined,
    ).length;
  const maxBlogPosts = Math.max(
    1,
    ...blogStats.map((row) => row.postsTotal),
  );
  const todayRows = [...blogStats].sort(
    (left, right) =>
      right.postsToday - left.postsToday ||
      right.postsTotal - left.postsTotal,
  );

  return (
    <div className="min-h-screen bg-[#f6f7f4] text-foreground">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="min-w-0 lg:pl-[240px]">
        <div className="mx-auto max-w-[1240px] px-4 py-5 sm:px-6 lg:px-10 lg:py-8">
          <header className="mb-6 flex items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <Button
                variant="outline"
                size="icon"
                className="shrink-0 lg:hidden"
                onClick={() => setSidebarOpen(true)}
                aria-label="메뉴 열기"
              >
                <Menu className="h-5 w-5" />
              </Button>
              <div className="min-w-0">
                <h1 className="truncate text-2xl font-extrabold tracking-[-0.04em] text-slate-900 sm:text-3xl">
                  콘텐츠 인텔리전스
                </h1>
                <p className="mt-1 hidden text-sm text-muted-foreground sm:block">
                  15개 블로그의 발행과 조회 흐름을 한눈에 확인하세요.
                </p>
              </div>
            </div>
            <button
              className="flex shrink-0 items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3 text-left shadow-sm transition hover:border-slate-300"
              onClick={() => void loadData(true)}
              aria-label="데이터 새로고침"
            >
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-40" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
              </span>
              <span className="hidden sm:block">
                <span className="block text-xs font-semibold text-slate-800">
                  {formatDate(data.generated_at, true)} 최신
                </span>
                <span className="mt-0.5 block text-[10px] text-muted-foreground">
                  KST · 매시간 자동 업데이트
                </span>
              </span>
              <RefreshCw
                className={cn(
                  "h-4 w-4 text-slate-400",
                  refreshing && "animate-spin",
                )}
              />
            </button>
          </header>

          <section
            id="overview"
            className="relative overflow-hidden rounded-[24px] bg-[#0b1220] px-6 py-7 text-white sm:px-8 sm:py-8"
          >
            <div className="absolute -right-12 -top-16 h-72 w-72 rounded-full bg-[#b7f34a]/15" />
            <div className="relative flex flex-col justify-between gap-8 lg:flex-row lg:items-center">
              <div>
                <Badge className="border-[#23314b] bg-[#121e34] text-[#b7f34a]">
                  <Sparkles className="mr-1.5 h-3 w-3" />
                  HOURLY LIVE INDEX
                </Badge>
                <h2 className="mt-5 text-3xl font-extrabold tracking-[-0.045em] sm:text-4xl">
                  블로그 포스트 통합 현황
                </h2>
                <p className="mt-3 text-sm text-slate-300">
                  발행량, 누적 조회수, 당일 성장률을 실시간에 가깝게
                  추적합니다.
                </p>
              </div>
              <div className="relative text-left lg:text-right">
                <div className="text-4xl font-extrabold tracking-[-0.04em] sm:text-5xl">
                  {formatNumber(totalPosts)}
                </div>
                <div className="mt-2 text-[10px] font-semibold tracking-[0.13em] text-slate-400">
                  INDEXED POSTS
                </div>
              </div>
            </div>
          </section>

          <section className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="오늘 발행"
              value={formatNumber(todayPosts)}
              note={`${statsDate} · KST 기준`}
              icon={BookOpen}
              tone="emerald"
            />
            <MetricCard
              label="연결 블로그"
              value={formatNumber(data.blog_count ?? blogStats.length)}
              note="WikiDocs 14 · Tilnote 1"
              icon={Bot}
              tone="blue"
            />
            <MetricCard
              label="누적 조회수"
              value={formatCompact(totalViews)}
              note={`조회 지원 ${formatNumber(supportedPosts)}개 포스트`}
              icon={Eye}
              tone="amber"
            />
            <MetricCard
              label="오늘 조회수"
              value={formatCompact(todayViews)}
              note="당일 시작 스냅샷 대비"
              icon={Activity}
              tone="coral"
            />
          </section>

          <section className="mt-5 grid gap-5 xl:grid-cols-[1.8fr_0.9fr]">
            <Card>
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle>발행 추이</CardTitle>
                  <CardDescription className="mt-1">최근 14일</CardDescription>
                </div>
                <Badge className="border-transparent bg-blue-50 text-blue-600">
                  게시물
                </Badge>
              </CardHeader>
              <CardContent className="h-[270px] pl-2 pr-5">
                <Suspense fallback={<Skeleton className="h-full w-full" />}>
                  <PublishingChart data={trendData} />
                </Suspense>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle>오늘 발행 현황</CardTitle>
                  <CardDescription className="mt-1">
                    블로그별 당일 발행량
                  </CardDescription>
                </div>
                <Badge className="border-transparent bg-emerald-50 text-emerald-600">
                  {formatNumber(todayPosts)} POST
                </Badge>
              </CardHeader>
              <CardContent>
                <div className="divide-y divide-border">
                  {todayRows.slice(0, 5).map((row, index) => (
                    <button
                      key={row.key}
                      className="flex w-full items-center gap-3 py-3 text-left transition hover:text-blue-600"
                      onClick={() => selectBlog(row.blogName, true)}
                    >
                      <span
                        className={cn(
                          "h-2.5 w-2.5 rounded-full",
                          [
                            "bg-blue-600",
                            "bg-[#ff6b57]",
                            "bg-amber-500",
                            "bg-emerald-500",
                            "bg-violet-600",
                          ][index],
                        )}
                      />
                      <span className="min-w-0 flex-1 truncate text-xs font-semibold">
                        {row.blogName}
                      </span>
                      <strong className="text-sm">
                        {formatNumber(row.postsToday)}
                      </strong>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </section>

          <section id="blogs" className="mt-5 scroll-mt-5">
            <Card>
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle>블로그별 발행 현황</CardTitle>
                  <CardDescription className="mt-1">
                    포스트와 조회 성과 비교
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setBlog("");
                    postSectionRef.current?.scrollIntoView({
                      behavior: "smooth",
                    });
                  }}
                >
                  전체 보기
                  <ArrowUpRight className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="min-w-[220px]">블로그</TableHead>
                      <TableHead>플랫폼</TableHead>
                      <TableHead className="text-right">전체 글</TableHead>
                      <TableHead className="text-right">오늘</TableHead>
                      <TableHead className="text-right">누적 조회</TableHead>
                      <TableHead className="text-right">오늘 조회</TableHead>
                      <TableHead className="min-w-[120px]">발행 비중</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {blogStats.map((row) => (
                      <TableRow
                        key={row.key}
                        className="cursor-pointer"
                        onClick={() => selectBlog(row.blogName)}
                      >
                        <TableCell className="font-semibold">
                          {row.blogName}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              row.platform === "Tilnote"
                                ? "tilnote"
                                : "wikidocs"
                            }
                          >
                            {row.platform}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-semibold tabular-nums">
                          {formatNumber(row.postsTotal)}
                        </TableCell>
                        <TableCell className="text-right font-bold tabular-nums">
                          {formatNumber(row.postsToday)}
                        </TableCell>
                        <TableCell className="text-right font-medium tabular-nums">
                          {formatNumber(row.viewsTotal)}
                        </TableCell>
                        <TableCell className="text-right font-bold text-emerald-600 tabular-nums">
                          {formatNumber(row.viewsToday)}
                        </TableCell>
                        <TableCell>
                          <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                            <div
                              className="h-full rounded-full bg-[#b7f34a]"
                              style={{
                                width: `${Math.max(
                                  2,
                                  (row.postsTotal / maxBlogPosts) * 100,
                                )}%`,
                              }}
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </section>

          <section id="coverage" className="mt-5 scroll-mt-5">
            <div className="flex flex-col gap-3 rounded-2xl border border-emerald-200/70 bg-emerald-50/70 px-5 py-4 text-xs text-emerald-950 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <Database className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                <div>
                  <strong>조회수 집계 범위</strong>
                  <span className="ml-2 text-emerald-800">
                    {formatNumber(supportedPosts)} / {formatNumber(totalPosts)}
                    개 포스트
                  </span>
                  <p className="mt-1 text-[11px] leading-5 text-emerald-800/80">
                    Tilnote 공개 API 제공 범위를 매시간 갱신합니다. WikiDocs는
                    공식 API에서 조회수를 제공하지 않습니다.
                  </p>
                </div>
              </div>
              <div className="shrink-0 text-[10px] text-emerald-800/70">
                마지막 확인 {formatDate(data.views?.checked_at, true)}
              </div>
            </div>
          </section>

          <section
            ref={postSectionRef}
            id="posts"
            className="mt-5 scroll-mt-5"
          >
            <Card>
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle>전체 포스트</CardTitle>
                  <CardDescription className="mt-1">
                    {formatNumber(totalPosts)}개 콘텐츠 디렉터리
                  </CardDescription>
                </div>
                <Button asChild size="sm" className="hidden sm:inline-flex">
                  <a
                    href={`${import.meta.env.BASE_URL}data/posts.csv`}
                    download
                  >
                    <CloudDownload className="mr-2 h-4 w-4" />
                    CSV 내려받기
                  </a>
                </Button>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 lg:grid-cols-[minmax(260px,1fr)_repeat(4,minmax(120px,auto))]">
                  <label className="relative">
                    <Search className="pointer-events-none absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                    <Input
                      type="search"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="제목 또는 블로그 검색"
                      className="pl-10"
                    />
                  </label>
                  <select
                    value={platform}
                    onChange={(event) => setPlatform(event.target.value)}
                    className={selectClassName()}
                    aria-label="플랫폼 선택"
                  >
                    <option value="">모든 플랫폼</option>
                    <option value="WikiDocs">WikiDocs</option>
                    <option value="Tilnote">Tilnote</option>
                  </select>
                  <select
                    value={blog}
                    onChange={(event) => setBlog(event.target.value)}
                    className={selectClassName()}
                    aria-label="블로그 선택"
                  >
                    <option value="">모든 블로그</option>
                    {blogs.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  <select
                    value={day}
                    onChange={(event) => setDay(event.target.value)}
                    className={selectClassName()}
                    aria-label="발행일 선택"
                  >
                    <option value="">전체 날짜</option>
                    <option value="today">오늘 발행만</option>
                  </select>
                  <select
                    value={sort}
                    onChange={(event) => setSort(event.target.value)}
                    className={selectClassName()}
                    aria-label="정렬 선택"
                  >
                    <option value="newest">최신 발행순</option>
                    <option value="oldest">오래된 발행순</option>
                    <option value="views">누적 조회수순</option>
                    <option value="today-views">오늘 조회수순</option>
                    <option value="title">제목순</option>
                  </select>
                </div>

                <div className="mt-4 overflow-hidden rounded-xl border border-border">
                  <Table>
                    <TableHeader className="bg-slate-50/80">
                      <TableRow>
                        <TableHead>플랫폼</TableHead>
                        <TableHead className="min-w-[180px]">블로그</TableHead>
                        <TableHead className="min-w-[360px]">
                          포스트 제목
                        </TableHead>
                        <TableHead className="whitespace-nowrap">
                          발행일
                        </TableHead>
                        <TableHead className="text-right">누적 조회</TableHead>
                        <TableHead className="text-right">오늘 조회</TableHead>
                        <TableHead>
                          <span className="sr-only">열기</span>
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {visiblePosts.map((post) => (
                        <TableRow key={post.key}>
                          <TableCell>
                            <Badge
                              variant={
                                post.platform === "Tilnote"
                                  ? "tilnote"
                                  : "wikidocs"
                              }
                            >
                              {post.platform}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-semibold">
                            {post.blog_name}
                          </TableCell>
                          <TableCell>
                            <a
                              href={post.post_url}
                              target="_blank"
                              rel="noreferrer"
                              className="line-clamp-1 font-medium text-slate-900 transition hover:text-blue-600"
                            >
                              {post.title}
                            </a>
                          </TableCell>
                          <TableCell
                            className="whitespace-nowrap text-xs text-muted-foreground"
                            title={
                              post.post_date_source === "first_seen"
                                ? "원문 발행일 미제공 · 최초 수집일 기준"
                                : "원문 발행일"
                            }
                          >
                            {formatDate(
                              `${postDate(post)}T00:00:00+09:00`,
                            )}
                            {post.post_date_source === "first_seen" ? "*" : ""}
                          </TableCell>
                          <TableCell className="text-right font-semibold tabular-nums">
                            {formatNumber(post.views_total)}
                          </TableCell>
                          <TableCell className="text-right font-bold text-emerald-600 tabular-nums">
                            {formatNumber(post.views_today)}
                          </TableCell>
                          <TableCell>
                            <Button variant="ghost" size="icon" asChild>
                              <a
                                href={post.post_url}
                                target="_blank"
                                rel="noreferrer"
                                aria-label={`${post.title} 열기`}
                              >
                                <ArrowUpRight className="h-4 w-4" />
                              </a>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {!visiblePosts.length && (
                    <div className="grid min-h-40 place-items-center text-sm text-muted-foreground">
                      조건과 일치하는 포스트가 없습니다.
                    </div>
                  )}
                </div>

                <footer className="mt-4 flex flex-col gap-3 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
                  <span>
                    {filteredPosts.length
                      ? formatNumber((safePage - 1) * PER_PAGE + 1)
                      : 0}
                    –
                    {formatNumber(
                      Math.min(safePage * PER_PAGE, filteredPosts.length),
                    )}{" "}
                    / {formatNumber(filteredPosts.length)}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="mr-2">
                      {safePage} / {maxPage} 페이지
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={safePage <= 1}
                      onClick={() => setPage((current) => current - 1)}
                    >
                      <ChevronLeft className="mr-1 h-4 w-4" />
                      이전
                    </Button>
                    <Button
                      size="sm"
                      disabled={safePage >= maxPage}
                      onClick={() => setPage((current) => current + 1)}
                    >
                      다음
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Button>
                  </div>
                </footer>
              </CardContent>
            </Card>
          </section>

          <footer className="flex flex-col gap-2 px-1 pb-3 pt-7 text-[11px] text-muted-foreground sm:flex-row sm:justify-between">
            <span>
              데이터 범위 · 공개 메타데이터 및 제공 가능한 조회수 기준
            </span>
            <a
              href="https://github.com/yiugn/blog-post-dashboard"
              className="font-semibold transition hover:text-slate-900"
            >
              GitHub Actions · Hourly
            </a>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default App;
