export interface Post {
  key: string;
  platform: "WikiDocs" | "Tilnote" | string;
  slug: string;
  blog_name: string;
  blog_url: string;
  account_masked?: string;
  post_id: string;
  title: string;
  post_url: string;
  published_at?: string;
  first_seen_at?: string;
  last_seen_at?: string;
  post_date?: string;
  post_date_source?: string;
  views_total?: number | null;
  views_today?: number | null;
  views_checked_at?: string;
}

export interface ViewSummary {
  total?: number;
  today?: number;
  supported_posts?: number;
  total_posts?: number;
  supported_blogs?: number;
  total_blogs?: number;
  checked_at?: string;
  note?: string;
}

export interface BlogStat {
  key: string;
  platform: string;
  slug: string;
  blogName: string;
  postsTotal: number;
  postsToday: number;
  viewsTotal: number | null;
  viewsToday: number | null;
  viewPosts: number;
}

export interface DashboardData {
  generated_at?: string;
  stats_date?: string;
  total_posts?: number;
  blog_count?: number;
  views?: ViewSummary;
  source_state?: {
    tilnote?: {
      total_pages?: number;
      completed_count?: number;
      completed_pages?: number[];
      history_complete?: boolean;
    };
  };
  posts: Post[];
}
