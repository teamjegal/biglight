-- ClassHub LMS — 관리자(admin) 역할과 교수 계정 생성 RPC.
--
-- lms_users 는 anon 키로 직접 쓸 수 없으므로(컬럼 단위 읽기만 허용), 계정 생성은
-- 서버 함수로만 가능하다. 함수는 호출할 때마다 관리자 아이디/비밀번호를 DB 에서
-- 다시 검증하고, 만들 수 있는 역할은 교수(professor)뿐이다(admin 은 만들 수 없음).

alter table lms_users drop constraint if exists lms_users_role_check;
alter table lms_users add constraint lms_users_role_check
  check (role in ('student', 'professor', 'admin'));

create or replace function lms_admin_create_user(
  p_admin_id text,
  p_admin_password text,
  p_login_id text,
  p_password text,
  p_name text,
  p_department text,
  p_semester text
)
returns bigint
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  new_id bigint;
begin
  if not exists (
    select 1 from lms_users u
    where u.login_id = p_admin_id
      and u.role = 'admin'
      and u.password_hash = crypt(p_admin_password, u.password_hash)
  ) then
    raise exception 'invalid admin credentials' using errcode = '42501';
  end if;

  if length(coalesce(p_password, '')) < 8 then
    raise exception 'password too short' using errcode = '22023';
  end if;
  if length(trim(coalesce(p_login_id, ''))) = 0 or length(trim(coalesce(p_name, ''))) = 0 then
    raise exception 'login id and name are required' using errcode = '22023';
  end if;

  insert into lms_users (login_id, password_hash, role, name, department, semester)
  values (trim(p_login_id), crypt(p_password, gen_salt('bf')), 'professor',
          trim(p_name), nullif(trim(coalesce(p_department, '')), ''), p_semester)
  returning id into new_id;

  return new_id;
end;
$$;

revoke all on function lms_admin_create_user(text, text, text, text, text, text, text) from public;
grant execute on function lms_admin_create_user(text, text, text, text, text, text, text)
  to anon, authenticated;
