-- Supabase 대시보드 > SQL Editor 에서 한 번 실행
create table if not exists public.notes (
  id bigint generated always as identity primary key,
  content text not null,
  created_at timestamptz not null default now()
);
