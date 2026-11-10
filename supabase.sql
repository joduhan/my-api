-- Supabase 대시보드 > SQL Editor 에서 한 번 실행 (여러 번 실행해도 안전)

-- 1) 메모 (테스트용)
create table if not exists public.notes (
  id bigint generated always as identity primary key,
  content text not null,
  created_at timestamptz not null default now()
);

-- 2) 상품
create table if not exists public.products (
  id bigint generated always as identity primary key,
  name text not null,
  description text not null default '',
  price integer not null check (price >= 0),   -- 원(KRW)
  emoji text not null default '🎁',
  category text not null default '기타'
);

-- 3) 장바구니 (cart_id = 브라우저가 만든 임의의 UUID)
create table if not exists public.cart_items (
  id bigint generated always as identity primary key,
  cart_id text not null,
  product_id bigint not null references public.products(id) on delete cascade,
  quantity integer not null default 1 check (quantity between 1 and 99),
  created_at timestamptz not null default now(),
  unique (cart_id, product_id)
);
create index if not exists cart_items_cart_id_idx on public.cart_items (cart_id);

-- 4) [보안] RLS 켜기: 공개(anon) 키로는 이 테이블에 직접 접근 불가.
--    우리 FastAPI는 secret 키를 쓰므로 RLS를 우회해서 정상 동작함.
alter table public.notes enable row level security;
alter table public.products enable row level security;
alter table public.cart_items enable row level security;

-- 5) 샘플 상품 (비어 있을 때만 넣음)
insert into public.products (name, description, price, emoji, category)
select * from (values
  ('감귤 초콜릿',   '제주 감귤 향이 퍼지는 달콤한 초콜릿',   9900, '🍊', '간식'),
  ('한라봉 주스',   '착즙 그대로, 새콤달콤 한라봉 100%',      6500, '🧃', '음료'),
  ('흑돼지 육포',   '쫄깃하고 고소한 제주 흑돼지 육포',      12000, '🥓', '간식'),
  ('오메기떡 세트', '팥고물 가득, 제주 전통 오메기떡 6입',   15000, '🍡', '간식'),
  ('제주 녹차',     '오설록 스타일 청정 녹차 티백 20입',     11000, '🍵', '음료'),
  ('돌하르방 마그넷','냉장고에 붙이는 귀여운 돌하르방',        4500, '🗿', '기념품'),
  ('해녀 에코백',   '바다를 닮은 튼튼한 캔버스 에코백',      13500, '👜', '기념품'),
  ('유채꽃 향초',   '봄 제주의 향기를 담은 소이 캔들',       18000, '🕯️', '기념품')
) as v(name, description, price, emoji, category)
where not exists (select 1 from public.products);
