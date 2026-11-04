-- ClassHub LMS 데모 시드 (멱등: 지우고 다시 넣는다). 모든 데이터는 가상이다.
--
-- 데모 계정 (비밀번호는 DB에 bcrypt 해시로만 저장됨)
--   교수  P2001(박지우·운영체제) / P2002(이서연·자료구조) / P2003(정민호·글쓰기)  → 비밀번호 prof1234
--   학생  202512345(김한결) / 202512346(이도윤) / 202512347(최서윤)               → 비밀번호 student1234
-- 이 계정은 공개 데모용이다. 실서비스 계정에 같은 값을 쓰지 말 것.

delete from lms_qna_replies;
delete from lms_qna;
delete from lms_lecture_progress;
delete from lms_lectures;
delete from lms_exams;
delete from lms_announcements;
delete from lms_attendance;
delete from lms_submissions;
delete from lms_assignments;
delete from lms_materials;
delete from lms_enrollments;
delete from lms_courses;
delete from lms_users;

insert into lms_users (login_id, password_hash, role, name, department, semester) values
  ('P2001', extensions.crypt('prof1234', extensions.gen_salt('bf')), 'professor', '박지우', '컴퓨터공학과', '2026학년도 1학기'),
  ('P2002', extensions.crypt('prof1234', extensions.gen_salt('bf')), 'professor', '이서연', '컴퓨터공학과', '2026학년도 1학기'),
  ('P2003', extensions.crypt('prof1234', extensions.gen_salt('bf')), 'professor', '정민호', '교양대학', '2026학년도 1학기'),
  ('202512345', extensions.crypt('student1234', extensions.gen_salt('bf')), 'student', '김한결', '컴퓨터공학과', '2026학년도 1학기'),
  ('202512346', extensions.crypt('student1234', extensions.gen_salt('bf')), 'student', '이도윤', '컴퓨터공학과', '2026학년도 1학기'),
  ('202512347', extensions.crypt('student1234', extensions.gen_salt('bf')), 'student', '최서윤', '컴퓨터공학과', '2026학년도 1학기');

insert into lms_courses (id, title, professor_id, schedule, room, card_color, course_code, sort_order)
select v.id, v.title, u.id, v.schedule, v.room, v.color, v.code, v.ord
from (values
  ('CSE311', '운영체제', 'P2001', '월·수 10:00–11:15', '공학관 401', '#3b5bdb', '0001765003', 1),
  ('CSE245', '자료구조', 'P2002', '화·목 13:00–14:15', '공학관 207', '#2f9e44', '0001772003', 2),
  ('GEN102', '글쓰기와 커뮤니케이션', 'P2003', '금 09:00–11:45', '인문관 115', '#e8590c', '0000936039', 3)
) v(id, title, prof, schedule, room, color, code, ord)
join lms_users u on u.login_id = v.prof;

insert into lms_enrollments (course_id, student_id)
select v.c, u.id from (values
  ('CSE311', '202512345'), ('CSE245', '202512345'), ('GEN102', '202512345'),
  ('CSE311', '202512346'), ('CSE245', '202512346'),
  ('CSE311', '202512347'), ('GEN102', '202512347')
) v(c, l) join lms_users u on u.login_id = v.l;

insert into lms_materials (course_id, week, title, type, size_kb, posted) values
  ('CSE311', 1, '강의 개요와 운영체제의 역할', 'PDF', 1240, '2026-03-09'),
  ('CSE311', 2, '프로세스와 스레드', 'PDF', 2010, '2026-03-16'),
  ('CSE311', 3, 'CPU 스케줄링', 'PDF', 1875, '2026-03-23'),
  ('CSE311', 4, '동기화와 교착 상태', '슬라이드', 3320, '2026-03-30'),
  ('CSE311', 5, '메모리 관리 기법', 'PDF', 2460, '2026-04-06'),
  ('CSE245', 1, '복잡도 분석과 빅오 표기법', 'PDF', 980, '2026-03-10'),
  ('CSE245', 2, '배열과 연결 리스트', 'PDF', 1530, '2026-03-17'),
  ('CSE245', 3, '스택과 큐', '슬라이드', 2140, '2026-03-24'),
  ('CSE245', 4, '트리와 이진 탐색 트리', 'PDF', 2680, '2026-04-07'),
  ('GEN102', 1, '학술적 글쓰기의 기초', 'PDF', 760, '2026-03-11'),
  ('GEN102', 2, '논증 구조 세우기', 'PDF', 1120, '2026-03-25'),
  ('GEN102', 3, '자료 인용과 출처 표기', '슬라이드', 1890, '2026-04-08');

insert into lms_assignments (id, course_id, title, due, points) values
  ('CSE311-A1', 'CSE311', '프로세스 상태 전이도 작성', '2026-04-03', 20),
  ('CSE311-A2', 'CSE311', '라운드로빈 스케줄러 구현', '2026-04-15', 30),
  ('CSE311-A3', 'CSE311', '교착 상태 탐지 보고서', '2026-04-22', 25),
  ('CSE245-A1', 'CSE245', '연결 리스트 ADT 구현', '2026-03-29', 20),
  ('CSE245-A2', 'CSE245', '이진 탐색 트리 순회', '2026-04-18', 25),
  ('GEN102-A1', 'GEN102', '주제문 초안 제출', '2026-04-10', 15),
  ('GEN102-A2', 'GEN102', '에세이 1차 원고', '2026-04-25', 30);

insert into lms_submissions (assignment_id, student_id, status, score, late, submitted_at)
select v.a, u.id, v.st, v.sc, v.late, v.d::date from (values
  ('CSE311-A1', '202512345', 'graded', 18, false, '2026-04-02'),
  ('CSE311-A2', '202512345', 'submitted', null::int, false, '2026-04-12'),
  ('CSE245-A1', '202512345', 'graded', 20, false, '2026-03-28'),
  ('CSE311-A1', '202512346', 'graded', 15, false, '2026-04-03'),
  ('CSE311-A2', '202512346', 'submitted', null::int, false, '2026-04-11'),
  ('CSE245-A1', '202512346', 'graded', 17, false, '2026-03-29'),
  ('CSE245-A2', '202512346', 'submitted', null::int, false, '2026-04-12'),
  ('CSE311-A1', '202512347', 'graded', 20, false, '2026-04-01'),
  ('CSE311-A2', '202512347', 'submitted', null::int, false, '2026-04-12'),
  ('GEN102-A1', '202512347', 'submitted', null::int, true, '2026-04-11')
) v(a, l, st, sc, late, d) join lms_users u on u.login_id = v.l;

insert into lms_attendance (course_id, student_id, week, date, status)
select v.c, u.id, t.w::int, v.base + 7 * (t.w::int - 1), t.s
from (values
  ('CSE311', '202512345', array['present','present','present','late','present'], date '2026-03-09'),
  ('CSE245', '202512345', array['present','present','absent','present'],          date '2026-03-10'),
  ('GEN102', '202512345', array['present','present','present'],                   date '2026-03-11'),
  ('CSE311', '202512346', array['present','late','present','present','present'],  date '2026-03-09'),
  ('CSE245', '202512346', array['present','late','present','present'],            date '2026-03-10'),
  ('CSE311', '202512347', array['present','present','absent','present','present'], date '2026-03-09'),
  ('GEN102', '202512347', array['present','present','late'],                      date '2026-03-11')
) v(c, l, sts, base)
join lms_users u on u.login_id = v.l
cross join lateral unnest(v.sts) with ordinality as t(s, w);

insert into lms_announcements (course_id, author_id, title, body, posted, pinned)
select v.c, u.id, v.title, v.body, v.posted::date, v.pinned
from (values
  (null::text, null::text, '중간고사 기간 도서관 24시간 개방 안내', '중간고사 기간 동안 중앙도서관을 24시간 개방합니다.', '2026-04-11', true),
  ('CSE311', 'P2001', '4주차 보강 안내', '지난주 휴강분 보강을 금요일 16시 공학관 401에서 진행합니다.', '2026-04-09', false),
  ('CSE311', 'P2001', '과제 2 제출 형식 공지', '라운드로빈 스케줄러는 소스와 실행 캡처를 zip으로 묶어 제출하세요.', '2026-04-07', false),
  ('CSE245', 'P2002', '실습실 PC 사용 안내', '자료구조 실습은 공학관 207 실습 PC에서도 가능합니다.', '2026-04-05', false),
  ('GEN102', 'P2003', '에세이 분량 기준', '1차 원고는 A4 3~4매 분량으로 작성합니다.', '2026-04-08', false)
) v(c, a, title, body, posted, pinned)
left join lms_users u on u.login_id = v.a;

insert into lms_exams (course_id, student_id, name, score, max, date)
select v.c, u.id, '중간고사', v.sc, 50, v.d::date from (values
  ('CSE311', '202512345', 42, '2026-04-12'), ('CSE245', '202512345', 47, '2026-04-11'),
  ('CSE311', '202512346', 38, '2026-04-12'), ('CSE245', '202512346', 41, '2026-04-11'),
  ('CSE311', '202512347', 45, '2026-04-12')
) v(c, l, sc, d) join lms_users u on u.login_id = v.l;

insert into lms_lectures (course_id, week, title, duration_min) values
  ('CSE311', 1, '운영체제란 무엇인가', 48),
  ('CSE311', 2, '프로세스 생성과 종료', 52),
  ('CSE311', 3, '스케줄링 알고리즘 비교', 45),
  ('CSE311', 4, '세마포어와 뮤텍스', 50),
  ('CSE245', 1, '빅오 표기법 직관', 38),
  ('CSE245', 2, '연결 리스트 구현', 41),
  ('CSE245', 3, '스택으로 괄호 검사', 35),
  ('GEN102', 1, '좋은 글의 조건', 30),
  ('GEN102', 2, '논증과 근거', 33);

insert into lms_lecture_progress (lecture_id, student_id, watched_pct)
select l.id, u.id, t.p::int
from (values
  ('CSE311', '202512345', array[100,100,60,0]),
  ('CSE245', '202512345', array[100,80,0]),
  ('GEN102', '202512345', array[100,50]),
  ('CSE311', '202512346', array[100,70,0,0]),
  ('CSE245', '202512346', array[100,100,40]),
  ('CSE311', '202512347', array[100,100,100,30]),
  ('GEN102', '202512347', array[100,100])
) v(c, lg, ps)
join lms_users u on u.login_id = v.lg
cross join lateral unnest(v.ps) with ordinality as t(p, w)
join lms_lectures l on l.course_id = v.c and l.week = t.w::int;

with q1 as (
  insert into lms_qna (course_id, author_id, author, title, body, posted, answered)
  select 'CSE311', u.id, u.name, '라운드로빈 타임 퀀텀 값 질문',
         '과제 2에서 타임 퀀텀은 고정값으로 두면 되나요?', '2026-04-10', true
  from lms_users u where u.login_id = '202512345'
  returning id
)
insert into lms_qna_replies (qna_id, author_id, author, body)
select q1.id, p.id, p.name || ' 교수', '네, 4ms로 고정해서 구현하세요.'
from q1, lms_users p where p.login_id = 'P2001';

insert into lms_qna (course_id, author_id, author, title, body, posted, answered)
select 'CSE245', u.id, u.name, 'BST 중복 키 처리',
       '이진 탐색 트리에 중복 키가 들어오면 어떻게 처리하나요?', '2026-04-12', false
from lms_users u where u.login_id = '202512346';
