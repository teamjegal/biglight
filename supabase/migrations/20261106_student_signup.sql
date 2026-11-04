-- ClassHub LMS — 학생 회원가입 RPC.
--
-- lms_users 는 anon 키로 직접 쓸 수 없으므로, 가입은 서버 함수로만 가능하다.
-- 이 함수로 만들 수 있는 역할은 학생(student)뿐이다. 교수·관리자 계정은
-- 관리자 화면(lms_admin_create_user)으로만 발급한다.

create or replace function lms_signup_student(
  p_login_id text,
  p_password text,
  p_name text,
  p_department text
)
returns bigint
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  new_id bigint;
  v_login text := trim(coalesce(p_login_id, ''));
  v_name text := trim(coalesce(p_name, ''));
begin
  if v_login !~ '^[0-9]{6,12}$' then
    raise exception 'invalid student id' using errcode = '22023';
  end if;
  if length(v_name) = 0 or length(v_name) > 30 then
    raise exception 'invalid name' using errcode = '22023';
  end if;
  if length(coalesce(p_password, '')) < 8 then
    raise exception 'password too short' using errcode = '22023';
  end if;

  insert into lms_users (login_id, password_hash, role, name, department, semester)
  values (v_login, crypt(p_password, gen_salt('bf')), 'student', v_name,
          nullif(trim(coalesce(p_department, '')), ''), '2026학년도 1학기')
  returning id into new_id;

  return new_id;
end;
$$;

revoke all on function lms_signup_student(text, text, text, text) from public;
grant execute on function lms_signup_student(text, text, text, text) to anon, authenticated;
