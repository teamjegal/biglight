-- ClassHub LMS v2 — 로그인 + 학생/교수 역할 분리 스키마.
--
-- v1(학생 1명 전용) 테이블을 모두 지우고 다시 만든다. 데모 데이터는
-- supabase/seed.sql 로 다시 채운다. 모든 테이블은 lms_ 접두사를 쓴다.

drop table if exists
  lms_qna_replies, lms_qna, lms_lecture_progress, lms_lectures, lms_exams,
  lms_announcements, lms_attendance, lms_submissions, lms_assignments,
  lms_materials, lms_enrollments, lms_courses, lms_students, lms_users
  cascade;
drop function if exists lms_login(text, text);

create extension if not exists pgcrypto with schema extensions;

-- 계정. 비밀번호는 bcrypt 해시로만 저장한다.
create table lms_users (
  id bigint generated always as identity primary key,
  login_id text unique not null,            -- 학번(학생) / 사번(교수)
  password_hash text not null,
  role text not null check (role in ('student', 'professor')),
  name text not null,
  department text,
  semester text
);

create table lms_courses (
  id text primary key,
  title text not null,
  professor_id bigint references lms_users(id),
  schedule text,
  room text,
  card_color text,
  course_code text,
  sort_order int default 0
);

create table lms_enrollments (
  id bigint generated always as identity primary key,
  course_id text not null references lms_courses(id) on delete cascade,
  student_id bigint not null references lms_users(id) on delete cascade,
  unique (course_id, student_id)
);

create table lms_materials (
  id bigint generated always as identity primary key,
  course_id text not null references lms_courses(id) on delete cascade,
  week int,
  title text,
  type text,
  size_kb int,
  posted date
);

-- 과제는 과목 단위, 제출/채점은 학생 단위.
create table lms_assignments (
  id text primary key,
  course_id text not null references lms_courses(id) on delete cascade,
  title text,
  due date,
  points int
);

create table lms_submissions (
  id bigint generated always as identity primary key,
  assignment_id text not null references lms_assignments(id) on delete cascade,
  student_id bigint not null references lms_users(id) on delete cascade,
  status text not null default 'submitted' check (status in ('submitted', 'graded')),
  score int,
  late boolean default false,
  submitted_at date,
  unique (assignment_id, student_id)
);

create table lms_attendance (
  id bigint generated always as identity primary key,
  course_id text not null references lms_courses(id) on delete cascade,
  student_id bigint not null references lms_users(id) on delete cascade,
  week int not null,
  date date,
  status text not null check (status in ('present', 'late', 'absent')),
  unique (course_id, student_id, week)
);

create table lms_announcements (
  id bigint generated always as identity primary key,
  course_id text references lms_courses(id) on delete cascade,  -- null = 전체 공지
  author_id bigint references lms_users(id),
  title text,
  body text,
  posted date,
  pinned boolean default false
);

create table lms_exams (
  id bigint generated always as identity primary key,
  course_id text not null references lms_courses(id) on delete cascade,
  student_id bigint not null references lms_users(id) on delete cascade,
  name text,
  score int,
  max int,
  date date
);

create table lms_lectures (
  id bigint generated always as identity primary key,
  course_id text not null references lms_courses(id) on delete cascade,
  week int,
  title text,
  duration_min int
);

create table lms_lecture_progress (
  id bigint generated always as identity primary key,
  lecture_id bigint not null references lms_lectures(id) on delete cascade,
  student_id bigint not null references lms_users(id) on delete cascade,
  watched_pct int not null default 0,
  unique (lecture_id, student_id)
);

create table lms_qna (
  id bigint generated always as identity primary key,
  course_id text not null references lms_courses(id) on delete cascade,
  author_id bigint references lms_users(id),
  author text,
  title text,
  body text,
  posted date,
  answered boolean default false
);

create table lms_qna_replies (
  id bigint generated always as identity primary key,
  qna_id bigint not null references lms_qna(id) on delete cascade,
  author_id bigint references lms_users(id),
  author text,
  body text,
  created_at timestamptz default now()
);

-- 로그인: 서버(DB)에서 해시를 비교하고, 비밀번호 해시는 절대 돌려주지 않는다.
create function lms_login(p_login_id text, p_password text)
returns table (id bigint, login_id text, role text, name text, department text, semester text)
language sql
security definer
set search_path = public, extensions
as $$
  select u.id, u.login_id, u.role, u.name, u.department, u.semester
  from lms_users u
  where u.login_id = p_login_id
    and u.password_hash = crypt(p_password, u.password_hash);
$$;

revoke all on function lms_login(text, text) from public;
grant execute on function lms_login(text, text) to anon, authenticated;

-- lms_users: 해시 컬럼은 anon/authenticated 가 읽을 수 없게 컬럼 단위로만 허용.
alter table lms_users enable row level security;
revoke all on lms_users from anon, authenticated;
grant select (id, login_id, role, name, department, semester)
  on lms_users to anon, authenticated;
create policy lms_users_read on lms_users
  for select to anon, authenticated using (true);

-- 나머지 테이블: 데모용 전체 허용 RLS.
-- 주의: 역할(학생/교수) 권한은 앱 계층에서만 지킨다. 실서비스라면 Supabase Auth
-- JWT 기반 RLS 정책으로 DB에서 강제해야 한다.
do $$
declare t text;
begin
  foreach t in array array[
    'lms_courses', 'lms_enrollments', 'lms_materials', 'lms_assignments',
    'lms_submissions', 'lms_attendance', 'lms_announcements', 'lms_exams',
    'lms_lectures', 'lms_lecture_progress', 'lms_qna', 'lms_qna_replies'
  ] loop
    execute format('alter table %I enable row level security;', t);
    execute format(
      'create policy %I on %I for all to anon, authenticated using (true) with check (true);',
      t || '_demo_all', t
    );
  end loop;
end $$;
